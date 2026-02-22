import json
import os
import threading
import time
from dataclasses import asdict

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header, Int32, String

from connectx_robot_bridge.core.cmd_vel_mapping import twist_to_sdk_normalized
from connectx_robot_bridge.core.config_manager import ConfigManager
from connectx_robot_bridge.core.constants import (
    CAMERA_FRAME_ID,
    CAMERA_FRONT_COMPRESSED_TOPIC,
    CAMERA_FRONT_FULL_COMPRESSED_TOPIC,
    CMD_VEL_TOPIC,
    LAMP_TOPIC,
    DEFAULT_CAMERA_FULL_PUBLISH_RATE,
    DEFAULT_CAMERA_PUBLISH_RATE,
    DEFAULT_IMAGE_FORMAT,
    DEFAULT_MAX_ANGULAR_SPEED,
    DEFAULT_MAX_LINEAR_SPEED,
    DEFAULT_TELEMETRY_PUBLISH_RATE,
    ROBOT_TELEMETRY_TOPIC,
)
from connectx_robot_bridge.core.robot_base import RobotBase
from connectx_robot_bridge.core.robot_factory import create_robot


def setup_cmd_vel_subscriber(node: Node, robot: RobotBase, last_lamp_ref: list) -> None:
    """
    Set up cmd_vel subscriber for robot control.

    Uses last_lamp_ref[0] so every velocity command is sent with the latest lamp state.

    Args:
    ----
    node : Node
        ROS 2 node
    robot : RobotBase
        Robot instance to control
    last_lamp_ref : list
        Single-element list holding last lamp value (0 or 1) from /robot/lamp

    """
    node.declare_parameter('max_linear_speed', DEFAULT_MAX_LINEAR_SPEED)
    node.declare_parameter('max_angular_speed', DEFAULT_MAX_ANGULAR_SPEED)
    max_linear = node.get_parameter('max_linear_speed').value
    max_angular = node.get_parameter('max_angular_speed').value
    last_cmd_vel_log = [0.0]
    cmd_vel_log_count = [0]
    rtm_first_ok_logged = [False]
    last_rtm_fail_log = [0.0]
    CMD_VEL_LOG_INTERVAL = 2.0
    CMD_VEL_LOG_FIRST_N = 3  # log first N non-zero cmd_vel immediately so operator sees response
    RTM_FAIL_LOG_INTERVAL = 5.0

    def on_cmd_vel(msg: Twist) -> None:
        if robot is None:
            now = time.monotonic()
            if now - last_cmd_vel_log[0] >= CMD_VEL_LOG_INTERVAL:
                last_cmd_vel_log[0] = now
                node.get_logger().error(
                    'cmd_vel received but no robot (robot is None). '
                    'Set SDK_API_TOKEN and BOT_SLUG in .env and ensure bridge can authenticate.'
                )
            return
        # Apply latest lamp state so this velocity command carries it to the SDK
        if hasattr(robot, 'set_lamp'):
            robot.set_lamp(last_lamp_ref[0])

        # Convert ROS Twist to Frodobots SDK format
        linear_x = msg.linear.x
        angular_z = msg.angular.z
        linear_normalized, angular_normalized = twist_to_sdk_normalized(
            linear_x, angular_z, max_linear, max_angular
        )

        # Send continuous velocity command for smooth control (includes lamp via set_lamp above)
        rtm_ok = robot.send_velocity(linear_normalized, angular_normalized)
        if rtm_ok and not rtm_first_ok_logged[0]:
            rtm_first_ok_logged[0] = True
            node.get_logger().info(
                'RTM send OK: velocity commands accepted by Agora. '
                'If robot does not move, ensure robot/SDK is in the same channel.'
            )
        if not rtm_ok and (abs(linear_x) > 0.01 or abs(angular_z) > 0.01):
            now = time.monotonic()
            if now - last_rtm_fail_log[0] >= RTM_FAIL_LOG_INTERVAL:
                last_rtm_fail_log[0] = now
                node.get_logger().warning(
                    'RTM send failed: Agora API or network error. '
                    'Check RTM_TOKEN, BOT_UID, and that robot is online and in channel.'
                )

        # Log so operators see commands reaching the bridge
        # (first few immediately, then rate-limited)
        if abs(linear_x) > 0.01 or abs(angular_z) > 0.01:
            now = time.monotonic()
            should_log = (
                cmd_vel_log_count[0] < CMD_VEL_LOG_FIRST_N
                or (now - last_cmd_vel_log[0] >= CMD_VEL_LOG_INTERVAL)
            )
            if should_log:
                cmd_vel_log_count[0] += 1
                last_cmd_vel_log[0] = now
                node.get_logger().info(
                    f'cmd_vel -> robot: linear={linear_x:.2f} (n={linear_normalized:.2f}) '
                    f'angular={angular_z:.2f} (n={angular_normalized:.2f})'
                )

    node.create_subscription(Twist, CMD_VEL_TOPIC, on_cmd_vel, 10)
    node.get_logger().info(
        f'Subscribed to {CMD_VEL_TOPIC} '
        f'(max_linear={max_linear:.2f}, max_angular={max_angular:.2f}); ready.'
    )


def setup_lamp_subscriber(node: Node, robot: RobotBase, last_lamp_ref: list) -> None:
    """
    Set up lamp state subscriber.

    Store latest lamp (0=off, 1=on) in last_lamp_ref; cmd_vel applies it to SDK.
    """
    def on_lamp(msg: Int32) -> None:
        last_lamp_ref[0] = 1 if msg.data else 0
        if robot is not None and hasattr(robot, 'set_lamp'):
            robot.set_lamp(last_lamp_ref[0])

    node.create_subscription(Int32, LAMP_TOPIC, on_lamp, 10)
    node.get_logger().info(f'Subscribed to {LAMP_TOPIC} for lamp control.')


def setup_camera_publisher(node: Node, robot: RobotBase) -> None:
    """
    Set up camera publisher for front camera feed.

    When camera_use_stream is True, runs a thread from get_front_camera_stream();
    otherwise uses a timer at camera_publish_rate.
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

    frame_counter_ref = [0]

    def on_camera_timer() -> None:
        if robot is None:
            return
        try:
            result = robot.get_front_camera_frame()
            if result is None:
                return
            if isinstance(result, tuple):
                frame_bytes, metrics = result
            else:
                frame_bytes, metrics = result, {}
            frame_counter_ref[0] += 1
            msg = CompressedImage()
            msg.header = Header()
            msg.header.stamp = node.get_clock().now().to_msg()
            c, f = metrics.get('capture_ms', 0), metrics.get('fetch_ms', 0)
            fid = frame_counter_ref[0]
            msg.header.frame_id = f"{CAMERA_FRAME_ID}_{fid}_{c:.2f}_{f:.2f}"
            msg.format = image_format
            msg.data = list(frame_bytes)
            camera_pub.publish(msg)
        except Exception as e:
            node.get_logger().debug(f'Failed to get camera frame: {e}')

    if camera_use_stream and robot is not None:
        stop_event = threading.Event()
        node._camera_stop_event = stop_event

        def camera_stream_loop() -> None:
            none_count = 0
            no_frame_logged = [False]
            for result in robot.get_front_camera_stream(stop_event):
                if result is None:
                    none_count += 1
                    if none_count >= 50 and not no_frame_logged[0]:
                        no_frame_logged[0] = True
                        node.get_logger().warning(
                            "No camera frames from SDK after 50 attempts. "
                            "Check SDK running and auth/channel configured."
                        )
                    continue
                none_count = 0
                try:
                    if isinstance(result, tuple):
                        frame_bytes, metrics = result
                    else:
                        frame_bytes, metrics = result, {}
                    frame_counter_ref[0] += 1
                    msg = CompressedImage()
                    msg.header = Header()
                    msg.header.stamp = node.get_clock().now().to_msg()
                    c, f = metrics.get('capture_ms', 0), metrics.get('fetch_ms', 0)
                    fid = frame_counter_ref[0]
                    msg.header.frame_id = f"{CAMERA_FRAME_ID}_{fid}_{c:.2f}_{f:.2f}"
                    msg.format = image_format
                    msg.data = list(frame_bytes)
                    camera_pub.publish(msg)
                except Exception as e:
                    node.get_logger().debug(f'Failed to publish camera frame: {e}')

        thread = threading.Thread(target=camera_stream_loop, daemon=True)
        thread.start()
        node.get_logger().info('Camera publishing from stream (max rate).')
    else:
        node.create_timer(1.0 / camera_rate, on_camera_timer)


def setup_camera_full_publisher(node: Node, robot: RobotBase) -> None:
    """
    Publish full-resolution (viewport) front camera on a separate topic at a low rate.

    Only active if the robot implements get_front_camera_frame_full().
    """
    if robot is None or not hasattr(robot, 'get_front_camera_frame_full'):
        return
    node.declare_parameter('camera_full_publish_rate', DEFAULT_CAMERA_FULL_PUBLISH_RATE)
    full_rate = node.get_parameter('camera_full_publish_rate').value
    image_format = os.getenv('IMAGE_FORMAT', DEFAULT_IMAGE_FORMAT)

    camera_full_pub = node.create_publisher(
        CompressedImage,
        CAMERA_FRONT_FULL_COMPRESSED_TOPIC,
        10,
    )
    frame_counter_ref = [0]

    def on_camera_full_timer() -> None:
        try:
            result = robot.get_front_camera_frame_full()
            if result is None:
                return
            if isinstance(result, tuple):
                frame_bytes, metrics = result
            else:
                frame_bytes, metrics = result, {}
            frame_counter_ref[0] += 1
            msg = CompressedImage()
            msg.header = Header()
            msg.header.stamp = node.get_clock().now().to_msg()
            c, f = metrics.get('capture_ms', 0), metrics.get('fetch_ms', 0)
            msg.header.frame_id = f"{CAMERA_FRAME_ID}_full_{frame_counter_ref[0]}_{c:.2f}_{f:.2f}"
            msg.format = image_format
            msg.data = list(frame_bytes)
            camera_full_pub.publish(msg)
        except Exception as e:
            node.get_logger().debug(f'Failed to get full camera frame: {e}')

    node.create_timer(1.0 / full_rate, on_camera_full_timer)
    node.get_logger().info(
        f'Publishing full-res camera on {CAMERA_FRONT_FULL_COMPRESSED_TOPIC} at {full_rate} Hz'
    )


def setup_telemetry_publisher(node: Node, robot: RobotBase) -> None:
    """Set up telemetry publisher for robot sensor data (velocity, battery, GPS, IMU)."""
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
    """Run the bridge node (entry point)."""
    rclpy.init(args=args)
    node = Node('bridge_node')

    try:
        # Set up robot configuration
        robot_type = ConfigManager.setup_robot_config(node)

        # Create robot instance
        robot = create_robot(robot_type)
        node.robot = robot
        if robot is None:
            node.get_logger().error(
                f'Unknown robot_type "{robot_type}"; running without robot.'
            )
        else:
            rtm_ok = getattr(robot, '_rtm_client', None) is not None
            if rtm_ok:
                node.get_logger().info(
                    'Robot control ready (RTM client initialized).'
                )
            else:
                node.get_logger().error(
                    'RTM client not initialized. Set SDK_API_TOKEN and BOT_SLUG in .env.'
                )

        # Shared ref so cmd_vel always sends with latest lamp (0=off, 1=on)
        last_lamp_ref = [0]

        # Set up subscribers and publishers
        setup_cmd_vel_subscriber(node, robot, last_lamp_ref)
        setup_lamp_subscriber(node, robot, last_lamp_ref)
        setup_camera_publisher(node, robot)
        setup_camera_full_publisher(node, robot)
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
