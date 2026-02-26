#!/usr/bin/env python3
"""
Subscribe to the bridged model pose (from Gazebo PosePublisher) and publish
world -> chassis and chassis -> box_car to /tf so Foxglove 3D shows the robot
moving in the world frame. The box_car frame (identity from chassis) exists so
clients that expect the Gazebo model name as a frame can resolve it.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster


def main(args=None):
    rclpy.init(args=args)
    node = Node("pose_to_tf")
    broadcaster = TransformBroadcaster(node)

    def cb(msg: PoseStamped):
        # world -> chassis (robot base in world)
        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "world"
        t.child_frame_id = "chassis"
        t.transform.translation.x = msg.pose.position.x
        t.transform.translation.y = msg.pose.position.y
        t.transform.translation.z = msg.pose.position.z
        t.transform.rotation.x = msg.pose.orientation.x
        t.transform.rotation.y = msg.pose.orientation.y
        t.transform.rotation.z = msg.pose.orientation.z
        t.transform.rotation.w = msg.pose.orientation.w
        broadcaster.sendTransform(t)
        # chassis -> box_car (identity so "box_car" frame exists for clients using model name)
        t2 = TransformStamped()
        t2.header.stamp = msg.header.stamp
        t2.header.frame_id = "chassis"
        t2.child_frame_id = "box_car"
        t2.transform.translation.x = 0.0
        t2.transform.translation.y = 0.0
        t2.transform.translation.z = 0.0
        t2.transform.rotation.x = 0.0
        t2.transform.rotation.y = 0.0
        t2.transform.rotation.z = 0.0
        t2.transform.rotation.w = 1.0
        broadcaster.sendTransform(t2)

    node.create_subscription(PoseStamped, "/model_pose", cb, 10)
    node.get_logger().info(
        "pose_to_tf: subscribing to /model_pose, publishing world->chassis and chassis->box_car to /tf"
    )
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
