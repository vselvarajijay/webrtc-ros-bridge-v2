#!/usr/bin/env python3
"""
Controller node: executes high-level autonomy commands (forward X, turn theta).

Subscribes to /autonomy/command (String) and /robot/telemetry (String JSON).
Publishes /cmd_vel (Twist) in m/s and rad/s. Uses P control or trapezoidal
velocity profile (when velocity/accel/decel specified in command).
"""

import math
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from scout_controller.command_parser import parse_command, STOP_COMMAND
from scout_controller.constants import (
    AUTONOMY_COMMAND_TOPIC,
    CMD_VEL_TOPIC,
    ROBOT_TELEMETRY_TOPIC,
    DEFAULT_MAX_LINEAR_SPEED,
    DEFAULT_MAX_ANGULAR_SPEED,
    DEFAULT_CONTROL_HZ,
    DEFAULT_DISTANCE_TOLERANCE_M,
    DEFAULT_ANGLE_TOLERANCE_DEG,
    DEFAULT_STEP_TIMEOUT_S,
    DEFAULT_LINEAR_P_GAIN,
    DEFAULT_ANGULAR_P_GAIN,
    DEFAULT_ANGULAR_I_GAIN,
    DEFAULT_ANGULAR_D_GAIN,
    DEFAULT_ANGULAR_INTEGRAL_MAX,
    DEFAULT_LINEAR_ACCEL,
    DEFAULT_LINEAR_DECEL,
    DEFAULT_ANGULAR_ACCEL,
    DEFAULT_ANGULAR_DECEL,
)
from scout_controller.telemetry_parse import parse_telemetry

DEG_TO_RAD = math.pi / 180.0


def _normalize_angle_deg(deg: float) -> float:
    """Normalize to [0, 360)."""
    deg = deg % 360.0
    if deg < 0:
        deg += 360.0
    return deg


def _angle_error_deg(target_deg: float, current_deg: float) -> float:
    """Signed error in [-180, 180]: positive = need to turn left (CCW)."""
    target_deg = _normalize_angle_deg(target_deg)
    current_deg = _normalize_angle_deg(current_deg)
    err = target_deg - current_deg
    if err > 180:
        err -= 360
    elif err < -180:
        err += 360
    return err


def _compute_trapezoidal_turn(
    total_angle_rad: float,
    v_max: float,
    accel: float,
    decel: float,
) -> tuple[float, float, float]:
    """
    Compute phase durations (t_accel, t_hold, t_decel) for a turn.
    total_angle_rad is absolute. Returns (t_accel, t_hold, t_decel) in seconds.
    """
    if v_max <= 0 or accel <= 0 or decel <= 0:
        return (0.0, 0.0, 0.0)
    ramp_angle = (v_max * v_max / 2.0) * (1.0 / accel + 1.0 / decel)
    if total_angle_rad <= ramp_angle:
        denom = (1.0 / accel + 1.0 / decel)
        if denom <= 0:
            return (0.0, 0.0, 0.0)
        v_actual = math.sqrt(2.0 * total_angle_rad / denom)
        t_accel = v_actual / accel
        t_decel = v_actual / decel
        return (t_accel, 0.0, t_decel)
    t_accel = v_max / accel
    t_decel = v_max / decel
    hold_angle = total_angle_rad - ramp_angle
    t_hold = hold_angle / v_max if v_max > 0 else 0.0
    return (t_accel, t_hold, t_decel)


def _compute_trapezoidal_drive(
    total_distance_m: float,
    v_max: float,
    accel: float,
    decel: float,
) -> tuple[float, float, float]:
    """Compute (t_accel, t_hold, t_decel) for a drive."""
    if v_max <= 0 or accel <= 0 or decel <= 0:
        return (0.0, 0.0, 0.0)
    ramp_dist = (v_max * v_max / 2.0) * (1.0 / accel + 1.0 / decel)
    if total_distance_m <= ramp_dist:
        denom = (1.0 / accel + 1.0 / decel)
        if denom <= 0:
            return (0.0, 0.0, 0.0)
        v_actual = math.sqrt(2.0 * total_distance_m / denom)
        t_accel = v_actual / accel
        t_decel = v_actual / decel
        return (t_accel, 0.0, t_decel)
    t_accel = v_max / accel
    t_decel = v_max / decel
    hold_dist = total_distance_m - ramp_dist
    t_hold = hold_dist / v_max if v_max > 0 else 0.0
    return (t_accel, t_hold, t_decel)


def _get_profile_setpoint(
    t_elapsed: float,
    t_accel: float,
    t_hold: float,
    t_decel: float,
    v_max: float,
    accel: float,
    decel: float,
) -> float:
    """Return velocity setpoint at time t_elapsed for trapezoidal profile."""
    if t_elapsed < t_accel:
        return min(accel * t_elapsed, v_max)
    if t_elapsed < t_accel + t_hold:
        return v_max
    if t_elapsed < t_accel + t_hold + t_decel:
        tau = t_elapsed - (t_accel + t_hold)
        return max(v_max - decel * tau, 0.0)
    return 0.0


class ControllerNode(Node):
    """ROS 2 node that runs autonomy command goals with P control."""

    def __init__(self):
        super().__init__("controller_node")
        self._lock = threading.Lock()
        self._goal_queue: list = []
        self._state = "idle"  # idle | driving | turning
        self._traveled_m = 0.0
        self._target_heading_deg: float | None = None
        self._last_telemetry: tuple[float, float, float] | None = None  # (heading, speed, ts)
        self._last_ts = 0.0
        self._goal_start_time = 0.0

        # Trapezoidal profile state (set when starting a profile goal)
        self._profile_phase: str | None = None  # "ramp_up" | "hold" | "ramp_down" | None
        self._profile_t_accel = 0.0
        self._profile_t_hold = 0.0
        self._profile_t_decel = 0.0
        self._profile_t_elapsed = 0.0
        self._profile_integrated = 0.0  # angle_rad for turn, distance_m for drive
        self._profile_total = 0.0  # target total (angle_rad or distance_m)
        self._profile_v_max = 0.0  # peak velocity for current profile
        self._profile_setpoint = 0.0  # current velocity setpoint (rad/s or m/s)
        self._profile_sign = 1  # +1 or -1 for direction
        self._profile_accel = 0.0
        self._profile_decel = 0.0

        # PID state for turn (P-only branch)
        self._turn_integral = 0.0  # degree-seconds
        self._turn_last_err_deg: float | None = None
        self._turn_last_time = 0.0

        # Parameters
        self.declare_parameter("max_linear_speed", DEFAULT_MAX_LINEAR_SPEED)
        self.declare_parameter("max_angular_speed", DEFAULT_MAX_ANGULAR_SPEED)
        self.declare_parameter("control_hz", DEFAULT_CONTROL_HZ)
        self.declare_parameter("distance_tolerance_m", DEFAULT_DISTANCE_TOLERANCE_M)
        self.declare_parameter("angle_tolerance_deg", DEFAULT_ANGLE_TOLERANCE_DEG)
        self.declare_parameter("step_timeout_s", DEFAULT_STEP_TIMEOUT_S)
        self.declare_parameter("linear_p_gain", DEFAULT_LINEAR_P_GAIN)
        self.declare_parameter("angular_p_gain", DEFAULT_ANGULAR_P_GAIN)
        self.declare_parameter("angular_i_gain", DEFAULT_ANGULAR_I_GAIN)
        self.declare_parameter("angular_d_gain", DEFAULT_ANGULAR_D_GAIN)
        self.declare_parameter("angular_integral_max", DEFAULT_ANGULAR_INTEGRAL_MAX)
        self.declare_parameter("default_linear_accel", DEFAULT_LINEAR_ACCEL)
        self.declare_parameter("default_linear_decel", DEFAULT_LINEAR_DECEL)
        self.declare_parameter("default_angular_accel", DEFAULT_ANGULAR_ACCEL)
        self.declare_parameter("default_angular_decel", DEFAULT_ANGULAR_DECEL)

        self._cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.create_subscription(String, AUTONOMY_COMMAND_TOPIC, self._on_command, 10)
        self.create_subscription(String, ROBOT_TELEMETRY_TOPIC, self._on_telemetry, 10)

        control_hz = self.get_parameter("control_hz").value
        self._control_timer = self.create_timer(1.0 / control_hz, self._control_tick)
        self.get_logger().info(
            "controller_node started: sub %s, %s; pub %s; control %.1f Hz"
            % (AUTONOMY_COMMAND_TOPIC, ROBOT_TELEMETRY_TOPIC, CMD_VEL_TOPIC, control_hz)
        )

    def _on_command(self, msg: String) -> None:
        text = (msg.data or "").strip()
        if not text:
            return
        if text.lower() == STOP_COMMAND:
            with self._lock:
                self._goal_queue.clear()
                self._state = "idle"
            self.get_logger().info("Stop: cleared goal queue")
            return
        goals = parse_command(text)
        if not goals:
            self.get_logger().warn("Parse produced no goals for: %r" % text)
            return
        with self._lock:
            self._goal_queue = goals
            self._traveled_m = 0.0
            self._goal_start_time = time.monotonic()
            if self._state == "idle":
                self._start_next_goal()
        self.get_logger().info("Queued %d goal(s) from: %r" % (len(goals), text))

    def _on_telemetry(self, msg: String) -> None:
        parsed = parse_telemetry(msg.data or "")
        with self._lock:
            self._last_telemetry = parsed

    def _start_next_goal(self) -> None:
        """Assume lock held. Start first goal in queue or go idle."""
        if not self._goal_queue:
            self._state = "idle"
            self._profile_phase = None
            return
        goal = self._goal_queue[0]
        self._goal_start_time = time.monotonic()
        self._profile_phase = None

        if goal["type"] == "drive":
            self._state = "driving"
            self._traveled_m = 0.0
            # Trapezoidal profile when linear_vel_m_s is specified
            v_lin = goal.get("linear_vel_m_s")
            if v_lin is not None and v_lin > 0:
                max_linear = self.get_parameter("max_linear_speed").value
                v_max = min(v_lin, max_linear)
                accel = goal.get("accel_m_s2") or self.get_parameter("default_linear_accel").value
                decel = goal.get("decel_m_s2") or self.get_parameter("default_linear_decel").value
                dist = goal["distance_m"] * goal.get("direction", 1)
                dist_abs = abs(dist)
                t_a, t_h, t_d = _compute_trapezoidal_drive(dist_abs, v_max, accel, decel)
                self._profile_t_accel = t_a
                self._profile_t_hold = t_h
                self._profile_t_decel = t_d
                self._profile_t_elapsed = 0.0
                self._profile_integrated = 0.0
                self._profile_total = dist_abs
                self._profile_v_max = v_max
                self._profile_accel = accel
                self._profile_decel = decel
                self._profile_setpoint = 0.0
                self._profile_sign = 1 if dist >= 0 else -1
                self._profile_phase = "ramp_up"

        elif goal["type"] == "turn":
            self._state = "turning"
            self._turn_integral = 0.0
            self._turn_last_err_deg = None
            self._turn_last_time = time.monotonic()
            if self._last_telemetry is not None:
                current = self._last_telemetry[0]
                self._target_heading_deg = _normalize_angle_deg(current + goal["angle_deg"])
            else:
                self._target_heading_deg = _normalize_angle_deg(goal["angle_deg"])
            # Trapezoidal profile when angular_vel_rad_s is specified
            v_ang = goal.get("angular_vel_rad_s")
            if v_ang is not None and v_ang > 0:
                max_angular = self.get_parameter("max_angular_speed").value
                v_max = min(v_ang, max_angular)
                accel = goal.get("accel_rad_s2") or self.get_parameter("default_angular_accel").value
                decel = goal.get("decel_rad_s2") or self.get_parameter("default_angular_decel").value
                total_rad = abs(goal["angle_deg"]) * DEG_TO_RAD
                t_a, t_h, t_d = _compute_trapezoidal_turn(total_rad, v_max, accel, decel)
                self._profile_t_accel = t_a
                self._profile_t_hold = t_h
                self._profile_t_decel = t_d
                self._profile_t_elapsed = 0.0
                self._profile_integrated = 0.0
                self._profile_total = total_rad
                self._profile_v_max = v_max
                self._profile_accel = accel
                self._profile_decel = decel
                self._profile_setpoint = 0.0
                self._profile_sign = -1 if goal["angle_deg"] >= 0 else 1  # ROS: positive z = left
                self._profile_phase = "ramp_up"

    def _control_tick(self) -> None:
        with self._lock:
            telemetry = self._last_telemetry
            goals = list(self._goal_queue)
            state = self._state
            traveled = self._traveled_m
            target_heading = self._target_heading_deg
            goal_start = self._goal_start_time
        max_linear = self.get_parameter("max_linear_speed").value
        max_angular = self.get_parameter("max_angular_speed").value
        dist_tol = self.get_parameter("distance_tolerance_m").value
        angle_tol = self.get_parameter("angle_tolerance_deg").value
        step_timeout = self.get_parameter("step_timeout_s").value
        k_linear = self.get_parameter("linear_p_gain").value
        k_angular = self.get_parameter("angular_p_gain").value

        twist = Twist()
        twist.linear.x = 0.0
        twist.linear.y = 0.0
        twist.linear.z = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = 0.0

        if not goals:
            self._cmd_pub.publish(twist)
            return

        now = time.monotonic()
        if now - goal_start > step_timeout:
            self.get_logger().warn("Step timeout (%.1fs); skipping goal" % step_timeout)
            with self._lock:
                if self._goal_queue:
                    self._goal_queue.pop(0)
                self._start_next_goal()
            self._cmd_pub.publish(twist)
            return

        goal = goals[0]
        dt = 1.0 / self.get_parameter("control_hz").value

        if goal["type"] == "drive":
            if self._profile_phase is not None:
                setpoint = _get_profile_setpoint(
                    self._profile_t_elapsed,
                    self._profile_t_accel,
                    self._profile_t_hold,
                    self._profile_t_decel,
                    self._profile_v_max,
                    self._profile_accel,
                    self._profile_decel,
                )
                self._profile_t_elapsed += dt
                self._profile_integrated += setpoint * dt
                twist.linear.x = self._profile_sign * max(-max_linear, min(max_linear, setpoint))
                total_time = self._profile_t_accel + self._profile_t_hold + self._profile_t_decel
                if self._profile_integrated >= self._profile_total - dist_tol or self._profile_t_elapsed >= total_time:
                    with self._lock:
                        if self._goal_queue:
                            self._goal_queue.pop(0)
                        self._start_next_goal()
                self._cmd_pub.publish(twist)
                return
            if telemetry is None:
                self._cmd_pub.publish(twist)
                return
            _, speed_m_s, ts = telemetry
            last_ts = getattr(self, "_last_ts", 0.0)
            if last_ts > 0 and ts > last_ts:
                dtt = ts - last_ts
                traveled += speed_m_s * dtt * goal.get("direction", 1)
            with self._lock:
                self._traveled_m = traveled
            self._last_ts = ts

            remaining = goal["distance_m"] - abs(traveled)
            if remaining <= dist_tol:
                with self._lock:
                    if self._goal_queue:
                        self._goal_queue.pop(0)
                    self._start_next_goal()
                self._cmd_pub.publish(twist)
                return
            direction = goal.get("direction", 1)
            linear = direction * min(k_linear * remaining, max_linear)
            linear = max(-max_linear, min(max_linear, linear))
            twist.linear.x = linear
            self._cmd_pub.publish(twist)
            return

        if goal["type"] == "turn":
            if self._profile_phase is not None:
                setpoint = _get_profile_setpoint(
                    self._profile_t_elapsed,
                    self._profile_t_accel,
                    self._profile_t_hold,
                    self._profile_t_decel,
                    self._profile_v_max,
                    self._profile_accel,
                    self._profile_decel,
                )
                self._profile_t_elapsed += dt
                self._profile_integrated += setpoint * dt
                twist.angular.z = self._profile_sign * max(-max_angular, min(max_angular, setpoint))
                total_time = self._profile_t_accel + self._profile_t_hold + self._profile_t_decel
                if self._profile_integrated >= self._profile_total - (angle_tol * DEG_TO_RAD) or self._profile_t_elapsed >= total_time:
                    with self._lock:
                        if self._goal_queue:
                            self._goal_queue.pop(0)
                        self._start_next_goal()
                self._cmd_pub.publish(twist)
                return
            if telemetry is None or target_heading is None:
                self._cmd_pub.publish(twist)
                return
            current_heading, _, _ = telemetry
            err_deg = _angle_error_deg(target_heading, current_heading)
            if abs(err_deg) <= angle_tol:
                with self._lock:
                    if self._goal_queue:
                        self._goal_queue.pop(0)
                    self._start_next_goal()
                self._cmd_pub.publish(twist)
                return
            # PID: smooth turn. positive err = turn left (CCW) = positive angular.z in ROS
            k_i = self.get_parameter("angular_i_gain").value
            k_d = self.get_parameter("angular_d_gain").value
            integral_max = self.get_parameter("angular_integral_max").value
            now_t = time.monotonic()
            dt = now_t - self._turn_last_time if self._turn_last_time > 0 else dt
            if dt > 0 and dt < 1.0:
                self._turn_integral += err_deg * dt
                self._turn_integral = max(-integral_max, min(integral_max, self._turn_integral))
            self._turn_last_time = now_t
            deriv = 0.0
            if self._turn_last_err_deg is not None and dt > 0 and dt < 1.0:
                deriv = (err_deg - self._turn_last_err_deg) / dt
            self._turn_last_err_deg = err_deg
            angular = k_angular * err_deg + k_i * self._turn_integral + k_d * deriv
            angular = max(-max_angular, min(max_angular, angular))
            twist.angular.z = angular
            self._cmd_pub.publish(twist)
            return

        self._cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = ControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
</think>
Adding `_last_ts` to `__init__` and removing the duplicate property at the end.
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace