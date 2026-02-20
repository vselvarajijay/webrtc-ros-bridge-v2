#!/usr/bin/env python3
"""
Wander node: optical-flow-only wandering and navigation.

Core principle: flow magnitude ∝ 1/distance.
- Steer continuously toward the region with LOWEST flow (= furthest away = most open).
- Slow down proportionally as center flow increases (wall approaching).
- No binary obstacle thresholds. No dead zones. Pure gradient following.

Requires optical_flow_node (publishing /optical_flow).
Subscribes to /autonomy/command ("wander" -> enable, "stop" -> disable) and /optical_flow.
Publishes /cmd_vel.
"""

import random
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32MultiArray

from bunny_controller.constants import (
    CMD_VEL_TOPIC,
    AUTONOMY_COMMAND_TOPIC,
    DEFAULT_MAX_LINEAR_SPEED,
    DEFAULT_MAX_ANGULAR_SPEED,
)

OPTICAL_FLOW_TOPIC = "/optical_flow"

# Enhanced Float32MultiArray layout (18 elements):
# [vx_left_top, vy_left_top, mag_left_top, vx_center_top, vy_center_top, mag_center_top, vx_right_top, vy_right_top, mag_right_top,
#  vx_left_mid, vy_left_mid, mag_left_mid, vx_center_mid, vy_center_mid, mag_center_mid, vx_right_mid, vy_right_mid, mag_right_mid]
FLOW_VX_LEFT_TOP,    FLOW_VY_LEFT_TOP,    FLOW_MAG_LEFT_TOP    = 0,  1,  2
FLOW_VX_CENTER_TOP,  FLOW_VY_CENTER_TOP,  FLOW_MAG_CENTER_TOP  = 3,  4,  5
FLOW_VX_RIGHT_TOP,   FLOW_VY_RIGHT_TOP,   FLOW_MAG_RIGHT_TOP   = 6,  7,  8
FLOW_VX_LEFT_MID,    FLOW_VY_LEFT_MID,    FLOW_MAG_LEFT_MID    = 9,  10, 11
FLOW_VX_CENTER_MID,  FLOW_VY_CENTER_MID,  FLOW_MAG_CENTER_MID  = 12, 13, 14
FLOW_VX_RIGHT_MID,   FLOW_VY_RIGHT_MID,   FLOW_MAG_RIGHT_MID   = 15, 16, 17

# Legacy (9-element) indices
FLOW_VX_LEFT,   FLOW_VY_LEFT,   FLOW_MAG_LEFT   = 0, 1, 2
FLOW_VX_CENTER, FLOW_VY_CENTER, FLOW_MAG_CENTER = 3, 4, 5
FLOW_VX_RIGHT,  FLOW_VY_RIGHT,  FLOW_MAG_RIGHT  = 6, 7, 8

DEFAULT_CONTROL_HZ = 25.0
DEFAULT_WANDER_LINEAR = 0.25

# --- Core steering ---
# Gain on (mag_right - mag_left): how strongly to steer toward the open side.
# At 0.25 m/s with a 10 px/s asymmetry -> angular = 10 * 0.12 = 1.2 rad/s (sharp turn).
# Tune this first. Increase if robot doesn't turn enough; decrease if it oscillates.
DEFAULT_FLOW_ANGULAR_GAIN = 0.12  # Increased from 0.07 - turn much faster when asymmetry detected

# Hard cap on angular velocity
DEFAULT_MAX_FLOW_ANGULAR = 1.0  # Increased from 0.6 - allow sharper turns

# --- Speed scaling ---
# Center flow at which the robot slows to min_linear_frac of wander speed.
# Set to typical "close wall" flow value in your environment (px/s).
# Reduced to start slowing earlier
DEFAULT_FLOW_SCALE_MAX = 10.0  # Reduced from 15.0 - start slowing earlier

# Minimum forward speed fraction (so we always creep forward, never just spin)
DEFAULT_MIN_LINEAR_FRAC = 0.15

# When center flow is THIS fraction of FLOW_SCALE_MAX, start slowing down (0-1).
# 0.25 = start slowing at 25% of max, so there's early warning for 45-degree approaches.
DEFAULT_SLOWDOWN_START_FRAC = 0.25  # Reduced from 0.4 - slow down even earlier

# --- Temporal ---
DEFAULT_FLOW_TIMEOUT_S = 0.5
DEFAULT_FLOW_SMOOTHING_ALPHA = 0.25   # EMA on incoming flow (0=heavy smooth, 1=none)
DEFAULT_ANGULAR_DAMPING_ALPHA = 0.05  # Reduced from 0.15 - respond almost immediately
                                       # Keep very low so turns happen instantly

# --- Dead zone for steering ---
# Ignore small asymmetries to prevent noise-induced spinning
# Asymmetry below this threshold (px/s) produces no steering command
DEFAULT_FLOW_DEAD_ZONE = 2.0  # px/s - prevents spinning from noise

# --- Band selection ---
# False = mid band (rows ~28%-50%), True = top band (rows ~10%-28%)
# Mid band is better for ground-level columns/furniture.
# Top band can be better if camera is very low and floor dominates mid band.
DEFAULT_USE_TOP_BAND = False

# --- Rotation guard ---
# Ignore flow input while robot is actively turning (rotation-induced flow is noise)
# Increased threshold to prevent getting stuck in rotation guard state
DEFAULT_ROTATION_THRESHOLD = 0.3  # Increased from 0.15 rad/s - only ignore flow during fast spins

# --- Random nudge ---
# Small random angular component to break symmetry in open uniform spaces.
DEFAULT_RANDOM_NUDGE = 0.025

# --- Flow steering swap ---
DEFAULT_FLOW_STEERING_SWAP = False


class WanderNode(Node):
    def __init__(self):
        super().__init__("wander_node")
        self._lock = threading.Lock()
        self._enabled = False
        self._wander_linear_speed: float = 0.0
        self._last_flow: list[float] | None = None
        self._last_flow_time_ns: int | None = None
        self._flow_missing_logged = False
        self._smoothed_flow: list[float] | None = None
        self._last_linear: float = 0.0
        self._last_angular: float = 0.0

        self.declare_parameter("max_linear_speed", DEFAULT_MAX_LINEAR_SPEED)
        self.declare_parameter("max_angular_speed", DEFAULT_MAX_ANGULAR_SPEED)
        self.declare_parameter("control_hz", DEFAULT_CONTROL_HZ)
        self.declare_parameter("wander_linear_speed", DEFAULT_WANDER_LINEAR)
        self.declare_parameter("flow_angular_gain", DEFAULT_FLOW_ANGULAR_GAIN)
        self.declare_parameter("max_flow_angular", DEFAULT_MAX_FLOW_ANGULAR)
        self.declare_parameter("flow_scale_max", DEFAULT_FLOW_SCALE_MAX)
        self.declare_parameter("min_linear_frac", DEFAULT_MIN_LINEAR_FRAC)
        self.declare_parameter("slowdown_start_frac", DEFAULT_SLOWDOWN_START_FRAC)
        self.declare_parameter("flow_timeout_s", DEFAULT_FLOW_TIMEOUT_S)
        self.declare_parameter("flow_smoothing_alpha", DEFAULT_FLOW_SMOOTHING_ALPHA)
        self.declare_parameter("angular_damping_alpha", DEFAULT_ANGULAR_DAMPING_ALPHA)
        self.declare_parameter("use_top_band", DEFAULT_USE_TOP_BAND)
        self.declare_parameter("rotation_threshold", DEFAULT_ROTATION_THRESHOLD)
        self.declare_parameter("random_nudge", DEFAULT_RANDOM_NUDGE)
        self.declare_parameter("flow_steering_swap", DEFAULT_FLOW_STEERING_SWAP)
        self.declare_parameter("flow_dead_zone", DEFAULT_FLOW_DEAD_ZONE)

        self._cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.create_subscription(String, AUTONOMY_COMMAND_TOPIC, self._on_autonomy_command, 10)
        self.create_subscription(Float32MultiArray, OPTICAL_FLOW_TOPIC, self._on_optical_flow, 10)

        rate = self.get_parameter("control_hz").value
        self._control_timer = self.create_timer(1.0 / rate, self._control_tick)

        self._wander_linear_speed = min(
            self.get_parameter("wander_linear_speed").value,
            self.get_parameter("max_linear_speed").value,
        )
        self.get_logger().info(
            "wander_node: pure flow-gradient steering. sub %s, %s; pub %s; %.1f Hz"
            % (AUTONOMY_COMMAND_TOPIC, OPTICAL_FLOW_TOPIC, CMD_VEL_TOPIC, rate)
        )

    def _on_autonomy_command(self, msg: String) -> None:
        raw = (msg.data or "").strip()
        raw_lower = raw.lower()
        with self._lock:
            if raw_lower == "stop":
                self._enabled = False
                self.get_logger().info("Wander disabled")
            elif raw_lower == "wander" or raw_lower.startswith("wander "):
                self._enabled = True
                rest = raw[len("wander"):].strip()
                if rest:
                    try:
                        speed = float(rest)
                        max_linear = self.get_parameter("max_linear_speed").value
                        self._wander_linear_speed = max(0.0, min(max_linear, speed))
                        self.get_logger().info("Wander enabled at %.2f m/s" % self._wander_linear_speed)
                    except ValueError:
                        self.get_logger().warn("Wander: invalid speed %r, using current" % rest)
                        self.get_logger().info("Wander enabled")
                else:
                    self.get_logger().info("Wander enabled")

    def _on_optical_flow(self, msg: Float32MultiArray) -> None:
        if len(msg.data) < 9:
            return
        alpha = self.get_parameter("flow_smoothing_alpha").value
        raw = list(msg.data[:min(len(msg.data), 18)])
        with self._lock:
            if self._smoothed_flow is None or len(self._smoothed_flow) != len(raw):
                self._smoothed_flow = raw.copy()
            else:
                for i in range(len(raw)):
                    self._smoothed_flow[i] = alpha * raw[i] + (1.0 - alpha) * self._smoothed_flow[i]
            self._last_flow = self._smoothed_flow.copy()
            self._last_flow_time_ns = self.get_clock().now().nanoseconds
            self._flow_missing_logged = False

    def _control_tick(self) -> None:
        with self._lock:
            enabled = self._enabled

        twist = Twist()
        if not enabled:
            self._cmd_pub.publish(twist)
            return

        max_linear  = self.get_parameter("max_linear_speed").value
        max_angular = self.get_parameter("max_angular_speed").value
        with self._lock:
            wander_linear = min(self._wander_linear_speed, max_linear)
            flow_time_ns  = self._last_flow_time_ns

        flow_timeout_s = self.get_parameter("flow_timeout_s").value
        now_ns = self.get_clock().now().nanoseconds
        flow_recent = (
            flow_time_ns is not None
            and (now_ns - flow_time_ns) <= flow_timeout_s * 1e9
        )

        if not flow_recent:
            if not self._flow_missing_logged:
                with self._lock:
                    self._flow_missing_logged = True
                self.get_logger().warn("Wander: no recent optical flow; stopping.")
            self._cmd_pub.publish(twist)
            return

        with self._lock:
            flow = self._last_flow
            last_angular_cmd = self._last_angular

        # --- Extract flow values for the chosen band ---
        use_top_band = self.get_parameter("use_top_band").value
        use_enhanced = len(flow) >= 18

        if use_enhanced:
            if use_top_band:
                mag_left   = flow[FLOW_MAG_LEFT_TOP]
                mag_center = flow[FLOW_MAG_CENTER_TOP]
                mag_right  = flow[FLOW_MAG_RIGHT_TOP]
            else:
                mag_left   = flow[FLOW_MAG_LEFT_MID]
                mag_center = flow[FLOW_MAG_CENTER_MID]
                mag_right  = flow[FLOW_MAG_RIGHT_MID]
        else:
            mag_left   = flow[FLOW_MAG_LEFT]
            mag_center = flow[FLOW_MAG_CENTER]
            mag_right  = flow[FLOW_MAG_RIGHT]

        # --- CORE: steer toward lowest flow = longest distance ---
        #
        # mag_right - mag_left:
        #   positive -> right side has more flow (closer) -> turn LEFT (+angular)
        #   negative -> left side has more flow (closer)  -> turn RIGHT (-angular)
        #
        flow_gain       = self.get_parameter("flow_angular_gain").value
        max_flow_ang    = self.get_parameter("max_flow_angular").value
        steering_swap   = self.get_parameter("flow_steering_swap").value
        random_nudge    = self.get_parameter("random_nudge").value
        rotation_thresh = self.get_parameter("rotation_threshold").value
        flow_dead_zone  = self.get_parameter("flow_dead_zone").value

        asymmetry = mag_right - mag_left  # positive = right closer = turn left
        
        # Apply dead zone to prevent noise-induced spinning
        if abs(asymmetry) < flow_dead_zone:
            asymmetry = 0.0
        
        is_rotating = abs(last_angular_cmd) > rotation_thresh

        if is_rotating:
            # During fast rotation, reduce steering input but don't completely ignore it
            # This prevents getting stuck in a spin state
            raw_angular = asymmetry * flow_gain * 0.3  # Reduced but not zero
            raw_angular = max(-max_flow_ang, min(max_flow_ang, raw_angular))
        else:
            # Normal steering: full gain
            raw_angular = asymmetry * flow_gain
            raw_angular = max(-max_flow_ang, min(max_flow_ang, raw_angular))
            raw_angular += (random.random() - 0.5) * random_nudge

        if steering_swap:
            raw_angular = -raw_angular

        # --- Speed: slow down based on worst-case proximity from any direction ---
        #
        # Use max of center, left*0.7, right*0.7 to catch 45-degree approaches.
        # Side flow is weighted 0.7 because it's expected to be higher even in open corridors.
        # Linear interpolation:
        #   mag_sensor <= slowdown_start -> full wander speed
        #   mag_sensor >= flow_scale_max -> min_linear_frac * wander speed
        #
        flow_scale_max     = self.get_parameter("flow_scale_max").value
        min_linear_frac    = self.get_parameter("min_linear_frac").value
        slowdown_start_frac = self.get_parameter("slowdown_start_frac").value

        # Side-flow-based slowdown: use worst-case proximity from any direction
        # This catches 45-degree approaches where side flow is high but center flow is low
        mag_sensor = max(mag_center, mag_left * 0.7, mag_right * 0.7)
        
        slowdown_start = flow_scale_max * slowdown_start_frac
        if mag_sensor <= slowdown_start:
            speed_frac = 1.0
        elif mag_sensor >= flow_scale_max:
            speed_frac = min_linear_frac
        else:
            t = (mag_sensor - slowdown_start) / (flow_scale_max - slowdown_start + 1e-6)
            speed_frac = 1.0 - t * (1.0 - min_linear_frac)

        linear = wander_linear * speed_frac
        linear = max(wander_linear * min_linear_frac, min(wander_linear, linear))

        # --- Angular damping (EMA to smooth output, not to delay it) ---
        angular_damping = self.get_parameter("angular_damping_alpha").value
        with self._lock:
            prev_angular = self._last_angular
        angular = angular_damping * prev_angular + (1.0 - angular_damping) * raw_angular
        angular = max(-max_angular, min(max_angular, angular))
        linear  = max(0.0, min(max_linear, linear))

        # --- Debug log every ~2s (at 25Hz that's every 50 ticks) ---
        if not hasattr(self, "_debug_tick"):
            self._debug_tick = 0
        self._debug_tick += 1
        if self._debug_tick % 50 == 0:
            mag_sensor = max(mag_center, mag_left * 0.7, mag_right * 0.7)
            self.get_logger().info(
                "flow L=%.1f C=%.1f R=%.1f | sensor=%.1f asym=%.1f ang=%.2f lin=%.2f"
                % (mag_left, mag_center, mag_right, mag_sensor,
                   mag_right - mag_left, angular, linear)
            )

        twist.linear.x  = linear
        twist.angular.z = angular

        with self._lock:
            self._last_linear  = linear
            self._last_angular = angular

        self._cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = WanderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()