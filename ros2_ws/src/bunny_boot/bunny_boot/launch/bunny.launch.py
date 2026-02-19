import logging
from launch import LaunchDescription
from launch_ros.actions import Node

logger = logging.getLogger('launch')

def generate_launch_description():
    logger.info('Bunny boot launch file loading')
    # Placeholder for future use: add bridge_node, webrtc_node, etc. when needed.
    return LaunchDescription([
    ])