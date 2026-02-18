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

from scout_controller.command_parser import STOP_COMMAND, parse_command


def test_stop_returns_empty() -> None:
    assert parse_command("stop") == []
    assert parse_command("  stop  ") == []
    assert parse_command(STOP_COMMAND) == []


def test_empty_or_invalid_returns_empty() -> None:
    assert parse_command("") == []
    assert parse_command("   ") == []
    assert parse_command("nonsense") == []


def test_legacy_turn() -> None:
    goals = parse_command("turn left 30")
    assert len(goals) == 1
    assert goals[0]["type"] == "turn"
    assert goals[0]["angle_deg"] == -30
    assert "angular_vel_rad_s" not in goals[0]

    goals = parse_command("turn right 45 deg")
    assert len(goals) == 1
    assert goals[0]["type"] == "turn"
    assert goals[0]["angle_deg"] == 45


def test_short_turn() -> None:
    goals = parse_command("left 30")
    assert len(goals) == 1
    assert goals[0]["type"] == "turn"
    assert goals[0]["angle_deg"] == -30

    goals = parse_command("right 45")
    assert len(goals) == 1
    assert goals[0]["type"] == "turn"
    assert goals[0]["angle_deg"] == 45


def test_turn_with_profile() -> None:
    goals = parse_command("right 30 at 0.3 for 2 s")
    assert len(goals) == 1
    assert goals[0]["type"] == "turn"
    assert goals[0]["angle_deg"] == 30
    assert goals[0].get("angular_vel_rad_s") == 0.3
    assert goals[0].get("duration_s") == 2.0

    goals = parse_command("turn right 30 deg at 0.4 for 2 s accel 0.2 decel 0.3")
    assert len(goals) == 1
    assert goals[0]["angle_deg"] == 30
    assert goals[0].get("angular_vel_rad_s") == 0.4
    assert goals[0].get("duration_s") == 2.0
    assert goals[0].get("accel_rad_s2") == 0.2
    assert goals[0].get("decel_rad_s2") == 0.3

    goals = parse_command("left 20 accel 0.2 decel 0.3")
    assert len(goals) == 1
    assert goals[0]["angle_deg"] == -20
    assert goals[0].get("accel_rad_s2") == 0.2
    assert goals[0].get("decel_rad_s2") == 0.3


def test_legacy_drive() -> None:
    goals = parse_command("forward 1m")
    assert len(goals) == 1
    assert goals[0]["type"] == "drive"
    assert goals[0]["distance_m"] == 1.0
    assert goals[0]["direction"] == 1

    goals = parse_command("back 0.5 m")
    assert len(goals) == 1
    assert goals[0]["distance_m"] == 0.5
    assert goals[0]["direction"] == -1

    goals = parse_command("forward 1ft")
    assert len(goals) == 1
    assert goals[0]["type"] == "drive"
    assert abs(goals[0]["distance_m"] - 0.3048) < 1e-6


def test_drive_with_profile() -> None:
    goals = parse_command("forward 2 m at 0.3 for 7 s accel 0.15 decel 0.2")
    assert len(goals) == 1
    assert goals[0]["type"] == "drive"
    assert goals[0]["distance_m"] == 2.0
    assert goals[0]["direction"] == 1
    assert goals[0].get("linear_vel_m_s") == 0.3
    assert goals[0].get("duration_s") == 7.0
    assert goals[0].get("accel_m_s2") == 0.15
    assert goals[0].get("decel_m_s2") == 0.2


def test_time_based_drive() -> None:
    goals = parse_command("forward at 0.4 m/s for 5 s")
    assert len(goals) == 1
    assert goals[0]["type"] == "drive"
    assert goals[0]["distance_m"] == 2.0  # 0.4 * 5
    assert goals[0]["direction"] == 1
    assert goals[0].get("linear_vel_m_s") == 0.4
    assert goals[0].get("duration_s") == 5.0

    goals = parse_command("back at 0.2 m/s for 3 s accel 0.1 decel 0.15")
    assert len(goals) == 1
    assert goals[0]["direction"] == -1
    assert goals[0].get("linear_vel_m_s") == 0.2
    assert goals[0].get("duration_s") == 3.0
    assert goals[0].get("accel_m_s2") == 0.1
    assert goals[0].get("decel_m_s2") == 0.15


def test_bare_distance_forward() -> None:
    goals = parse_command("1m")
    assert len(goals) == 1
    assert goals[0]["type"] == "drive"
    assert goals[0]["distance_m"] == 1.0
    assert goals[0]["direction"] == 1


def test_then_clause() -> None:
    goals = parse_command("forward 1m then turn right 30")
    assert len(goals) == 2
    assert goals[0]["type"] == "drive"
    assert goals[0]["distance_m"] == 1.0
    assert goals[1]["type"] == "turn"
    assert goals[1]["angle_deg"] == 30

    goals = parse_command("right 30, forward 2 m")
    assert len(goals) == 2
    assert goals[0]["type"] == "turn"
    assert goals[1]["type"] == "drive"
