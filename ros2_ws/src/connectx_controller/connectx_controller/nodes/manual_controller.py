#!/usr/bin/env python3
"""
Manual controller node: subscribes to /teleop/velocity_target (from keyboard_node)
and /robot/telemetry, applies ramping and safety, publishes /cmd_vel.
"""

from __future__ import annotations

import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from connectx_controller.constants import (
    CMD_VEL_TOPIC,
    ROBOT_TELEMETRY_TOPIC,
    TELEOP_VELOCITY_TARGET_TOPIC,
)
from connectx_controller.telemetry_safety import TelemetryForSafety, parse_telemetry_json
from connectx_controller.teleop_controller import TeleopController
from connectx_controller.teleop_utils import print_hud

CONTROL_HZ = 50.0
LINEAR_MAX = 0.3
ANGULAR_MAX = 0.6
RAMP_UP_SEC = 0.1
RAMP_DN_SEC = 0.15
DECAY_ALPHA = 0.85
SPEED_MODE_DEFAULT = 3
SPEED_MODE_MAX = 5
HUD_INTERVAL_SEC = 0.1


class ManualControllerNode(Node):
    """Subscribes to teleop target and telemetry; publishes ramped/safe /cmd_vel."""

    def __init__(self):
        super().__init__("manual_controller")
        self._lock = threading.Lock()
        self._latest_target: Optional[Twist] = None
        self._latest_telemetry_json: Optional[str] = None

        self._cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.create_subscription(Twist, TELEOP_VELOCITY_TARGET_TOPIC, self._on_target, 10)
        self.create_subscription(String, ROBOT_TELEMETRY_TOPIC, self._on_telemetry, 10)

        self._controller = TeleopController(
            logger=self.get_logger(),
            linear_max=LINEAR_MAX,
            angular_max=ANGULAR_MAX,
            ramp_up_sec=RAMP_UP_SEC,
            ramp_dn_sec=RAMP_DN_SEC,
            decay_alpha=DECAY_ALPHA,
            control_hz=CONTROL_HZ,
        )

        self.create_timer(1.0 / CONTROL_HZ, self._control_tick)
        self._hud_timer = self.create_timer(HUD_INTERVAL_SEC, self._hud_tick)
        self.get_logger().info(
            "manual_controller: sub %s, %s; pub %s; %.1f Hz",
            TELEOP_VELOCITY_TARGET_TOPIC,
            ROBOT_TELEMETRY_TOPIC,
            CMD_VEL_TOPIC,
            CONTROL_HZ,
        )

    def _on_target(self, msg: Twist) -> None:
        with self._lock:
            self._latest_target = msg

    def _on_telemetry(self, msg: String) -> None:
        if msg.data:
            with self._lock:
                self._latest_telemetry_json = msg.data

    def _control_tick(self) -> None:
        with self._lock:
            target = self._latest_target
            telemetry_json = self._latest_telemetry_json

        if target is not None:
            self._controller.set_target_velocities(
                float(target.linear.x),
                float(target.angular.z),
            )
        else:
            # No teleop target (keyboard_node not running): ramp to zero
            self._controller.set_target_velocities(0.0, 0.0)

        telemetry: Optional[TelemetryForSafety] = None
        if telemetry_json:
            telemetry = parse_telemetry_json(telemetry_json)

        self._controller.tick(telemetry=telemetry)
        linear, angular = self._controller.get_current_velocities()

        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self._cmd_pub.publish(msg)

    def _hud_tick(self) -> None:
        telemetry = self._controller.get_last_telemetry()
        linear, angular = self._controller.get_current_velocities()
        print_hud(
            telemetry,
            linear,
            angular,
            speed_mode=SPEED_MODE_DEFAULT,
            speed_mode_max=SPEED_MODE_MAX,
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ManualControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        msg = Twist()
        node._cmd_pub.publish(msg)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
