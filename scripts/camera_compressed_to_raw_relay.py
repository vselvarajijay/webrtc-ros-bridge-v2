#!/usr/bin/env python3
"""
Relay camera from /camera/front/compressed (CompressedImage) to /camera/image_raw (Image).

Used so optical_flow_nav (which expects raw Image on /camera/image_raw) can run
against the ConnectX camera topic. Run in the same ROS2 environment as the camera
and optical_flow_nav node (e.g. connectx_bridge). Uses OpenCV only (no cv_bridge).

Usage:
  source /opt/ros/kilted/setup.bash
  source /root/workspace/ros2_ws/install/setup.bash
  python3 scripts/camera_compressed_to_raw_relay.py
"""

import sys

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image


def main():
    rclpy.init()
    node = Node("camera_compressed_to_raw_relay")

    def callback(msg: CompressedImage):
        try:
            buf = np.frombuffer(msg.data, dtype=np.uint8)
            cv_image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if cv_image is None:
                node.get_logger().warn("Failed to decode JPEG")
                return
            h, w = cv_image.shape[:2]
            if len(cv_image.shape) == 3 and cv_image.shape[2] == 3:
                encoding = "bgr8"
                step = w * 3
            else:
                encoding = "mono8"
                step = w
            raw_msg = Image()
            raw_msg.header = msg.header
            raw_msg.height = h
            raw_msg.width = w
            raw_msg.encoding = encoding
            raw_msg.step = step
            raw_msg.is_bigendian = 0
            raw_msg.data = cv_image.tobytes()
            pub.publish(raw_msg)
        except Exception as e:
            node.get_logger().warn(f"Decode/publish error: {e}")

    pub = node.create_publisher(Image, "/camera/image_raw", 10)
    node.create_subscription(
        CompressedImage,
        "/camera/front/compressed",
        callback,
        10,
    )
    node.get_logger().info(
        "Camera relay started: /camera/front/compressed -> /camera/image_raw"
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
