"""Configuration management for scout_robot_bridge."""

import os
from typing import Optional

from rclpy.node import Node

from scout_robot_bridge.core.constants import DEFAULT_MAP_ZOOM_LEVEL

# Mapping: ROS 2 parameter name (FRODOBOT_*) -> SDK env var name
FRODOBOT_PARAM_TO_ENV = {
    "FRODOBOT_SDK_API_TOKEN": "SDK_API_TOKEN",
    "FRODOBOT_BOT_SLUG": "BOT_SLUG",
    "FRODOBOT_CHROME_EXECUTABLE_PATH": "CHROME_EXECUTABLE_PATH",
    "FRODOBOT_MAP_ZOOM_LEVEL": "MAP_ZOOM_LEVEL",
    "FRODOBOT_MISSION_SLUG": "MISSION_SLUG",
}


class ConfigManager:
    """Manages ROS parameter to environment variable mapping for robot SDKs."""

    @staticmethod
    def setup_frodobot_config(node: Node) -> None:
        """
        Configure environment variables from ROS parameters for FrodoBot SDK.
        
        For each FRODOBOT_* parameter:
        1. Declare the parameter with appropriate default
        2. Get the parameter value
        3. If non-empty, set the corresponding SDK env var
        4. If empty but FRODOBOT_* env var exists, use that instead
        
        Args:
            node: ROS 2 node to declare parameters on
        """
        for ros_param, sdk_env in FRODOBOT_PARAM_TO_ENV.items():
            default = DEFAULT_MAP_ZOOM_LEVEL if sdk_env == "MAP_ZOOM_LEVEL" else ""
            node.declare_parameter(ros_param, default)
            value = node.get_parameter(ros_param).value
            value_str = str(value).strip()
            
            # Use param when non-empty; else use FRODOBOT_* from env (e.g. .env)
            # so SDK gets CHROME_EXECUTABLE_PATH etc.
            if value_str:
                os.environ[sdk_env] = value_str
            elif os.environ.get(ros_param):
                os.environ[sdk_env] = str(os.environ.get(ros_param)).strip()
