import os

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header

from scout_robot_bridge.robot_factory import create_robot

# Mapping: ROS 2 parameter name (FRODOBOT_*) -> SDK env var name
FRODOBOT_PARAM_TO_ENV = {
    'FRODOBOT_SDK_API_TOKEN': 'SDK_API_TOKEN',
    'FRODOBOT_BOT_SLUG': 'BOT_SLUG',
    'FRODOBOT_CHROME_EXECUTABLE_PATH': 'CHROME_EXECUTABLE_PATH',
    'FRODOBOT_MAP_ZOOM_LEVEL': 'MAP_ZOOM_LEVEL',
    'FRODOBOT_MISSION_SLUG': 'MISSION_SLUG',
}


def main(args=None):
    rclpy.init(args=args)
    node = Node('bridge_node')

    node.declare_parameter('robot_type', 'earth-rovers-sdk')
    robot_type = node.get_parameter('robot_type').value

    if robot_type == 'earth-rovers-sdk':
        for ros_param, sdk_env in FRODOBOT_PARAM_TO_ENV.items():
            default = '18' if sdk_env == 'MAP_ZOOM_LEVEL' else ''
            node.declare_parameter(ros_param, default)
            value = node.get_parameter(ros_param).value
            value_str = str(value).strip()
            # Use param when non-empty; else use FRODOBOT_* from env (e.g. .env) so SDK gets CHROME_EXECUTABLE_PATH etc.
            if value_str:
                os.environ[sdk_env] = value_str
            elif os.environ.get(ros_param):
                os.environ[sdk_env] = str(os.environ.get(ros_param)).strip()

    robot = create_robot(robot_type)
    node.robot = robot
    if robot is None:
        node.get_logger().warn('Unknown robot_type "%s"; running without robot.', robot_type)

    # Control: /cmd_vel -> discrete move commands
    node.declare_parameter('cmd_vel_threshold', 0.1)
    threshold = node.get_parameter('cmd_vel_threshold').value

    def on_cmd_vel(msg: Twist) -> None:
        # Log every cmd_vel so we can see when control commands arrive
        node.get_logger().info(
            'cmd_vel received: linear.x=%.2f angular.z=%.2f' % (msg.linear.x, msg.angular.z),
        )
        if node.robot is None:
            node.get_logger().warn('cmd_vel received but no robot (robot is None); check auth/env.')
            return
        linear_x = msg.linear.x
        angular_z = msg.angular.z
        if linear_x > threshold:
            node.robot.move_forward()
            node.get_logger().info('cmd_vel: forward')
        elif linear_x < -threshold:
            node.robot.move_backward()
            node.get_logger().info('cmd_vel: backward')
        elif angular_z > threshold:
            node.robot.move_right()
            node.get_logger().info('cmd_vel: right')
        elif angular_z < -threshold:
            node.robot.move_left()
            node.get_logger().info('cmd_vel: left')

    node.create_subscription(Twist, '/cmd_vel', on_cmd_vel, 10)
    node.get_logger().info('Subscribed to /cmd_vel (threshold=%.2f); bridge ready.' % threshold)

    # Video: timer -> get_front_camera_frame -> /camera/front/compressed
    node.declare_parameter('camera_publish_rate', 5.0)
    camera_rate = node.get_parameter('camera_publish_rate').value
    image_format = os.getenv('IMAGE_FORMAT', 'png')

    camera_pub = node.create_publisher(
        CompressedImage,
        '/camera/front/compressed',
        10,
    )

    def on_camera_timer() -> None:
        if node.robot is None:
            return
        frame = node.robot.get_front_camera_frame()
        if frame is None:
            return
        msg = CompressedImage()
        msg.header = Header()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_front'
        msg.format = image_format
        msg.data = list(frame)
        camera_pub.publish(msg)

    node.create_timer(1.0 / camera_rate, on_camera_timer)

    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
