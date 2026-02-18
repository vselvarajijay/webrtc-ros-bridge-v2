#!/usr/bin/env python3
"""
Smooth arrow-key teleop: publishes Twist to /cmd_vel with velocity ramping.

Improvements over naive version:
  - Velocity ramps up/down over RAMP_TIME instead of jumping to max speed
  - Key state is tracked by a dedicated thread using evdev-style raw reads,
    NOT by timestamping queue entries, eliminating the OS key-repeat race condition
  - A single high-frequency timer drives all velocity updates (50 Hz)
  - Stopping is exponential decay (feels natural) rather than instant zeroing
  - Telemetry-aware safety limits (battery, GPS, stuck detection)
  - Live HUD display showing telemetry status
"""

import sys
import threading
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

# Terminal input - no X11 dependencies needed for direct robot control
import termios
import tty
import select

# Try to import keyboard library for key release detection
try:
    import keyboard
    HAS_KEYBOARD_LIB = True
except ImportError:
    HAS_KEYBOARD_LIB = False
    keyboard = None

from scout_robot_bridge.core.config_manager import ConfigManager
from scout_robot_bridge.core.constants import DEFAULT_ROBOT_TYPE
from scout_robot_bridge.core.robot_factory import create_robot
from scout_robot_bridge.core.teleop_controller import TeleopController
from scout_robot_bridge.core.teleop_utils import print_hud

# ── Tuning constants ────────────────────────────────────────────────────────
LINEAR_MAX   = 0.3          # m/s (mode 5)
ANGULAR_MAX  = 0.6          # rad/s (mode 5)
RAMP_UP_SEC  = 0.1          # seconds to reach full speed from zero (faster response)
RAMP_DN_SEC  = 0.15         # seconds to reach zero from full speed (quicker stop)
DECAY_ALPHA  = 0.85         # exponential decay per tick when no key held (0–1, higher = longer coast)
CONTROL_HZ   = 50           # timer frequency for velocity updates
SPEED_MODE_MIN = 1          # keys 1–5: 1 = slowest
SPEED_MODE_MAX = 5          # 5 = fastest
SPEED_MODE_DEFAULT = 3      # default speed mode on startup
# ────────────────────────────────────────────────────────────────────────────


class SmoothTeleop(Node):

    def __init__(self):
        super().__init__("smooth_teleop")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # Set up robot configuration
        self.declare_parameter('robot_type', DEFAULT_ROBOT_TYPE)
        robot_type = self.get_parameter('robot_type').value

        if robot_type == 'earth_rovers_sdk':
            ConfigManager.setup_frodobot_config(self)

        # Create robot instance
        self.robot = create_robot(robot_type)
        self._use_direct_control = self.robot is not None

        if self._use_direct_control:
            self.get_logger().info(f"Using direct robot control with {robot_type}")
            # Check if RTM client is available
            if hasattr(self.robot, '_rtm_client'):
                if self.robot._rtm_client is None:
                    self.get_logger().warning("RTM client not initialized - robot commands may not work. Check authentication.")
                else:
                    self.get_logger().info("RTM client initialized successfully")
            # Create teleop controller with robot instance
            self.controller = TeleopController(
                robot=self.robot,
                logger=self.get_logger(),
                linear_max=LINEAR_MAX,
                angular_max=ANGULAR_MAX,
                ramp_up_sec=RAMP_UP_SEC,
                ramp_dn_sec=RAMP_DN_SEC,
                decay_alpha=DECAY_ALPHA,
                control_hz=CONTROL_HZ,
            )
            self.get_logger().info("TeleopController created successfully")
        else:
            self.get_logger().warning(
                f"Robot creation failed for type '{robot_type}'. "
                "Falling back to ROS /cmd_vel publishing mode."
            )
            # Fallback: keep old velocity ramping logic
            self.cur_linear = 0.0
            self.cur_angular = 0.0
            dt = 1.0 / CONTROL_HZ
            self._up_step = LINEAR_MAX / (RAMP_UP_SEC * CONTROL_HZ)
            self._dn_step = LINEAR_MAX / (RAMP_DN_SEC * CONTROL_HZ)
            self._ang_up = ANGULAR_MAX / (RAMP_UP_SEC * CONTROL_HZ)
            self._ang_dn = ANGULAR_MAX / (RAMP_DN_SEC * CONTROL_HZ)

        # Which direction keys are held right now (set by keyboard listener, read by timer)
        self._lock = threading.Lock()
        self._held: set[str] = set()   # {"up", "down", "left", "right"}
        self._quit = threading.Event()

        # Speed mode 1–5 (1=slowest, 5=fastest); keys 1–5 set this, state persists
        self._speed_mode = SPEED_MODE_DEFAULT

        # Control loop timer (50 Hz)
        dt = 1.0 / CONTROL_HZ
        self.create_timer(dt, self._control_tick)

        # HUD display timer (10 Hz - slower to avoid terminal flicker)
        self.create_timer(0.1, self._hud_tick)

    def _get_speed_limits(self) -> tuple[float, float]:
        """Return (linear_max, angular_max) for current speed mode (1–5). Mode 5 = 100%."""
        scale = self._speed_mode / float(SPEED_MODE_MAX)
        return (LINEAR_MAX * scale, ANGULAR_MAX * scale)

    # ── Control loop (runs at CONTROL_HZ) ───────────────────────────────────

    def _control_tick(self):
        # Stop immediately if shutdown requested
        if self._quit.is_set():
            return
        
        with self._lock:
            held = set(self._held)  # snapshot

        linear_max_i, angular_max_i = self._get_speed_limits()

        # ── Compute target velocities from held keys (scaled by speed mode)
        target_linear  = 0.0
        target_angular = 0.0
        if "up"    in held: target_linear  += linear_max_i
        if "down"  in held: target_linear  -= linear_max_i
        if "right" in held: target_angular -= angular_max_i  # Right turn = negative angular (clockwise)
        if "left"  in held: target_angular += angular_max_i  # Left turn = positive angular (counter-clockwise)

        # ── Normalize diagonal movement to prevent faster diagonal speed
        # When both linear and angular are non-zero, apply normalization factor
        if abs(target_linear) > 0.01 and abs(target_angular) > 0.01:
            factor = 1.0 / (2.0 ** 0.5)  # 1/sqrt(2) ≈ 0.707
            target_linear *= factor
            target_angular *= factor

        if self._use_direct_control:
            # ── Use telemetry-aware controller
            self.controller.set_target_velocities(target_linear, target_angular)
            self.controller.tick()
            # Get current velocities for HUD display
            self.cur_linear, self.cur_angular = self.controller.get_current_velocities()
            # Publish to /cmd_vel so webrtc_node (and others) see speed for telemetry/UI
            msg = Twist()
            msg.linear.x = self.cur_linear
            msg.angular.z = self.cur_angular
            self.pub.publish(msg)
        else:
            # ── Fallback: ROS publishing mode (old behavior)
            # ── Ramp linear velocity toward target
            self.cur_linear = self._ramp(
                self.cur_linear, target_linear,
                self._up_step, self._dn_step
            )

            # ── Ramp angular velocity toward target
            self.cur_angular = self._ramp(
                self.cur_angular, target_angular,
                self._ang_up, self._ang_dn
            )

            # ── If no keys held, apply exponential decay for a natural coast-to-stop
            if not held:
                self.cur_linear  *= DECAY_ALPHA
                self.cur_angular *= DECAY_ALPHA
                # Snap to zero below threshold to prevent infinite coast
                if abs(self.cur_linear)  < 0.02: self.cur_linear  = 0.0
                if abs(self.cur_angular) < 0.02: self.cur_angular = 0.0

            # ── Publish to ROS topic
            msg = Twist()
            msg.linear.x  = self.cur_linear
            msg.angular.z = self.cur_angular
            self.pub.publish(msg)
        
        # Debug logging (reduce frequency to avoid spam)
        if len(held) > 0 or abs(self.cur_linear) > 0.01 or abs(self.cur_angular) > 0.01:
            is_diagonal = abs(target_linear) > 0.01 and abs(target_angular) > 0.01
            diagonal_note = " (diagonal)" if is_diagonal else ""
            self.get_logger().debug(
                f"Control tick: held={list(held)}{diagonal_note}, "
                f"target=({target_linear:.3f}, {target_angular:.3f}), "
                f"current=({self.cur_linear:.3f}, {self.cur_angular:.3f})"
            )

    def _hud_tick(self):
        """Update HUD display with telemetry (runs at 10 Hz)."""
        with self._lock:
            speed_mode = self._speed_mode
        if self._use_direct_control:
            telemetry = self.controller.get_last_telemetry()
            linear, angular = self.controller.get_current_velocities()
            print_hud(telemetry, linear, angular, speed_mode=speed_mode, speed_mode_max=SPEED_MODE_MAX)
        else:
            # Fallback: show basic info without telemetry
            print(
                f"\rROS mode: v={self.cur_linear:.2f} a={self.cur_angular:.2f} S{speed_mode}/{SPEED_MODE_MAX}    ",
                end="",
                flush=True,
            )

    @staticmethod
    def _ramp(current: float, target: float, up_step: float, dn_step: float) -> float:
        """
        Move current toward target by the appropriate step size.
        
        Used only in fallback ROS publishing mode.
        """
        diff = target - current
        if abs(diff) < 1e-9:
            return target
        # "up" = moving away from zero toward target; "dn" = decelerating
        moving_toward_zero = (current * target <= 0) or (abs(target) < abs(current))
        step = dn_step if moving_toward_zero else up_step
        if abs(diff) <= step:
            return target
        return current + step * (1 if diff > 0 else -1)

    def _trigger_immediate_tick(self, key_pressed=None):
        """
        Trigger immediate control tick for instant response.
        Can be called from keyboard library or terminal key reader.
        
        Args:
            key_pressed: The key that was pressed (or None if just updating state)
        """
        if not (self._use_direct_control and hasattr(self, 'controller')):
            return
        
        try:
            self.get_logger().info(f"_trigger_immediate_tick called (key_pressed={key_pressed})")
            # Calculate target velocities from currently held keys
            with self._lock:
                held_snapshot = set(self._held)
            
            self.get_logger().info(f"held_snapshot: {held_snapshot}")
            
            linear_max_i, angular_max_i = self._get_speed_limits()
            target_linear = 0.0
            target_angular = 0.0
            
            if "up" in held_snapshot:
                target_linear += linear_max_i
            if "down" in held_snapshot:
                target_linear -= linear_max_i
            if "right" in held_snapshot:
                target_angular -= angular_max_i
            if "left" in held_snapshot:
                target_angular += angular_max_i
            
            # Normalize diagonal
            if abs(target_linear) > 0.01 and abs(target_angular) > 0.01:
                factor = 1.0 / (2.0 ** 0.5)
                target_linear *= factor
                target_angular *= factor
            
            self.get_logger().info(f"Calculated targets: linear={target_linear:.3f}, angular={target_angular:.3f}")
            
            # Set target and update current velocities immediately
            self.controller.set_target_velocities(target_linear, target_angular)
            
            # Check if we're transitioning to diagonal movement (both dimensions non-zero)
            is_diagonal = abs(target_linear) > 0.001 and abs(target_angular) > 0.001
            was_moving_linear = abs(self.controller.cur_linear) > 0.01
            was_moving_angular = abs(self.controller.cur_angular) > 0.01
            
            # Force immediate kick by setting current velocity directly
            if abs(target_linear) > 0.001:
                if is_diagonal and was_moving_linear and not was_moving_angular:
                    # Transitioning from linear-only to diagonal: preserve existing linear velocity
                    # Don't modify it - let the controller ramp it toward the diagonal target
                    # This keeps the robot moving smoothly without stopping
                    self.get_logger().info(f"Preserving linear velocity for diagonal: {self.controller.cur_linear:.3f} (will ramp to {target_linear:.3f})")
                    # Don't modify cur_linear - keep it at current value
                else:
                    # Starting from zero or already diagonal: use normal kick
                    self.controller.cur_linear = target_linear * 0.7  # 70% kick
                    self.get_logger().info(f"Set cur_linear to {self.controller.cur_linear:.3f}")
            else:
                self.controller.cur_linear = 0.0  # Instant stop on key release
                self.get_logger().info("Set cur_linear to 0.0 (instant stop)")
            
            if abs(target_angular) > 0.001:
                if is_diagonal and was_moving_angular and not was_moving_linear:
                    # Transitioning from angular-only to diagonal: preserve existing angular velocity
                    # Don't modify it - let the controller ramp it toward the diagonal target
                    self.get_logger().info(f"Preserving angular velocity for diagonal: {self.controller.cur_angular:.3f} (will ramp to {target_angular:.3f})")
                    # Don't modify cur_angular - keep it at current value
                elif is_diagonal and not was_moving_angular:
                    # Adding angular to existing linear: kick-start angular immediately
                    self.controller.cur_angular = target_angular * 0.7  # 70% kick
                    self.get_logger().info(f"Kick-started angular for diagonal: {self.controller.cur_angular:.3f}")
                else:
                    # Starting from zero or already diagonal: use normal kick
                    self.controller.cur_angular = target_angular * 0.7  # 70% kick
                    self.get_logger().info(f"Set cur_angular to {self.controller.cur_angular:.3f}")
            else:
                self.controller.cur_angular = 0.0  # Instant stop on key release
                self.get_logger().info("Set cur_angular to 0.0 (instant stop)")
            
            # Send command immediately without calling tick() to avoid double updates
            # The periodic _control_tick will handle regular updates
            linear_normalized = self.controller.cur_linear / self.controller.linear_max if self.controller.linear_max > 0 else 0.0
            angular_normalized = self.controller.cur_angular / self.controller.angular_max if self.controller.angular_max > 0 else 0.0
            linear_normalized = max(-1.0, min(1.0, linear_normalized))
            angular_normalized = max(-1.0, min(1.0, angular_normalized))
            self.controller.robot.send_velocity(linear_normalized, angular_normalized)
            self.get_logger().info(f"Sent immediate velocity: linear={linear_normalized:.3f}, angular={angular_normalized:.3f}")
            # Publish to /cmd_vel so webrtc_node can show speed in UI telemetry
            msg = Twist()
            msg.linear.x = self.controller.cur_linear
            msg.angular.z = self.controller.cur_angular
            self.pub.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error in immediate tick: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())

    # ── Keyboard listener (keyboard library with key release events, fallback to terminal) ──────────────

    def run_keyboard_listener(self):
        """
        Start keyboard listener with proper key release detection.
        
        Tries keyboard library first (provides keydown/keyup events),
        falls back to terminal raw mode if not available.
        """
        self.get_logger().info(f"HAS_KEYBOARD_LIB={HAS_KEYBOARD_LIB}")
        if HAS_KEYBOARD_LIB:
            try:
                self.get_logger().info("Attempting to use keyboard library for key release detection")
                self._run_keyboard_lib_listener()
                return
            except Exception as e:
                self.get_logger().warning(f"keyboard library failed: {e}, falling back to terminal mode")
                import traceback
                self.get_logger().warning(traceback.format_exc())
        
        self.get_logger().info("Using terminal input for keyboard control (no key release events)")
        self._run_terminal_key_reader()

    def _run_keyboard_lib_listener(self):
        """
        Use keyboard library for proper keydown/keyup events.
        This provides real key release detection without timeouts.
        """
        key_map = {
            'up': 'up',
            'down': 'down',
            'left': 'left',
            'right': 'right',
        }
        
        def on_key_event(event):
            """Handle keydown/keyup events from keyboard library."""
            try:
                if event.event_type == keyboard.KEY_DOWN:
                    key_name = event.name.lower()
                    # Speed mode 1–5: persist in state, do not add to _held
                    if key_name in ("1", "2", "3", "4", "5"):
                        with self._lock:
                            self._speed_mode = int(key_name)
                        self.get_logger().info(f"Speed mode set to {self._speed_mode}/{SPEED_MODE_MAX}")
                        return
                    if key_name in key_map:
                        mapped_key = key_map[key_name]
                        with self._lock:
                            was_new = mapped_key not in self._held
                            self._held.add(mapped_key)
                        if was_new:
                            self.get_logger().info(f"Key pressed: {mapped_key}")
                            # Trigger immediate tick for instant response (outside lock to avoid deadlock)
                            self._trigger_immediate_tick(mapped_key)
                
                elif event.event_type == keyboard.KEY_UP:
                    key_name = event.name.lower()
                    if key_name in key_map:
                        mapped_key = key_map[key_name]
                        released = False
                        with self._lock:
                            if mapped_key in self._held:
                                self._held.discard(mapped_key)
                                released = True
                        if released:
                            self.get_logger().info(f"Key released: {mapped_key}")
                            # Immediately update when key is released (outside lock to avoid deadlock)
                            self._trigger_immediate_tick(None)
            except Exception as e:
                self.get_logger().error(f"Error in keyboard event handler: {e}")
        
        # Hook keyboard events
        keyboard.hook(on_key_event)
        self.get_logger().info("Keyboard library listener active. Press arrow keys to control robot.")
        
        # Wait until quit
        try:
            while not self._quit.is_set():
                time.sleep(0.1)
        finally:
            keyboard.unhook_all()
            self.get_logger().info("Keyboard library listener stopped")

    def _run_terminal_key_reader(self):
        """
        Terminal-based key reader.
        
        Reads arrow keys and tracks them with timeout-based release detection.
        Optimized for low latency - uses shorter timeouts and faster key detection.
        """
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        HELD_TIMEOUT = 0.3  # Timeout for key expiration - increased to handle multi-key input better
        last_seen: dict[str, float] = {}

        try:
            tty.setraw(fd)
            self.get_logger().info("Terminal key reader: terminal set to raw mode. Press arrow keys to control robot.")
            while not self._quit.is_set():
                try:
                    # Use very short timeout (1ms) for fastest response
                    ready = select.select([sys.stdin], [], [], 0.001)[0]
                    if not ready:
                        now = time.monotonic()
                        expired = []
                        with self._lock:
                            expired = [k for k, t in last_seen.items() if now - t > HELD_TIMEOUT]
                            if expired:
                                for k in expired:
                                    self._held.discard(k)
                                    del last_seen[k]
                        # Log and trigger immediate update when keys expire (released)
                        if expired:
                            for k in expired:
                                self.get_logger().info(f"Key released (timeout): {k} (held: {list(self._held)})")
                            # Immediately update velocity when keys are released
                            self._trigger_immediate_tick(None)
                        continue

                    ch = sys.stdin.read(1)
                except Exception as e:
                    self.get_logger().error(f"Error in key reader loop: {e}")
                    time.sleep(0.01)  # Shorter sleep on error
                    continue

                if ch in ("\x03", "\x04"):
                    self._quit.set()
                    break

                if ch in (" ", "s", "S"):
                    with self._lock:
                        cleared_keys = list(self._held)
                        self._held.clear()
                    last_seen.clear()
                    if cleared_keys:
                        self.get_logger().info(f"Keys released (stop): {cleared_keys}")
                        # Immediately stop when space/s is pressed
                        self._trigger_immediate_tick(None)
                    continue

                # Speed mode 1–5: persist in state
                if ch in ("1", "2", "3", "4", "5"):
                    with self._lock:
                        self._speed_mode = int(ch)
                    self.get_logger().info(f"Speed mode set to {self._speed_mode}/{SPEED_MODE_MAX}")
                    continue

                if ch == "\x1b":
                    now = time.monotonic()
                    
                    # Read arrow key sequence quickly - try to read all at once
                    # Arrow keys are ESC [ A/B/C/D - read remaining chars quickly
                    try:
                        # Read bracket and code with minimal delay
                        remaining = sys.stdin.read(2)  # Read both chars at once
                        if len(remaining) >= 2 and remaining[0] == "[":
                            code = remaining[1]
                            key_map = {"A": "up", "B": "down", "C": "right", "D": "left"}
                            key = key_map.get(code)
                            if key:
                                now = time.monotonic()
                                conflicting_key = None
                                conflicting_removed = False
                                num_keys_before = 0
                                with self._lock:
                                    num_keys_before = len(self._held)
                                    
                                    if key == "up":
                                        conflicting_key = "down"
                                    elif key == "down":
                                        conflicting_key = "up"
                                    elif key == "left":
                                        conflicting_key = "right"
                                    elif key == "right":
                                        conflicting_key = "left"
                                    
                                    if conflicting_key and conflicting_key in self._held:
                                        self._held.discard(conflicting_key)
                                        conflicting_removed = True
                                        if conflicting_key in last_seen:
                                            del last_seen[conflicting_key]
                                    
                                    # Refresh all held keys FIRST when processing ANY arrow key sequence
                                    # This is critical for multi-key input - when holding two keys, the terminal
                                    # may only send ESC sequences for one key, but we need to refresh BOTH
                                    refreshed_keys = []
                                    for held_key in list(self._held):
                                        last_seen[held_key] = now
                                        refreshed_keys.append(held_key)
                                    
                                    # Immediately add the key - no delay
                                    was_new = key not in self._held
                                    self._held.add(key)
                                    last_seen[key] = now
                                    num_keys_after = len(self._held)

                                # Log conflicting key release if it happened
                                if conflicting_removed:
                                    self.get_logger().info(f"Key released (conflicting): {conflicting_key}")

                                # Only trigger immediate tick if:
                                # 1. Key is new (was_new), OR
                                # 2. We're adding a second key for diagonal movement (num_keys_after > num_keys_before)
                                should_trigger = was_new or (num_keys_after > num_keys_before)
                                
                                if should_trigger:
                                    if was_new:
                                        self.get_logger().info(f"Key pressed: {key} (held: {list(self._held)})")
                                    else:
                                        self.get_logger().info(f"Key added for diagonal: {key} (held: {list(self._held)})")
                                    self._trigger_immediate_tick(key)
                                else:
                                    # Key repeat - still refresh all held keys to prevent expiration
                                    # Log at info level to verify keys are being refreshed during multi-key input
                                    self.get_logger().info(f"Key repeat: {key} - refreshed all held keys: {refreshed_keys} (held: {list(self._held)})")
                    except Exception as e:
                        # If reading fails, log the error instead of silently continuing
                        self.get_logger().error(f"Error reading arrow key sequence: {e}")
                        import traceback
                        self.get_logger().error(traceback.format_exc())
        except Exception as e:
            self.get_logger().error(f"Fatal error in terminal key reader: {e}")
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
            with self._lock:
                self._held.clear()
            self.get_logger().info("Terminal key reader exiting")


def main(args=None):
    rclpy.init(args=args)
    node = SmoothTeleop()

    if not sys.stdin.isatty():
        node.get_logger().error("stdin is not a TTY – run this in a real terminal")
        return

    node.get_logger().info(
        "Smooth teleop ready. Arrow keys to move, 1-5 speed mode, Space/s to stop, Ctrl+C to quit."
    )
    node.get_logger().info(
        f"Ramp up: {RAMP_UP_SEC}s  |  Ramp down: {RAMP_DN_SEC}s  |  "
        f"Max linear: {LINEAR_MAX} m/s  |  Max angular: {ANGULAR_MAX} rad/s (keys 1-5 scale speed)"
    )

    keyboard_thread = threading.Thread(
        target=node.run_keyboard_listener, daemon=True, name="keyboard_listener"
    )
    keyboard_thread.start()
    node.get_logger().info(f"Keyboard listener thread started (alive={keyboard_thread.is_alive()})")
    
    # Give thread a moment to initialize
    time.sleep(0.1)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("Shutting down teleop node...")
        node._quit.set()
        # Stop robot - explicitly zero velocities first
        if node._use_direct_control and node.robot:
            # Zero out controller velocities
            if hasattr(node, 'controller') and node.controller:
                node.controller.cur_linear = 0.0
                node.controller.cur_angular = 0.0
                # Send zero velocity command explicitly
                node.controller.robot.send_velocity(0.0, 0.0)
                node.get_logger().info("Sent zero velocity command to robot")
            # Also call stop() as backup
            node.robot.stop()
            if hasattr(node.robot, 'cleanup'):
                node.robot.cleanup()
        else:
            # Fallback: publish zero velocity to ROS topic
            msg = Twist()
            node.pub.publish(msg)
        node.destroy_node()
        rclpy.shutdown()
        node.get_logger().info("Teleop node shutdown complete")


if __name__ == "__main__":
    main()
