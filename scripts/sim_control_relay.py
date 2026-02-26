#!/usr/bin/env python3
"""
HTTP server that receives velocity commands (POST /control) and publishes to ROS 2 /cmd_vel_sim.
Used so the webrtc_node (in scout_bridge) can drive the Gazebo sim (in gazebo_sim) without
relying on ROS 2 DDS discovery across Docker containers.

Publishes the last received command at a steady 50 Hz so the Gazebo DiffDrive plugin
gets a continuous stream (avoids jitter from bursty HTTP POSTs and slow spin).

Run inside the gazebo_sim container. Webrtc_node is configured with SIM_CONTROL_URL=http://gazebo_sim:5000.

Usage:
  source /opt/ros/kilted/setup.bash
  source /root/ros2_ws/install/setup.bash  # in gazebo container
  python3 scripts/sim_control_relay.py

Env:
  SIM_CONTROL_PORT  Port to listen on (default 5000)
"""

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CMD_VEL_SIM_TOPIC = "/cmd_vel_sim"
RELAY_HZ = 50
SPIN_TIMEOUT_SEC = 0.02  # 50 Hz spin so timer and publishes flush promptly

node_ref: list = []
pub_ref: list = []

# Last command received via POST; published at RELAY_HZ by timer. [linear_x, angular_z]
last_cmd_ref: list = [0.0, 0.0]


def run_ros_spin():
    """Background thread: spin the ROS node so timer and publishes are sent."""
    while rclpy.ok():
        try:
            if node_ref:
                rclpy.spin_once(node_ref[0], timeout_sec=SPIN_TIMEOUT_SEC)
            else:
                import time
                time.sleep(0.1)
        except Exception as e:
            LOG.debug("spin_once: %s", e)


_first_request_logged: list = [True]


class ControlHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/control" or self.path == "/control/":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length else b"{}"
                data = json.loads(body.decode("utf-8"))
                linear_x = float(data.get("linear_x", 0.0))
                angular_z = float(data.get("angular_z", 0.0))
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                LOG.warning("Invalid /control body: %s", e)
                self.send_response(400)
                self.end_headers()
                return
            # Store for timer; timer thread does the actual publish at 50 Hz
            last_cmd_ref[0] = linear_x
            last_cmd_ref[1] = angular_z
            if _first_request_logged[0]:
                _first_request_logged[0] = False
                LOG.info(
                    "Sim control relay: first POST (linear_x=%.2f angular_z=%.2f) -> %s at %d Hz",
                    linear_x, angular_z, CMD_VEL_SIM_TOPIC, RELAY_HZ,
                )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        LOG.debug("%s - %s", self.address_string(), format % args)


def main():
    port = int(os.environ.get("SIM_CONTROL_PORT", "5000"))
    try:
        rclpy.init()
    except Exception as e:
        LOG.error("sim_control_relay: rclpy.init failed: %s", e)
        raise
    node = Node("sim_control_relay")
    node_ref.append(node)
    pub = node.create_publisher(Twist, CMD_VEL_SIM_TOPIC, 10)
    pub_ref.append(pub)

    def timer_callback():
        if not pub_ref:
            return
        msg = Twist()
        msg.linear.x = last_cmd_ref[0]
        msg.angular.z = last_cmd_ref[1]
        pub_ref[0].publish(msg)

    node.create_timer(1.0 / RELAY_HZ, timer_callback)

    spin_thread = threading.Thread(target=run_ros_spin, daemon=True)
    spin_thread.start()
    server = HTTPServer(("0.0.0.0", port), ControlHandler)
    LOG.info(
        "Sim control relay listening on 0.0.0.0:%s (POST /control -> %s @ %d Hz)",
        port, CMD_VEL_SIM_TOPIC, RELAY_HZ,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
