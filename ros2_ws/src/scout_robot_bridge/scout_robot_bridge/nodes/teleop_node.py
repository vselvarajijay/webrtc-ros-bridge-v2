#!/usr/bin/env python3
"""
Smooth arrow-key teleop: publishes Twist to /cmd_vel with velocity ramping.

Improvements over naive version:
  - Velocity ramps up/down over RAMP_TIME instead of jumping to max speed
  - Key state is tracked by a dedicated thread using evdev-style raw reads,
    NOT by timestamping queue entries, eliminating the OS key-repeat race condition
  - A single high-frequency timer drives all velocity updates (50 Hz)
  - Stopping is exponential decay (feels natural) rather than instant zeroing
"""

import sys
import termios
import threading
import time
import tty
import select
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

# ── Tuning constants ────────────────────────────────────────────────────────
LINEAR_MAX   = 0.3          # m/s
ANGULAR_MAX  = 0.3          # rad/s
RAMP_UP_SEC  = 0.25         # seconds to reach full speed from zero
RAMP_DN_SEC  = 0.15         # seconds to reach zero from full speed (quicker stop)
DECAY_ALPHA  = 0.85         # exponential decay per tick when no key held (0–1, higher = longer coast)
CONTROL_HZ   = 50           # timer frequency for velocity updates
# ────────────────────────────────────────────────────────────────────────────


class SmoothTeleop(Node):

    def __init__(self):
        super().__init__("smooth_teleop")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # Current output velocities (what we're actually publishing)
        self.cur_linear  = 0.0
        self.cur_angular = 0.0

        # Which direction keys are held right now (set by reader thread, read by timer)
        self._lock = threading.Lock()
        self._held: set[str] = set()   # {"up", "down", "left", "right"}
        self._quit = threading.Event()

        # Per-tick ramp increments
        dt = 1.0 / CONTROL_HZ
        self._up_step = LINEAR_MAX  / (RAMP_UP_SEC * CONTROL_HZ)
        self._dn_step = LINEAR_MAX  / (RAMP_DN_SEC * CONTROL_HZ)
        self._ang_up  = ANGULAR_MAX / (RAMP_UP_SEC * CONTROL_HZ)
        self._ang_dn  = ANGULAR_MAX / (RAMP_DN_SEC * CONTROL_HZ)

        self.create_timer(dt, self._control_tick)

    # ── Control loop (runs at CONTROL_HZ) ───────────────────────────────────

    def _control_tick(self):
        with self._lock:
            held = set(self._held)  # snapshot

        # ── Compute target velocities from held keys
        target_linear  = 0.0
        target_angular = 0.0
        if "up"    in held: target_linear  += LINEAR_MAX
        if "down"  in held: target_linear  -= LINEAR_MAX
        if "right" in held: target_angular += ANGULAR_MAX
        if "left"  in held: target_angular -= ANGULAR_MAX

        # ── Normalize diagonal movement to prevent faster diagonal speed
        # When both linear and angular are non-zero, apply normalization factor
        if abs(target_linear) > 0.01 and abs(target_angular) > 0.01:
            factor = 1.0 / (2.0 ** 0.5)  # 1/sqrt(2) ≈ 0.707
            target_linear *= factor
            target_angular *= factor

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
            # Snap to zero below noise floor to stop publishing tiny commands
            if abs(self.cur_linear)  < 0.001: self.cur_linear  = 0.0
            if abs(self.cur_angular) < 0.001: self.cur_angular = 0.0

        # ── Publish
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

    @staticmethod
    def _ramp(current: float, target: float, up_step: float, dn_step: float) -> float:
        """Move current toward target by the appropriate step size."""
        diff = target - current
        if abs(diff) < 1e-9:
            return target
        # "up" = moving away from zero toward target; "dn" = decelerating
        moving_toward_zero = (current * target <= 0) or (abs(target) < abs(current))
        step = dn_step if moving_toward_zero else up_step
        if abs(diff) <= step:
            return target
        return current + step * (1 if diff > 0 else -1)

    # ── Key reader (runs in dedicated thread) ─────────────────────────────

    def run_key_reader(self):
        """
        Reads raw keypresses. Arrow down → add to held set.
        Arrow up is inferred: if a key hasn't been seen within ~80ms it's removed.
        (True key-up events aren't available via termios; timeout approximates it.)
        The per-key timestamp approach is correct here because it runs in its OWN
        thread at a high poll rate, not racing against a slow 100ms select timeout.
        """
        fd   = sys.stdin.fileno()
        old  = termios.tcgetattr(fd)
        HELD_TIMEOUT = 0.25   # key expires after 250ms without being refreshed (increased for better multi-key handling)

        last_seen: dict[str, float] = {}  # key -> time.monotonic()

        try:
            tty.setraw(fd)
            self.get_logger().info("Key reader thread: terminal set to raw mode")
            while not self._quit.is_set():
                try:
                    # ── Poll for new input (short timeout = fast key-release detection)
                    ready = select.select([sys.stdin], [], [], 0.02)[0]
                    if not ready:
                        # No input available - check for expired keys
                        now = time.monotonic()
                        with self._lock:
                            # Check expiration while holding lock to avoid race conditions
                            expired = [k for k, t in last_seen.items() if now - t > HELD_TIMEOUT]
                            if expired:
                                for k in expired:
                                    self._held.discard(k)
                                    del last_seen[k]
                                self.get_logger().debug(f"Keys expired: {expired}, remaining: {list(self._held)}")
                        continue

                    ch = sys.stdin.read(1)
                    self.get_logger().debug(f"Key reader: read char {repr(ch)}")
                except Exception as e:
                    self.get_logger().error(f"Error in key reader loop: {e}")
                    import traceback
                    self.get_logger().error(traceback.format_exc())
                    time.sleep(0.1)  # Brief pause before retrying
                    continue

                # Ctrl-C / Ctrl-D
                if ch in ("\x03", "\x04"):
                    self._quit.set()
                    break

                # Space / s = stop: clear all held keys immediately
                if ch in (" ", "s", "S"):
                    with self._lock:
                        self._held.clear()
                    last_seen.clear()
                    self.get_logger().info("STOP key pressed")
                    continue

                # Arrow key escape sequence: ESC [ A/B/C/D
                if ch == "\x1b":
                    # Refresh ALL held keys immediately when we detect ESC - this prevents expiration
                    # while reading the escape sequence. If user is actively pressing keys, all held
                    # keys should be considered "fresh" since we're actively reading input.
                    now = time.monotonic()
                    with self._lock:
                        # Refresh ALL currently held keys - ensure they all have timestamps
                        for held_key in list(self._held):  # Use list() to avoid modification during iteration
                            last_seen[held_key] = now
                    
                    # Wait a bit longer for the rest of the sequence
                    if not select.select([sys.stdin], [], [], 0.05)[0]:
                        self.get_logger().debug("ESC detected but no follow-up chars")
                        continue
                    bracket = sys.stdin.read(1)
                    if bracket != "[":
                        self.get_logger().debug(f"ESC followed by {repr(bracket)}, not '['")
                        continue
                    # Wait for the direction code
                    if not select.select([sys.stdin], [], [], 0.05)[0]:
                        self.get_logger().debug("ESC [ detected but no direction code")
                        continue
                    code = sys.stdin.read(1)
                    key_map = {"A": "up", "B": "down", "C": "right", "D": "left"}
                    key = key_map.get(code)
                    if key:
                        # Refresh timestamps AGAIN right before adding new key to ensure no keys expired
                        # during escape sequence reading (which can take ~0.1-0.15s)
                        now = time.monotonic()
                        with self._lock:
                            # FIRST: Remove conflicting keys BEFORE refreshing timestamps
                            # up/down and left/right are mutually exclusive
                            conflicting_key = None
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
                                if conflicting_key in last_seen:
                                    del last_seen[conflicting_key]
                                self.get_logger().debug(f"Removed conflicting key: {conflicting_key} (pressed: {key})")
                            
                            # SECOND: Refresh timestamps for all REMAINING keys (non-conflicting ones)
                            for held_key in list(self._held):
                                last_seen[held_key] = now
                            
                            # THIRD: Add the new key (or refresh if already present)
                            was_already_held = key in self._held
                            self._held.add(key)  # add() is idempotent for sets
                            last_seen[key] = now
                            
                            # Log the held keys (already holding lock from above)
                            held_snapshot = list(self._held)
                            if was_already_held:
                                self.get_logger().debug(f"Arrow key repeat: {key} (held: {held_snapshot})")
                            else:
                                self.get_logger().info(f"Arrow key detected: {key} (held: {held_snapshot})")
                    else:
                        self.get_logger().debug(f"Unknown arrow code: {repr(code)}")

        except Exception as e:
            self.get_logger().error(f"Fatal error in key reader thread: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
            # Ensure robot stops on exit
            with self._lock:
                self._held.clear()
            self.get_logger().info("Key reader thread exiting")


def main(args=None):
    rclpy.init(args=args)
    node = SmoothTeleop()

    if not sys.stdin.isatty():
        node.get_logger().error("stdin is not a TTY – run this in a real terminal")
        return

    node.get_logger().info(
        "Smooth teleop ready. Arrow keys to move, Space/s to stop, Ctrl+C to quit."
    )
    node.get_logger().info(
        f"Ramp up: {RAMP_UP_SEC}s  |  Ramp down: {RAMP_DN_SEC}s  |  "
        f"Max linear: {LINEAR_MAX} m/s  |  Max angular: {ANGULAR_MAX} rad/s"
    )

    reader_thread = threading.Thread(
        target=node.run_key_reader, daemon=True, name="key_reader"
    )
    reader_thread.start()
    node.get_logger().info(f"Key reader thread started (alive={reader_thread.is_alive()})")
    
    # Give thread a moment to initialize
    time.sleep(0.1)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._quit.set()
        msg = Twist()
        node.pub.publish(msg)   # zero-velocity stop
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
