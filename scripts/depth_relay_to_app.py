#!/usr/bin/env python3
"""
Relay depth images from ROS2 /da3/depth_colored to the app's POST /api/depth_image_ingest.

Run in an environment where ROS2 is available (e.g. scout_perception container or host
with ros2 workspace sourced). The app must be reachable at APP_URL (default http://127.0.0.1:8000).

Usage:
  source /opt/ros/kilted/setup.bash
  source /root/workspace/ros2_ws/install/setup.bash  # if needed
  python3 scripts/depth_relay_to_app.py

Env:
  APP_URL  Base URL of the app (default: http://127.0.0.1:8000)
"""

import os
import sys
import urllib.error
import urllib.request

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


def main():
    app_url = os.environ.get("APP_URL", "http://127.0.0.1:8000").rstrip("/")
    ingest_url = f"{app_url}/api/depth_image_ingest"

    rclpy.init()
    node = Node("depth_relay_to_app")

    def callback(msg: CompressedImage):
        try:
            req = urllib.request.Request(
                ingest_url,
                data=bytes(msg.data),
                method="POST",
                headers={"Content-Type": "image/jpeg"},
            )
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            node.get_logger().warn(f"Depth ingest HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            node.get_logger().warn(f"Depth ingest URL error: {e.reason}")
        except Exception as e:
            node.get_logger().warn(f"Depth ingest error: {e}")

    node.create_subscription(
        CompressedImage,
        "/da3/depth_colored",
        callback,
        10,
    )
    node.get_logger().info(f"Depth relay started: /da3/depth_colored -> {ingest_url}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
    sys.exit(0)
