import logging
from launch import LaunchDescription
from launch_ros.actions import Node

logger = logging.getLogger('launch')

def generate_launch_description():
    logger.info('Scout boot launch file loading')
    return LaunchDescription([
        # Add nodes here as you create them        
    ])