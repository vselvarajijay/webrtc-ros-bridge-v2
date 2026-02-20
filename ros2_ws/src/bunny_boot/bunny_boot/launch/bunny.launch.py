import logging
from launch import LaunchDescription
from launch_ros.actions import Node

logger = logging.getLogger('launch')


def generate_launch_description():
    logger.info('Bunny boot launch file loading')
    return LaunchDescription([
        Node(
            package='bunny_perception_cpp',
            executable='floor_mask_node',
            name='floor_mask_node',
        ),
        Node(
            package='bunny_perception_cpp',
            executable='optical_flow_node',
            name='optical_flow_node',
        ),
        Node(
            package='bunny_controller',
            executable='wander_node',
            name='wander_node',
        ),
    ])