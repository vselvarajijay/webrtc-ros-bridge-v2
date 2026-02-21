# Copyright 2025 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pytest

import rclpy
from rclpy.node import Node

from connectx_robot_bridge.core.config_manager import ConfigManager
from connectx_robot_bridge.core.constants import DEFAULT_MAP_ZOOM_LEVEL, DEFAULT_ROBOT_TYPE


@pytest.fixture
def rclpy_node():
    rclpy.init()
    node = Node("test_config_node")
    yield node
    node.destroy_node()
    rclpy.shutdown()


def test_setup_robot_config_returns_robot_type(rclpy_node: Node) -> None:
    robot_type = ConfigManager.setup_robot_config(rclpy_node)
    assert robot_type == DEFAULT_ROBOT_TYPE
    assert rclpy_node.get_parameter("robot_type").value == "earth_rovers_sdk"


def test_setup_frodobot_config_sets_map_zoom_env(rclpy_node: Node) -> None:
    # Save and restore MAP_ZOOM_LEVEL to avoid polluting env
    old = os.environ.get("MAP_ZOOM_LEVEL")
    try:
        ConfigManager.setup_frodobot_config(rclpy_node)
        assert os.environ.get("MAP_ZOOM_LEVEL") == DEFAULT_MAP_ZOOM_LEVEL
    finally:
        if old is not None:
            os.environ["MAP_ZOOM_LEVEL"] = old
        elif "MAP_ZOOM_LEVEL" in os.environ:
            del os.environ["MAP_ZOOM_LEVEL"]


def test_setup_frodobot_config_declares_parameters(rclpy_node: Node) -> None:
    ConfigManager.setup_frodobot_config(rclpy_node)
    assert rclpy_node.has_parameter("FRODOBOT_MAP_ZOOM_LEVEL")
    assert rclpy_node.has_parameter("FRODOBOT_SDK_API_TOKEN")
