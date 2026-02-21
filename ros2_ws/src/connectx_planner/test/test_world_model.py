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

import pytest

from connectx_planner.nodes.world_model_node import (
    parse_speed_and_angular_from_telemetry,
    parse_speed_from_telemetry,
    compute_risk_and_turn,
)

pytestmark = pytest.mark.unit


def test_parse_speed_empty_or_invalid() -> None:
    assert parse_speed_from_telemetry("") == 0.0
    assert parse_speed_from_telemetry("   ") == 0.0
    assert parse_speed_from_telemetry("nonsense") == 0.0
    assert parse_speed_and_angular_from_telemetry("") == (0.0, 0.0)
    assert parse_speed_and_angular_from_telemetry("  ") == (0.0, 0.0)
    assert parse_speed_and_angular_from_telemetry("not json") == (0.0, 0.0)
    assert parse_speed_and_angular_from_telemetry("[]") == (0.0, 0.0)


def test_parse_speed_valid_json() -> None:
    assert parse_speed_from_telemetry('{"speed": 0.5}') == 0.5
    assert parse_speed_from_telemetry('{"speed": 0.0}') == 0.0
    assert parse_speed_and_angular_from_telemetry('{"speed": 0.3, "angular_z": 0.1}') == (
        0.3,
        0.1,
    )
    assert parse_speed_and_angular_from_telemetry('{"speed": null}') == (0.0, 0.0)
    assert parse_speed_and_angular_from_telemetry('{"angular_z": -0.5}') == (0.0, -0.5)


def test_parse_speed_edge_cases() -> None:
    assert parse_speed_and_angular_from_telemetry("{}") == (0.0, 0.0)
    # String "0.5" is converted to float
    assert parse_speed_and_angular_from_telemetry('{"speed": "0.5"}') == (0.5, 0.0)
    # Invalid value yields 0
    assert parse_speed_and_angular_from_telemetry('{"speed": "abc"}') == (0.0, 0.0)


def test_compute_risk_and_turn_low_velocity_no_risk() -> None:
    # Below min_linear_velocity_for_risk -> forward_safe True, urgency 0
    safe, turn, urgency = compute_risk_and_turn(
        10.0, 50.0, 10.0, 0.02, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert safe is True
    assert urgency == 0.0


def test_compute_risk_and_turn_high_angular_no_risk() -> None:
    # Above max_angular_velocity_for_risk -> forward_safe True
    safe, turn, urgency = compute_risk_and_turn(
        10.0, 100.0, 10.0, 0.3, 0.6, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert safe is True
    assert urgency == 0.0


def test_compute_risk_and_turn_low_flow_safe() -> None:
    # Low center mag, moving -> forward_safe True
    safe, turn, urgency = compute_risk_and_turn(
        5.0, 2.0, 5.0, 0.2, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert safe is True
    assert urgency < 1.0


def test_compute_risk_and_turn_high_flow_unsafe() -> None:
    # High center mag, moving -> forward_safe False, urgency high
    safe, turn, urgency = compute_risk_and_turn(
        5.0, 100.0, 5.0, 0.2, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert safe is False
    assert urgency >= 0.0
    assert urgency <= 1.0


def test_compute_risk_and_turn_safest_turn() -> None:
    # Left mag < right -> safest_turn -1
    _, turn, _ = compute_risk_and_turn(
        2.0, 10.0, 20.0, 0.1, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert turn == -1

    # Right mag < left -> safest_turn 1
    _, turn, _ = compute_risk_and_turn(
        20.0, 10.0, 2.0, 0.1, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert turn == 1

    # Within dead_zone -> safest_turn 0
    _, turn, _ = compute_risk_and_turn(
        10.0, 10.0, 10.5, 0.1, 0.0, 30.0, 0.05, 2.0, 0.05, 0.5
    )
    assert turn == 0
