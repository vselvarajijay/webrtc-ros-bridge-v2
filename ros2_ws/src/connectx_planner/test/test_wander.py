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

from connectx_msgs.msg import NavigationState
from connectx_planner.nodes.wander_node import compute_wander_twist


def _make_state(
    forward_safe: bool = True,
    safest_turn: int = 0,
    urgency_score: float = 0.0,
    confidence: float = 1.0,
) -> NavigationState:
    state = NavigationState()
    state.forward_safe = forward_safe
    state.safest_turn = safest_turn
    state.urgency_score = urgency_score
    state.confidence = confidence
    return state


def test_wander_low_confidence_output_bounds() -> None:
    state = _make_state(confidence=0.3)
    lin, ang, _, _, _ = compute_wander_twist(
        state, True, 0, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2,
    )
    assert lin == 0.0
    assert ang == 0.3


def test_wander_forward_safe_output_bounds() -> None:
    state = _make_state(forward_safe=True, confidence=1.0)
    lin, ang, next_was, next_turning, next_escape = compute_wander_twist(
        state, True, 0, 0, 0.1,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2,
    )
    assert lin == 0.25
    assert -0.2 <= ang <= 0.2
    assert next_was is True
    assert next_turning == 0
    assert next_escape == 0


def test_wander_turn_mode_output_bounds() -> None:
    state = _make_state(forward_safe=False, safest_turn=1, urgency_score=0.8, confidence=1.0)
    lin, ang, next_was, next_turning, next_escape = compute_wander_twist(
        state, False, 10, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2,
    )
    assert lin == 0.05
    assert abs(ang) <= 0.6 * 1.5
    assert next_was is False
    assert next_turning == 11


def test_wander_escape_pulse() -> None:
    state = _make_state(forward_safe=False, confidence=1.0)
    lin, ang, _, next_turning, next_escape = compute_wander_twist(
        state, False, 75, 3, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2,
    )
    assert lin == 0.05
    assert ang == 0.0
    assert next_escape == 2
