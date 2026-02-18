import json
import os
import threading
from dataclasses import asdict

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header, String

from scout_robot_bridge.core.config_manager import ConfigManager
from scout_robot_bridge.core.constants import (
    CAMERA_FRAME_ID,
    CAMERA_FRONT_COMPRESSED_TOPIC,
    CMD_VEL_TOPIC,
    DEFAULT_CAMERA_PUBLISH_RATE,
    DEFAULT_IMAGE_FORMAT,
    DEFAULT_MAX_ANGULAR_SPEED,
    DEFAULT_MAX_LINEAR_SPEED,
    DEFAULT_TELEMETRY_PUBLISH_RATE,
    MAX_VELOCITY,
    MIN_VELOCITY,
    ROBOT_TELEMETRY_TOPIC,
)
from scout_robot_bridge.core.robot_base import RobotBase
from scout_robot_bridge.core.robot_factory import create_robot


def setup_cmd_vel_subscriber(node: Node, robot: RobotBase) -> None:
    """
    Set up cmd_vel subscriber for robot control.
    
    Args:
        node: ROS 2 node
        robot: Robot instance to control
    """
    node.declare_parameter('max_linear_speed', DEFAULT_MAX_LINEAR_SPEED)
    node.declare_parameter('max_angular_speed', DEFAULT_MAX_ANGULAR_SPEED)
    max_linear = node.get_parameter('max_linear_speed').value
    max_angular = node.get_parameter('max_angular_speed').value

    def on_cmd_vel(msg: Twist) -> None:
        if robot is None:
            node.get_logger().warn('cmd_vel received but no robot (robot is None); check auth/env.')
            return
        
        # Convert ROS Twist to Frodobots SDK format
        # ROS linear.x: forward/backward (m/s), angular.z: rotation (rad/s)
        # Frodobots: linear: -1.0 to 1.0, angular: -1.0 to 1.0
        linear_x = msg.linear.x
        angular_z = msg.angular.z
        
        # Normalize to [-1.0, 1.0] range using max speeds
        linear_normalized = (
            max(MIN_VELOCITY, min(MAX_VELOCITY, linear_x / max_linear))
            if max_linear > 0 else 0.0
        )
        angular_normalized = (
            max(MIN_VELOCITY, min(MAX_VELOCITY, angular_z / max_angular))
            if max_angular > 0 else 0.0
        )
        
        # Send continuous velocity command for smooth control
        robot.send_velocity(linear_normalized, angular_normalized)
        
        # Log periodically (not every message to reduce spam)
        if abs(linear_x) > 0.01 or abs(angular_z) > 0.01:
            node.get_logger().debug(
                f'cmd_vel: linear={linear_x:.2f} (norm={linear_normalized:.2f}) '
                f'angular={angular_z:.2f} (norm={angular_normalized:.2f})'
            )

    node.create_subscription(Twist, CMD_VEL_TOPIC, on_cmd_vel, 10)
    node.get_logger().info(
        f'Subscribed to {CMD_VEL_TOPIC} '
        f'(max_linear={max_linear:.2f}, max_angular={max_angular:.2f}); bridge ready.'
    )


def setup_camera_publisher(node: Node, robot: RobotBase) -> None:
    """
    Set up camera publisher for front camera feed.
    When camera_use_stream is True, runs a dedicated thread that pulls from
    get_front_camera_stream() and publishes every frame; otherwise uses a timer at camera_publish_rate.
    """
    node.declare_parameter('camera_publish_rate', DEFAULT_CAMERA_PUBLISH_RATE)
    node.declare_parameter('camera_use_stream', True)
    camera_rate = node.get_parameter('camera_publish_rate').value
    camera_use_stream = node.get_parameter('camera_use_stream').value
    image_format = os.getenv('IMAGE_FORMAT', DEFAULT_IMAGE_FORMAT)

    camera_pub = node.create_publisher(
        CompressedImage,
        CAMERA_FRONT_COMPRESSED_TOPIC,
        10,
    )

    def on_camera_timer() -> None:
        if robot is None:
            return
        try:
            frame = robot.get_front_camera_frame()
            if frame is None:
                return
            msg = CompressedImage()
            msg.header = Header()
            msg.header.stamp = node.get_clock().now().to_msg()
            msg.header.frame_id = CAMERA_FRAME_ID
            msg.format = image_format
            msg.data = list(frame)
            camera_pub.publish(msg)
        except Exception as e:
            node.get_logger().debug(f'Failed to get camera frame: {e}')

    if camera_use_stream and robot is not None:
        stop_event = threading.Event()
        node._camera_stop_event = stop_event

        def camera_stream_loop() -> None:
            for frame in robot.get_front_camera_stream(stop_event):
                if frame is None:
                    continue
                try:
                    msg = CompressedImage()
                    msg.header = Header()
                    msg.header.stamp = node.get_clock().now().to_msg()
                    msg.header.frame_id = CAMERA_FRAME_ID
                    msg.format = image_format
                    msg.data = list(frame)
                    camera_pub.publish(msg)
                except Exception as e:
                    node.get_logger().debug(f'Failed to publish camera frame: {e}')

        thread = threading.Thread(target=camera_stream_loop, daemon=True)
        thread.start()
        node.get_logger().info('Camera publishing from stream (max rate).')
    else:
        node.create_timer(1.0 / camera_rate, on_camera_timer)


def setup_telemetry_publisher(node: Node, robot: RobotBase) -> None:
    """
    Set up telemetry publisher for robot sensor data (velocity, battery, GPS, IMU, etc.).
    """
    node.declare_parameter('telemetry_publish_rate', DEFAULT_TELEMETRY_PUBLISH_RATE)
    telemetry_rate = node.get_parameter('telemetry_publish_rate').value
    telemetry_pub = node.create_publisher(String, ROBOT_TELEMETRY_TOPIC, 10)

    def on_telemetry_timer() -> None:
        if robot is None:
            return
        try:
            telemetry = robot.get_telemetry()
            if telemetry is None:
                return
            msg = String()
            msg.data = json.dumps(asdict(telemetry))
            telemetry_pub.publish(msg)
        except Exception as e:
            node.get_logger().debug(f'Failed to get telemetry: {e}')

    node.create_timer(1.0 / telemetry_rate, on_telemetry_timer)
    node.get_logger().info(
        f'Publishing telemetry on {ROBOT_TELEMETRY_TOPIC} at {telemetry_rate} Hz'
    )


def main(args=None):
    """Main entry point for bridge node."""
    rclpy.init(args=args)
    node = Node('bridge_node')

    try:
        # Set up robot configuration
        robot_type = ConfigManager.setup_robot_config(node)
        
        # Create robot instance
        robot = create_robot(robot_type)
        node.robot = robot
        if robot is None:
            node.get_logger().warn(
                f'Unknown robot_type "{robot_type}"; running without robot.'
            )

        # Set up subscribers and publishers
        setup_cmd_vel_subscriber(node, robot)
        setup_camera_publisher(node, robot)
        setup_telemetry_publisher(node, robot)

        # Run node
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            node.get_logger().info("Received interrupt signal, shutting down...")
        except Exception as e:
            node.get_logger().error(f"Error during spin: {e}")
    finally:
        # Cleanup
        try:
            if hasattr(node, '_camera_stop_event'):
                node._camera_stop_event.set()
            if hasattr(node, 'robot') and node.robot is not None:
                if hasattr(node.robot, 'cleanup'):
                    node.robot.cleanup()
            node.destroy_node()
        except Exception as e:
            node.get_logger().warning(f"Error during node cleanup: {e}")
        finally:
            try:
                rclpy.shutdown()
            except Exception:
                pass  # Ignore shutdown errors if already shut down


if __name__ == '__main__':
    main()
