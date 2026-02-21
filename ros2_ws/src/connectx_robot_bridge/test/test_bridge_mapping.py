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

import json
import pytest
from dataclasses import asdict

from connectx_robot_bridge.core.cmd_vel_mapping import twist_to_sdk_normalized
from connectx_robot_bridge.core.models.telemetry import TelemetryFrame


@pytest.mark.unit
def test_twist_to_sdk_normalized_zero() -> None:
    lin, ang = twist_to_sdk_normalized(0.0, 0.0, 0.5, 0.8)
    assert lin == 0.0
    assert ang == 0.0


@pytest.mark.unit
def test_twist_to_sdk_normalized_full_forward() -> None:
    lin, ang = twist_to_sdk_normalized(0.5, 0.0, 0.5, 0.8)
    assert lin == 1.0
    assert ang == 0.0


@pytest.mark.unit
def test_twist_to_sdk_normalized_clamped() -> None:
    lin, ang = twist_to_sdk_normalized(2.0, 2.0, 0.5, 0.8)
    assert lin == 1.0
    assert ang == 1.0

    lin, ang = twist_to_sdk_normalized(-1.0, -1.0, 0.5, 0.8)
    assert lin == -1.0
    assert ang == -1.0


@pytest.mark.unit
def test_twist_to_sdk_normalized_scaling() -> None:
    lin, ang = twist_to_sdk_normalized(0.25, 0.4, 0.5, 0.8)
    assert abs(lin - 0.5) < 1e-6
    assert abs(ang - 0.5) < 1e-6


@pytest.mark.unit
def test_twist_to_sdk_normalized_zero_max_speeds() -> None:
    lin, ang = twist_to_sdk_normalized(0.1, 0.1, 0.0, 0.0)
    assert lin == 0.0
    assert ang == 0.0


@pytest.mark.unit
def test_telemetry_json_roundtrip_speed() -> None:
    """TelemetryFrame serializes to JSON that contains 'speed'; parsing yields same value."""
    frame = TelemetryFrame(
        battery=85.0,
        signal_level=4,
        speed=0.35,
        lamp=0,
        latitude=37.0,
        longitude=-122.0,
        gps_signal=15.0,
        orientation=90,
    )
    data = asdict(frame)
    msg = json.dumps(data)
    parsed = json.loads(msg)
    assert parsed["speed"] == 0.35
    assert parsed["battery"] == 85.0
    assert parsed["orientation"] == 90
