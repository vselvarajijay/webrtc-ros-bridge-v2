#!/usr/bin/env python3
"""
Wander planner: converts navigation state into velocity commands.

Subscribes to /navigation_state and /autonomy/command.
Publishes to /cmd_vel when wander is enabled (UI "Start wandering"), and to /cmd_vel_target.
When "Stop wandering" is clicked, publishes zero to /cmd_vel so the robot stops.
"""

import random

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from connectx_msgs.msg import NavigationState

from connectx_planner.constants import (
    CMD_VEL_TOPIC,
    CMD_VEL_TARGET_TOPIC,
    NAVIGATION_STATE_TOPIC,
    AUTONOMY_COMMAND_TOPIC,
)

DEFAULT_FORWARD_SPEED = 0.25
DEFAULT_BASE_TURN_SPEED = 0.6
DEFAULT_LOW_CONFIDENCE_ANGULAR = 0.3
DEFAULT_WANDER_BIAS_STEP = 0.02
DEFAULT_WANDER_BIAS_LIMIT = 0.2
DEFAULT_TICK_HZ = 25.0
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_HYSTERESIS_URGENCY_CLEAR = 0.9
DEFAULT_TURN_TIMEOUT_FRAMES = 75  # ~3 s at 25 Hz
DEFAULT_CREEP_SPEED = 0.05
DEFAULT_ESCAPE_PULSE_FRAMES = 8


def compute_wander_twist(
    state: NavigationState,
    was_forward_safe: bool,
    turning_frames: int,
    escape_pulse_remaining: int,
    wander_bias: float,
    forward_speed: float,
    base_turn_speed: float,
    low_confidence_angular: float,
    confidence_threshold: float,
    hysteresis_urgency_clear: float,
    turn_timeout_frames: int,
    creep_speed: float,
    escape_pulse_frames: int,
    wander_bias_limit: float,
) -> tuple[float, float, bool, int, int]:
    """Compute twist (linear_x, angular_z) and next internal state from current state.
    Returns (linear_x, angular_z, next_was_forward_safe, next_turning_frames, next_escape_pulse_remaining).
    Pure function for testing and use by WanderPlanner._tick (wander_bias is updated by caller with random)."""
    if state.confidence < confidence_threshold:
        return (
            0.0,
            low_confidence_angular,
            was_forward_safe,
            0,
            0,
        )

    if escape_pulse_remaining > 0:
        next_remaining = escape_pulse_remaining - 1
        next_turning = 0 if next_remaining == 0 else turning_frames
        return (creep_speed, 0.0, was_forward_safe, next_turning, next_remaining)

    next_was = was_forward_safe
    next_turning = turning_frames
    if state.forward_safe:
        next_was = True
        next_turning = 0
    elif state.urgency_score > hysteresis_urgency_clear:
        next_was = False

    forward_allowed = next_was

    if forward_allowed:
        clamped_bias = max(
            -wander_bias_limit,
            min(wander_bias_limit, wander_bias),
        )
        return (forward_speed, clamped_bias, next_was, 0, 0)

    next_turning = turning_frames + 1
    if next_turning >= turn_timeout_frames:
        return (creep_speed, 0.0, next_was, next_turning, escape_pulse_frames)
    turn_dir = float(state.safest_turn)
    urgency = max(0.0, min(1.0, state.urgency_score))
    angular = turn_dir * (base_turn_speed * (0.5 + urgency))
    return (creep_speed, angular, next_was, next_turning, 0)


class WanderPlanner(Node):
    def __init__(self):
        super().__init__("wander_planner")

        self._last_state: NavigationState | None = None
        self._was_forward_safe = True
        self._wander_bias = 0.0
        self._turning_frames = 0
        self._escape_pulse_remaining = 0
        self._debug_tick = 0
        self._wander_enabled = False
        self._stop_sent_count = 0  # publish zero this many ticks after "stop" then leave /cmd_vel to others
        self._no_state_warn_count = 0

        self.declare_parameter("forward_speed", DEFAULT_FORWARD_SPEED)
        self.declare_parameter("base_turn_speed", DEFAULT_BASE_TURN_SPEED)
        self.declare_parameter("low_confidence_angular", DEFAULT_LOW_CONFIDENCE_ANGULAR)
        self.declare_parameter("wander_bias_step", DEFAULT_WANDER_BIAS_STEP)
        self.declare_parameter("wander_bias_limit", DEFAULT_WANDER_BIAS_LIMIT)
        self.declare_parameter("tick_hz", DEFAULT_TICK_HZ)
        self.declare_parameter("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        self.declare_parameter(
            "hysteresis_urgency_clear", DEFAULT_HYSTERESIS_URGENCY_CLEAR
        )
        self.declare_parameter("turn_timeout_frames", DEFAULT_TURN_TIMEOUT_FRAMES)
        self.declare_parameter("creep_speed", DEFAULT_CREEP_SPEED)
        self.declare_parameter("escape_pulse_frames", DEFAULT_ESCAPE_PULSE_FRAMES)
        self.declare_parameter("debug_log_interval", 50)  # log every N ticks (~2 s at 25 Hz)

        self._forward_speed = self.get_parameter("forward_speed").value
        self._base_turn_speed = self.get_parameter("base_turn_speed").value
        self._low_conf_angular = self.get_parameter("low_confidence_angular").value
        self._wander_bias_step = self.get_parameter("wander_bias_step").value
        self._wander_bias_limit = self.get_parameter("wander_bias_limit").value
        self._confidence_threshold = self.get_parameter("confidence_threshold").value
        self._hysteresis_urgency_clear = self.get_parameter(
            "hysteresis_urgency_clear"
        ).value
        self._turn_timeout_frames = self.get_parameter("turn_timeout_frames").value
        self._creep_speed = self.get_parameter("creep_speed").value
        self._escape_pulse_frames = self.get_parameter("escape_pulse_frames").value
        self._debug_log_interval = self.get_parameter("debug_log_interval").value

        self.create_subscription(
            NavigationState,
            NAVIGATION_STATE_TOPIC,
            self._on_state,
            10,
        )
        self.create_subscription(
            String,
            AUTONOMY_COMMAND_TOPIC,
            self._on_autonomy_command,
            10,
        )

        self._cmd_target_pub = self.create_publisher(
            Twist,
            CMD_VEL_TARGET_TOPIC,
            10,
        )
        self._cmd_vel_pub = self.create_publisher(
            Twist,
            CMD_VEL_TOPIC,
            10,
        )

        period = 1.0 / self.get_parameter("tick_hz").value
        self.create_timer(period, self._tick)

        self.get_logger().info(
            "wander_planner: sub %s, %s; pub %s, %s; %.1f Hz"
            % (
                NAVIGATION_STATE_TOPIC,
                AUTONOMY_COMMAND_TOPIC,
                CMD_VEL_TARGET_TOPIC,
                CMD_VEL_TOPIC,
                1.0 / period,
            )
        )

    def _on_autonomy_command(self, msg: String) -> None:
        raw = (msg.data or "").strip().lower()
        if raw == "stop":
            self._wander_enabled = False
            self._stop_sent_count = 25  # ~1 s at 25 Hz so robot stops, then yield /cmd_vel to manual/controller
            self.get_logger().info("Wander disabled (stop)")
        elif raw == "wander" or raw.startswith("wander "):
            self._wander_enabled = True
            self._stop_sent_count = 0
            self.get_logger().info("Wander enabled")

    def _on_state(self, msg: NavigationState) -> None:
        self._last_state = msg
        self._no_state_warn_count = 0

    def _tick(self) -> None:
        if not self._wander_enabled:
            if self._stop_sent_count > 0:
                zero = Twist()
                zero.linear.x = 0.0
                zero.angular.z = 0.0
                self._cmd_vel_pub.publish(zero)
                self._stop_sent_count -= 1
            return

        if self._last_state is None:
            self._no_state_warn_count += 1
            if self._no_state_warn_count == 1 or self._no_state_warn_count % 50 == 0:
                self.get_logger().warn(
                    "Wander enabled but no /navigation_state yet; is world_model_node running?"
                )
            zero = Twist()
            zero.linear.x = 0.0
            zero.angular.z = 0.0
            self._cmd_vel_pub.publish(zero)
            return

        state = self._last_state
        linear_x, angular_z, next_was, next_turning, next_escape = compute_wander_twist(
            state,
            self._was_forward_safe,
            self._turning_frames,
            self._escape_pulse_remaining,
            self._wander_bias,
            self._forward_speed,
            self._base_turn_speed,
            self._low_conf_angular,
            self._confidence_threshold,
            self._hysteresis_urgency_clear,
            self._turn_timeout_frames,
            self._creep_speed,
            self._escape_pulse_frames,
            self._wander_bias_limit,
        )
        self._was_forward_safe = next_was
        self._turning_frames = next_turning
        self._escape_pulse_remaining = next_escape

        if (
            state.confidence >= self._confidence_threshold
            and next_escape == 0
            and next_was
        ):
            self._wander_bias += random.uniform(
                -self._wander_bias_step, self._wander_bias_step
            )
            self._wander_bias = max(
                -self._wander_bias_limit,
                min(self._wander_bias_limit, self._wander_bias),
            )

        cmd = Twist()
        cmd.linear.x = linear_x
        cmd.angular.z = angular_z

        if self._debug_log_interval > 0:
            self._debug_tick += 1
            if self._debug_tick >= self._debug_log_interval:
                self._debug_tick = 0
                mode = (
                    "low_conf"
                    if state.confidence < self._confidence_threshold
                    else "escape"
                    if self._escape_pulse_remaining > 0
                    else "forward"
                    if next_was
                    else "turn"
                )
                self.get_logger().info(
                    "planner mode=%s safe=%s turn=%d urgency=%.2f conf=%.2f | lin=%.2f ang=%.2f"
                    % (
                        mode,
                        state.forward_safe,
                        state.safest_turn,
                        state.urgency_score,
                        state.confidence,
                        cmd.linear.x,
                        cmd.angular.z,
                    )
                )

        self._cmd_target_pub.publish(cmd)
        self._cmd_vel_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = WanderPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
