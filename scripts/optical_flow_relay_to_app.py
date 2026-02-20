#!/usr/bin/env python3
"""
Relay optical flow images from ROS2 /optical_flow/image/compressed to the app's
POST /api/optical_flow_image_ingest.

Run in an environment where ROS2 sees the topic (e.g. scout_bridge container
where optical_flow_node runs). The app must be reachable at APP_URL.

Usage:
  source /opt/ros/kilted/setup.bash
  source /root/workspace/ros2_ws/install/setup.bash  # if needed
  APP_URL=http://app:8000 python3 scripts/optical_flow_relay_to_app.py

Env:
  APP_URL  Base URL of the app (e.g. http://app:8000 in Docker, http://127.0.0.1:8000 on host)
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
    ingest_url = f"{app_url}/api/optical_flow_image_ingest"

    rclpy.init()
    node = Node("optical_flow_relay_to_app")

    def callback(msg: CompressedImage):
        try:
            stamp = msg.header.stamp
            frame_time = stamp.sec + stamp.nanosec * 1e-9
            req = urllib.request.Request(
                ingest_url,
                data=bytes(msg.data),
                method="POST",
                headers={
                    "Content-Type": "image/jpeg",
                    "X-Depth-Frame-Time": str(frame_time),
                },
            )
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            node.get_logger().warn(f"Optical flow ingest HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            node.get_logger().warn(f"Optical flow ingest URL error: {e.reason}")
        except Exception as e:
            node.get_logger().warn(f"Optical flow ingest error: {e}")

    node.create_subscription(
        CompressedImage,
        "/optical_flow/image/compressed",
        callback,
        10,
    )
    node.get_logger().info(
        f"Optical flow relay started: /optical_flow/image/compressed -> {ingest_url}"
    )
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
