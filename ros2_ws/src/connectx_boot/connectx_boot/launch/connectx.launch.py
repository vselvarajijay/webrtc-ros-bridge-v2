import logging
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

logger = logging.getLogger('launch')


def generate_launch_description():
    logger.info('ConnectX boot launch file loading')

    share_planner = get_package_share_directory('connectx_planner')
    share_controller = get_package_share_directory('connectx_controller')
    share_bridge = get_package_share_directory('connectx_robot_bridge')

    world_model_params = os.path.join(share_planner, 'config', 'world_model_params.yaml')
    wander_params = os.path.join(share_planner, 'config', 'wander_params.yaml')
    controller_params = os.path.join(share_controller, 'config', 'controller_params.yaml')
    frodobot_params = os.path.join(share_bridge, 'config', 'frodobot_params.yaml')

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
            parameters=[world_model_params],
        ),
        Node(
            package='connectx_planner',
            executable='wander_node',
            name='wander_node',
            parameters=[wander_params],
        ),
        Node(
            package='connectx_controller',
            executable='controller_node',
            name='controller_node',
            parameters=[controller_params],
        ),
        Node(
            package='connectx_robot_bridge',
            executable='bridge_node',
            name='bridge_node',
            parameters=[frodobot_params],
        ),
    ])
