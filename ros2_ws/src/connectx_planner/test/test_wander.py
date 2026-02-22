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

pytestmark = pytest.mark.unit


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
    """Low confidence: never stop, keep moving at turn_linear."""
    state = _make_state(confidence=0.3)
    lin, ang, _, _, _ = compute_wander_twist(
        state, True, 0, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert lin == 0.25 * 0.6  # turn_linear_fraction, never stop
    assert ang == 0.3


def test_wander_forward_safe_output_bounds() -> None:
    # safest_turn=0 (default) -> angular 0 (no random bias)
    state = _make_state(forward_safe=True, confidence=1.0)
    lin, ang, next_was, next_turning, next_escape = compute_wander_twist(
        state, True, 0, 0, 0.1,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert lin == 0.25
    assert ang == 0.0
    assert next_was is True
    assert next_turning == 0
    assert next_escape == 0


def test_wander_forward_steer_toward_furthest() -> None:
    """In forward mode we steer only toward furthest (safest_turn); no random bias."""
    forward_steer = 0.4
    bias_limit = 0.2
    # Right clearer: safest_turn=1 -> steer right (positive angular)
    state_r = _make_state(forward_safe=True, safest_turn=1, confidence=1.0)
    lin, ang, next_was, _, _ = compute_wander_twist(
        state_r, True, 0, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, bias_limit, forward_steer, 0.6,
    )
    assert lin == 0.25
    assert next_was is True
    assert ang == forward_steer
    # Left clearer: safest_turn=-1 -> steer left (negative angular)
    state_l = _make_state(forward_safe=True, safest_turn=-1, confidence=1.0)
    _, ang_l, _, _, _ = compute_wander_twist(
        state_l, True, 0, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, bias_limit, forward_steer, 0.6,
    )
    assert ang_l == -forward_steer


def test_wander_turn_mode_output_bounds() -> None:
    state = _make_state(forward_safe=False, safest_turn=1, urgency_score=0.8, confidence=1.0)
    lin, ang, next_was, next_turning, next_escape = compute_wander_twist(
        state, False, 10, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert lin == 0.25 * 0.6  # turn_linear_fraction
    assert abs(ang) <= 0.6 * 3.0  # turn_mult up to 3.0 when urgency high
    assert next_was is False
    assert next_turning == 11


def test_wander_escape_pulse() -> None:
    state = _make_state(forward_safe=False, confidence=1.0)
    lin, ang, _, next_turning, next_escape = compute_wander_twist(
        state, False, 75, 3, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.9, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert lin == 0.25 * 0.6  # escape pulse still uses turn_linear
    assert ang == 0.0
    assert next_escape == 2


def test_wander_enter_turn_immediately_when_unsafe() -> None:
    """As soon as forward_safe=False we enter turn mode (even if urgency is low)."""
    state = _make_state(forward_safe=False, safest_turn=-1, urgency_score=0.3, confidence=1.0)
    lin, ang, next_was, next_turning, _ = compute_wander_twist(
        state, True, 0, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, 0.55, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert next_was is False
    assert lin == 0.25 * 0.6  # turn while moving
    assert next_turning == 1
    assert ang != 0.0  # turning towards safest_turn


def test_wander_clear_hysteresis_no_forward_while_urgency_high() -> None:
    """One safe frame with high urgency must not clear turn mode (avoids oscillation)."""
    state = _make_state(forward_safe=True, urgency_score=0.7, confidence=1.0)
    hysteresis = 0.55
    lin, ang, next_was, next_turning, _ = compute_wander_twist(
        state, False, 5, 0, 0.0,
        0.25, 0.6, 0.3, 0.5, hysteresis, 75, 0.05, 8, 0.2, 0.4, 0.6,
    )
    assert next_was is False
    assert lin == 0.25 * 0.6  # turn while moving
    assert next_turning == 6
