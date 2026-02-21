#!/usr/bin/env python3
"""
Wander planner: converts navigation state into velocity commands.

Subscribes to /navigation_state and /autonomy/command.
When wander is enabled (e.g. UI "Start wandering"), continuously publishes to /cmd_vel
and /cmd_vel_target so the robot keeps moving. Runs until it receives another command
(e.g. "stop" or manual drive); only then does it publish zero and yield /cmd_vel.
"""

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
DEFAULT_LOW_CONFIDENCE_GRACE_TICKS = 15  # ~0.6 s at 25 Hz; hold last cmd during brief flow dropouts
DEFAULT_OUTPUT_SMOOTHING_ALPHA = 0.7  # 0=no smoothing, higher=smoother (EMA of published cmd)
DEFAULT_FORWARD_STEER_TOWARD_FURTHEST = 0.4  # rad/s; steer toward clearest side (safest_turn) while going forward
DEFAULT_TURN_LINEAR_FRACTION = 0.6  # fraction of forward_speed to keep while turning (avoid stop-and-turn)


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
    forward_steer_toward_furthest: float,
    turn_linear_fraction: float,
) -> tuple[float, float, bool, int, int]:
    """Compute twist (linear_x, angular_z) and next internal state from current state.
    Returns (linear_x, angular_z, next_was_forward_safe, next_turning_frames, next_escape_pulse_remaining).
    Pure function for testing and use by WanderPlanner._tick (wander_bias is updated by caller with random)."""
    if state.confidence < confidence_threshold:
        # Never stop: keep moving at turn_linear while turning in place (low conf).
        min_linear = forward_speed * turn_linear_fraction
        return (
            min_linear,
            low_confidence_angular,
            was_forward_safe,
            0,
            0,
        )

    if escape_pulse_remaining > 0:
        next_remaining = escape_pulse_remaining - 1
        next_turning = 0 if next_remaining == 0 else turning_frames
        turn_linear = forward_speed * turn_linear_fraction
        return (turn_linear, 0.0, was_forward_safe, next_turning, next_remaining)

    # Hysteresis only for clearing: enter turn as soon as path is unsafe (forward_safe=False).
    # Return to forward only when path is clear AND urgency is below threshold (avoids
    # oscillating on a single noisy safe frame, e.g. on carpet).
    next_was = was_forward_safe
    next_turning = turning_frames
    if state.forward_safe and state.urgency_score < hysteresis_urgency_clear:
        next_was = True
        next_turning = 0
    elif not state.forward_safe:
        next_was = False  # enter turn immediately when path is unsafe

    forward_allowed = next_was

    if forward_allowed:
        # Go toward longest distance (furthest): steer only by safest_turn (direction of lowest flow = most open). No random wander.
        angular_z = float(state.safest_turn) * forward_steer_toward_furthest
        angular_z = max(
            -forward_steer_toward_furthest,
            min(forward_steer_toward_furthest, angular_z),
        )
        return (forward_speed, angular_z, next_was, 0, 0)

    next_turning = turning_frames + 1
    # Keep moving while turning: use a fraction of forward_speed, never stop-and-turn.
    turn_linear = forward_speed * turn_linear_fraction
    turn_dir = float(state.safest_turn)
    urgency = max(0.0, min(1.0, state.urgency_score))
    # Turn very strong when obstacles nearby: turn_mult 1.0 to 3.0 (urgency scales aggressively).
    turn_mult = 1.0 + 2.0 * urgency
    angular = turn_dir * (base_turn_speed * turn_mult)
    # No escape pulse: keep turning (no pause). If we hit timeout, same command.
    return (turn_linear, angular, next_was, next_turning, 0)


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
        self._low_conf_ticks = 0  # consecutive ticks with confidence < threshold
        self._last_linear = 0.0
        self._last_angular = 0.0

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
        self.declare_parameter(
            "low_confidence_grace_ticks", DEFAULT_LOW_CONFIDENCE_GRACE_TICKS
        )
        self.declare_parameter(
            "output_smoothing_alpha", DEFAULT_OUTPUT_SMOOTHING_ALPHA
        )
        self.declare_parameter(
            "forward_steer_toward_furthest", DEFAULT_FORWARD_STEER_TOWARD_FURTHEST
        )
        self.declare_parameter(
            "turn_linear_fraction", DEFAULT_TURN_LINEAR_FRACTION
        )
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
        self._low_conf_grace_ticks = self.get_parameter(
            "low_confidence_grace_ticks"
        ).value
        self._output_smoothing_alpha = self.get_parameter(
            "output_smoothing_alpha"
        ).value
        self._forward_steer_toward_furthest = self.get_parameter(
            "forward_steer_toward_furthest"
        ).value
        self._turn_linear_fraction = self.get_parameter(
            "turn_linear_fraction"
        ).value
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

        # No navigation state yet or temporarily missing: keep moving with last command
        # (or default forward) so wander never stops until we get an explicit "stop" command.
        if self._last_state is None:
            self._no_state_warn_count += 1
            if self._no_state_warn_count == 1 or self._no_state_warn_count % 50 == 0:
                self.get_logger().warn(
                    "Wander enabled but no /navigation_state yet; is world_model_node running?"
                )
            cmd_linear = (
                self._last_linear
                if abs(self._last_linear) > 1e-6 or abs(self._last_angular) > 1e-6
                else self._forward_speed
            )
            cmd_linear = max(self._forward_speed * 0.3, cmd_linear)
            cmd_angular = self._last_angular if abs(self._last_angular) > 1e-6 else 0.0
            self._last_linear = cmd_linear
            self._last_angular = cmd_angular
            cmd = Twist()
            cmd.linear.x = cmd_linear
            cmd.angular.z = cmd_angular
            self._cmd_target_pub.publish(cmd)
            self._cmd_vel_pub.publish(cmd)
            return

        state = self._last_state

        # When confidence is low (e.g. optical flow dropout), hold last command for a
        # grace period; after that keep moving at last or reduced speed so wander never stops.
        if state.confidence < self._confidence_threshold:
            self._low_conf_ticks += 1
            if (
                self._low_conf_ticks <= self._low_conf_grace_ticks
                and (abs(self._last_linear) > 1e-6 or abs(self._last_angular) > 1e-6)
            ):
                cmd_linear = max(self._forward_speed * 0.3, self._last_linear)
                cmd_angular = self._last_angular
            else:
                # Beyond grace: keep moving (never full stop). Use last linear or turn_linear.
                cmd_linear = (
                    max(self._forward_speed * 0.3, self._last_linear)
                    if self._last_linear > 1e-6
                    else self._forward_speed * self._turn_linear_fraction
                )
                cmd_angular = self._low_conf_angular
            cmd_linear = max(self._forward_speed * 0.3, cmd_linear)
            self._last_linear = cmd_linear
            self._last_angular = cmd_angular
            cmd = Twist()
            cmd.linear.x = cmd_linear
            cmd.angular.z = cmd_angular
            self._cmd_target_pub.publish(cmd)
            self._cmd_vel_pub.publish(cmd)
            return

        self._low_conf_ticks = 0

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
            self._forward_steer_toward_furthest,
            self._turn_linear_fraction,
        )
        self._was_forward_safe = next_was
        self._turning_frames = next_turning
        self._escape_pulse_remaining = next_escape

        # No random wander bias: we steer only toward furthest (safest_turn from world model).

        # Smooth published velocity so motion is less jerky
        alpha = self._output_smoothing_alpha
        cmd_linear = alpha * self._last_linear + (1.0 - alpha) * linear_x
        cmd_angular = alpha * self._last_angular + (1.0 - alpha) * angular_z
        # Never stop moving forward: enforce minimum linear when wander is on.
        min_linear = self._forward_speed * 0.3
        cmd_linear = max(min_linear, cmd_linear)
        self._last_linear = cmd_linear
        self._last_angular = cmd_angular

        cmd = Twist()
        cmd.linear.x = cmd_linear
        cmd.angular.z = cmd_angular

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
