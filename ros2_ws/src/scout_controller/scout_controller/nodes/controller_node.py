#!/usr/bin/env python3
"""
Controller node: executes high-level autonomy commands (forward X, turn theta).

Subscribes to /autonomy/command (String) and /robot/telemetry (String JSON).
Publishes /cmd_vel (Twist) in m/s and rad/s. Uses P control for distance and heading.
"""

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
)
from scout_controller.telemetry_parse import parse_telemetry


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

        # Parameters
        self.declare_parameter("max_linear_speed", DEFAULT_MAX_LINEAR_SPEED)
        self.declare_parameter("max_angular_speed", DEFAULT_MAX_ANGULAR_SPEED)
        self.declare_parameter("control_hz", DEFAULT_CONTROL_HZ)
        self.declare_parameter("distance_tolerance_m", DEFAULT_DISTANCE_TOLERANCE_M)
        self.declare_parameter("angle_tolerance_deg", DEFAULT_ANGLE_TOLERANCE_DEG)
        self.declare_parameter("step_timeout_s", DEFAULT_STEP_TIMEOUT_S)
        self.declare_parameter("linear_p_gain", DEFAULT_LINEAR_P_GAIN)
        self.declare_parameter("angular_p_gain", DEFAULT_ANGULAR_P_GAIN)

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
            return
        goal = self._goal_queue[0]
        self._goal_start_time = time.monotonic()
        if goal["type"] == "drive":
            self._state = "driving"
            self._traveled_m = 0.0
        elif goal["type"] == "turn":
            self._state = "turning"
            if self._last_telemetry is not None:
                current = self._last_telemetry[0]
                self._target_heading_deg = _normalize_angle_deg(current + goal["angle_deg"])
            else:
                self._target_heading_deg = _normalize_angle_deg(goal["angle_deg"])

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
        if goal["type"] == "drive":
            if telemetry is None:
                self._cmd_pub.publish(twist)
                return
            _, speed_m_s, ts = telemetry
            last_ts = getattr(self, "_last_ts", 0.0)
            if last_ts > 0 and ts > last_ts:
                dt = ts - last_ts
                traveled += speed_m_s * dt * goal.get("direction", 1)
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
            # ROS: positive angular.z = CCW (left). Our error: positive = turn left.
            angular = k_angular * err_deg
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


# Fix: use instance attribute for _last_ts (was referencing before assignment in _control_tick)
# Replace _last_ts with a single stored value; we're already using self._last_ts in the method.
# Check: in _control_tick we have "if self._last_ts > 0" and "self._last_ts = ts" but we never defined _last_ts on the instance. So we need to add self._last_ts = 0.0 in __init__ and use it. Let me fix that.
</think>
Adding `_last_ts` to `__init__` and removing the duplicate property at the end.
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace