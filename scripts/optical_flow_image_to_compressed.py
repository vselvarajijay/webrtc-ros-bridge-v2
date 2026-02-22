#!/usr/bin/env python3
"""
Subscribe to /optical_flow_nav/debug_flow_image (sensor_msgs/Image), encode to JPEG,
and publish to /optical_flow/image/compressed so the existing optical_flow_relay_to_app
and app API continue to work unchanged.

Run in the same ROS2 environment as optical_flow_nav (e.g. connectx_bridge).
Requires opencv (cv2).
"""

import sys

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image


def main():
    rclpy.init()
    node = Node("optical_flow_image_to_compressed")

    pub = node.create_publisher(
        CompressedImage,
        "/optical_flow/image/compressed",
        10,
    )

    def callback(msg: Image):
        try:
            h, w = msg.height, msg.width
            step = msg.step
            buf = np.frombuffer(msg.data, dtype=np.uint8)
            if buf.size < h * step:
                return
            if msg.encoding in ("bgr8", "rgb8"):
                # step may have row padding
                if step == w * 3:
                    img = buf[: h * step].reshape((h, w, 3))
                else:
                    img = buf.reshape((h, step))[:, : w * 3].reshape((h, w, 3))
                if msg.encoding == "rgb8":
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif msg.encoding == "mono8":
                img = buf.reshape((h, step))[:, :w].copy()
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            else:
                node.get_logger().warn(f"Unhandled encoding: {msg.encoding}")
                return
            _, jpeg = cv2.imencode(".jpg", img)
            out = CompressedImage()
            out.header = msg.header
            out.format = "jpeg"
            out.data = jpeg.tobytes()
            pub.publish(out)
        except Exception as e:
            node.get_logger().warn(f"Encode/publish error: {e}")

    node.create_subscription(
        Image,
        "/optical_flow_nav/debug_flow_image",
        callback,
        10,
    )
    node.get_logger().info(
        "optical_flow_image_to_compressed: /optical_flow_nav/debug_flow_image -> /optical_flow/image/compressed"
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
