#!/usr/bin/env python3
"""
World model node: interprets optical flow + velocity into navigation state.

Subscribes to /optical_flow (Float32MultiArray) and /robot/telemetry (JSON).
Publishes /navigation_state (NavigationState: forward_safe, safest_turn, urgency_score, confidence).

Does not compute flow or send motor commands; perception and behavior stay in other nodes.
"""

import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_msgs.msg import Float32MultiArray
from connectx_msgs.msg import NavigationState

from connectx_planner.constants import (
    OPTICAL_FLOW_TOPIC,
    ROBOT_TELEMETRY_TOPIC,
    NAVIGATION_STATE_TOPIC,
)

# Legacy 9-element layout: [vx_l, vy_l, mag_l, vx_c, vy_c, mag_c, vx_r, vy_r, mag_r]
FLOW_MAG_LEFT, FLOW_MAG_CENTER, FLOW_MAG_RIGHT = 2, 5, 8
# Enhanced 18-element: mid band mags at 11, 14, 17
FLOW_MAG_LEFT_MID, FLOW_MAG_CENTER_MID, FLOW_MAG_RIGHT_MID = 11, 14, 17

DEFAULT_RISK_FORWARD_THRESHOLD = 30.0
DEFAULT_VELOCITY_EPSILON = 0.05
DEFAULT_STRAIGHT_DEAD_ZONE = 2.0
DEFAULT_PUBLISH_HZ = 25.0


def parse_speed_from_telemetry(json_str: str) -> float:
    """Parse speed (m/s) from /robot/telemetry JSON. Returns 0.0 if invalid."""
    if not json_str or not json_str.strip():
        return 0.0
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    speed = data.get("speed")
    if speed is None:
        return 0.0
    try:
        return float(speed)
    except (TypeError, ValueError):
        return 0.0


class WorldModelNode(Node):
    def __init__(self):
        super().__init__("world_model_node")
        self._lock = threading.Lock()
        self._last_flow: list[float] | None = None
        self._last_flow_stamp_ns: int | None = None
        self._last_velocity_m_s: float = 0.0
        self._last_telemetry_stamp_ns: int | None = None

        self.declare_parameter("risk_forward_threshold", DEFAULT_RISK_FORWARD_THRESHOLD)
        self.declare_parameter("velocity_epsilon", DEFAULT_VELOCITY_EPSILON)
        self.declare_parameter("straight_dead_zone", DEFAULT_STRAIGHT_DEAD_ZONE)
        self.declare_parameter("publish_hz", DEFAULT_PUBLISH_HZ)
        self.declare_parameter("optical_flow_topic", OPTICAL_FLOW_TOPIC)
        self.declare_parameter("robot_telemetry_topic", ROBOT_TELEMETRY_TOPIC)
        self.declare_parameter("navigation_state_topic", NAVIGATION_STATE_TOPIC)

        opt_topic = self.get_parameter("optical_flow_topic").value
        tele_topic = self.get_parameter("robot_telemetry_topic").value
        nav_topic = self.get_parameter("navigation_state_topic").value

        self._nav_pub = self.create_publisher(NavigationState, nav_topic, 10)
        self.create_subscription(Float32MultiArray, opt_topic, self._on_optical_flow, 10)
        self.create_subscription(String, tele_topic, self._on_telemetry, 10)

        rate = self.get_parameter("publish_hz").value
        self._timer = self.create_timer(1.0 / rate, self._publish_state)

        self.get_logger().info(
            "world_model_node: sub %s, %s; pub %s; %.1f Hz"
            % (opt_topic, tele_topic, nav_topic, rate)
        )

    def _on_optical_flow(self, msg: Float32MultiArray) -> None:
        if len(msg.data) < 9:
            return
        with self._lock:
            self._last_flow = list(msg.data[: min(len(msg.data), 18)])
            self._last_flow_stamp_ns = self.get_clock().now().nanoseconds

    def _on_telemetry(self, msg: String) -> None:
        v = parse_speed_from_telemetry(msg.data or "")
        with self._lock:
            self._last_velocity_m_s = v
            self._last_telemetry_stamp_ns = self.get_clock().now().nanoseconds

    def _get_mags(self) -> tuple[float, float, float] | None:
        with self._lock:
            flow = self._last_flow
        if flow is None or len(flow) < 9:
            return None
        if len(flow) >= 18:
            mag_left = flow[FLOW_MAG_LEFT_MID]
            mag_center = flow[FLOW_MAG_CENTER_MID]
            mag_right = flow[FLOW_MAG_RIGHT_MID]
        else:
            mag_left = flow[FLOW_MAG_LEFT]
            mag_center = flow[FLOW_MAG_CENTER]
            mag_right = flow[FLOW_MAG_RIGHT]
        return (mag_left, mag_center, mag_right)

    def _publish_state(self) -> None:
        mags = self._get_mags()
        with self._lock:
            velocity = self._last_velocity_m_s
        if mags is None:
            out = NavigationState()
            out.header.stamp = self.get_clock().now().to_msg()
            out.header.frame_id = ""
            out.forward_safe = False
            out.safest_turn = 0
            out.urgency_score = 0.0
            out.confidence = 0.0
            self._nav_pub.publish(out)
            return

        mag_left, mag_center, mag_right = mags
        threshold = self.get_parameter("risk_forward_threshold").value
        eps = self.get_parameter("velocity_epsilon").value
        dead_zone = self.get_parameter("straight_dead_zone").value

        vel_eff = velocity + eps
        risk_forward = mag_center / vel_eff if vel_eff > 0 else (mag_center / eps if eps > 0 else 0.0)
        forward_safe = risk_forward < threshold
        urgency_score = min(1.0, risk_forward / threshold) if threshold > 0 else 0.0

        asymmetry = mag_right - mag_left
        if abs(asymmetry) < dead_zone:
            safest_turn = 0
        elif mag_left < mag_right:
            safest_turn = -1
        else:
            safest_turn = 1

        confidence = 1.0
        with self._lock:
            if self._last_flow_stamp_ns is None:
                confidence *= 0.0
            # Optional: reduce confidence if telemetry is very stale (not required for MVP)

        out = NavigationState()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = ""
        out.forward_safe = forward_safe
        out.safest_turn = safest_turn
        out.urgency_score = urgency_score
        out.confidence = confidence
        self._nav_pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = WorldModelNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
