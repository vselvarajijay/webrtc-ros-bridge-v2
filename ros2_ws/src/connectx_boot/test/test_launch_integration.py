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

"""Minimal integration test: launch file is valid and loadable by ros2 launch."""

import subprocess
import pytest


def test_launch_file_show_args() -> None:
    """Run ros2 launch --show-args to verify the launch file is found and valid."""
    result = subprocess.run(
        ["ros2", "launch", "connectx_boot", "connectx.launch.py", "--show-args"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"ros2 launch failed: stderr={result.stderr!r} stdout={result.stdout!r}"
    )
