#!/usr/bin/env python3
"""
Publish /robot_description with transient_local QoS so late-joining subscribers
(e.g. Foxglove Studio) receive the URDF and can render the 3D model.
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String


def main(args=None):
    rclpy.init(args=args)
    node = Node("robot_description_publisher")

    # Parameter is set by the launch file
    robot_description = node.declare_parameter("robot_description", "").value
    if not robot_description:
        node.get_logger().error("robot_description parameter is empty")
        rclpy.shutdown()
        return

    # Transient local so Foxglove and other late subscribers get the last message
    qos = QoSProfile(
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        reliability=ReliabilityPolicy.RELIABLE,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )
    msg = String()
    msg.data = robot_description

    # Standard topic (some Foxglove setups report "invalid topic" for this name)
    pub_std = node.create_publisher(String, "/robot_description", qos)
    pub_std.publish(msg)

    # Alternate topic so Foxglove custom layer can use /urdf/robot_description if /robot_description is rejected
    pub_urdf = node.create_publisher(String, "/urdf/robot_description", qos)
    pub_urdf.publish(msg)

    node.get_logger().info("Published /robot_description and /urdf/robot_description (transient_local)")

    def republish():
        pub_std.publish(msg)
        pub_urdf.publish(msg)

    timer = node.create_timer(2.0, republish)

    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
