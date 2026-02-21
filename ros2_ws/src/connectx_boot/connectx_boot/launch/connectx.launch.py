import logging
from launch import LaunchDescription
from launch_ros.actions import Node

logger = logging.getLogger('launch')


def generate_launch_description():
    logger.info('ConnectX boot launch file loading')
    return LaunchDescription([
        Node(
            package='connectx_perception_cpp',
            executable='floor_mask_node',
            name='floor_mask_node',
        ),
        Node(
            package='connectx_perception_cpp',
            executable='optical_flow_node',
            name='optical_flow_node',
        ),
        Node(
            package='connectx_planner',
            executable='world_model_node',
            name='world_model_node',
        ),
        Node(
            package='connectx_planner',
            executable='wander_node',
            name='wander_node',
        ),
    ])