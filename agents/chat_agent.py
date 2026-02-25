"""ConnectX chat agent: a LangGraph ReAct agent that queries robot state and
sends velocity commands via the ConnectX app HTTP API.

Exported: graph  (consumed by LangGraph Studio via langgraph.json)

Environment variables:
  APP_URL         – ConnectX app base URL (default: http://app:8000 in Docker)
  OPENAI_API_KEY  – OpenAI API key for the LLM
  LLM_MODEL       – OpenAI model name (default: gpt-4o-mini)
"""

import asyncio
import inspect
import math
import os
import time

import httpx

# Request latest telemetry (no cached response)
_DATA_NO_CACHE_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
# Re-check orientation this often while turning (seconds)
_TURN_CHECK_INTERVAL_SEC = 0.03
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

APP_URL = os.environ.get("APP_URL", "http://app:8000").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


@tool
async def get_robot_state() -> str:
    """Get the latest ConnectX robot telemetry: battery, speed, GPS, orientation, IMU."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(_data_url(), headers=_DATA_NO_CACHE_HEADERS)
            r.raise_for_status()
            return r.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling."
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@tool
async def send_velocity(
    linear_x: float = 0.0,
    angular_z: float = 0.0,
    duration_ms: int = 500,
) -> str:
    """Send a velocity command to the ConnectX robot for a given duration, then stop.

    Args:
        linear_x: Forward (+) or backward (-) speed in m/s. Range: -1.0 to 1.0.
        angular_z: Turn left (+) or right (-) in rad/s. Range: -1.0 to 1.0.
        duration_ms: How long to apply the velocity in milliseconds; then stop. Default 500.
    """
    request_timeout = max(10.0, duration_ms / 1000.0 + 5.0)
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            r = await client.post(
                f"{APP_URL}/api/control",
                json={"linear_x": linear_x, "angular_z": angular_z},
            )
            if r.status_code != 200:
                if r.status_code == 503:
                    return "Robot not connected. Connect the robot via ConnectX signaling first."
                return f"HTTP error {r.status_code}: {r.text}"
            await asyncio.sleep(duration_ms / 1000.0)
            stop_r = await client.post(
                f"{APP_URL}/api/control",
                json={"linear_x": 0.0, "angular_z": 0.0},
            )
            if stop_r.status_code == 200:
                return f"Sent velocity linear_x={linear_x} angular_z={angular_z} for {duration_ms}ms, then stopped."
            return f"Sent velocity for {duration_ms}ms; stop command returned HTTP {stop_r.status_code}: {stop_r.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


def _wrap_angle_deg(angle_deg: float) -> float:
    """Wrap angle to [-180, 180]."""
    return (angle_deg + 180.0) % 360.0 - 180.0


def _data_url() -> str:
    """GET /data URL with cache-busting query so we always get latest telemetry."""
    return f"{APP_URL}/data?_={time.monotonic()}"


def _orientation_to_degrees(raw: int | float) -> float:
    """Return orientation as 0-360 degrees. Bridge already publishes 0-360 (converted from SDK 0-180)."""
    return float(raw) % 360.0


@tool
async def turn_by_degrees(
    angle_deg: float,
    heading_error_threshold_deg: float = 10.0,
    timeout_sec: float = 30.0,
) -> str:
    """Turn the robot by a relative angle in degrees. Use for 'turn right 45 degrees' or 'turn left 30 degrees'.

    Positive angle_deg = turn right (clockwise). Negative = turn left.
    E.g. turn right 45 degrees -> angle_deg=45, turn left 30 degrees -> angle_deg=-30.
    """
    Kp, Kd = 0.9, 0.2
    max_omega_rad_s = 0.3
    control_dt_sec = 0.05
    threshold_rad = math.radians(heading_error_threshold_deg)
    prev_error_rad = None
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(_data_url(), headers=_DATA_NO_CACHE_HEADERS)
            if r.status_code == 503:
                return "Robot not connected. Connect the robot via ConnectX signaling first."
            if r.status_code != 200:
                return f"Failed to get telemetry: HTTP {r.status_code}: {r.text}"
            data = r.json()
            raw_orient = data.get("orientation")
            if raw_orient is None or not isinstance(raw_orient, (int, float)):
                return "Telemetry has no valid 'orientation'. Cannot turn by degrees."
            current_deg = _orientation_to_degrees(raw_orient)
            target_heading_deg = (current_deg + angle_deg) % 360.0
            prev_check_time = start
            while True:
                if time.monotonic() - start > timeout_sec:
                    await client.post(
                        f"{APP_URL}/api/control",
                        json={"linear_x": 0.0, "angular_z": 0.0},
                    )
                    return f"Timeout after {timeout_sec}s before reaching target heading."
                # Get latest telemetry and check orientation (as it's turning)
                r = await client.get(_data_url(), headers=_DATA_NO_CACHE_HEADERS)
                if r.status_code != 200:
                    return f"Failed to get telemetry: HTTP {r.status_code}: {r.text}"
                data = r.json()
                raw_orient = data.get("orientation")
                if raw_orient is None:
                    return "Telemetry has no valid 'orientation'."
                current_deg = _orientation_to_degrees(raw_orient)
                error_deg = _wrap_angle_deg(target_heading_deg - current_deg)
                error_rad = math.radians(error_deg)
                if abs(error_rad) <= threshold_rad:
                    await client.post(
                        f"{APP_URL}/api/control",
                        json={"linear_x": 0.0, "angular_z": 0.0},
                    )
                    return f"Turned by {angle_deg}° (reached target heading {target_heading_deg:.1f}°)."
                dt = time.monotonic() - prev_check_time
                d_error_rad = (
                    0.0
                    if prev_error_rad is None or dt <= 0
                    else (error_rad - prev_error_rad) / dt
                )
                prev_error_rad = error_rad
                prev_check_time = time.monotonic()
                omega = Kp * error_rad + Kd * d_error_rad
                # Scale down max omega for small errors to avoid over-correction and overshoot
                error_deg_abs = abs(error_deg)
                scale = max(0.2, min(1.0, error_deg_abs / 45.0))  # full speed at 45°+, gentler below
                max_effective = max_omega_rad_s * scale
                omega = max(-max_effective, min(max_effective, omega))
                # ConnectX/Earth Rovers: positive angular = left, negative = right; compass increases when turning right.
                omega_cmd = -omega
                ctrl_r = await client.post(
                    f"{APP_URL}/api/control",
                    json={"linear_x": 0.0, "angular_z": omega_cmd},
                )
                if ctrl_r.status_code == 503:
                    return "Robot disconnected during turn. Stopped."
                if ctrl_r.status_code != 200:
                    return f"Control API error: HTTP {ctrl_r.status_code}: {ctrl_r.text}"
                # Until next control step: keep getting data and checking so we stop as soon as on target
                next_cmd_time = time.monotonic() + control_dt_sec
                while time.monotonic() < next_cmd_time and (time.monotonic() - start) <= timeout_sec:
                    await asyncio.sleep(_TURN_CHECK_INTERVAL_SEC)
                    r = await client.get(_data_url(), headers=_DATA_NO_CACHE_HEADERS)
                    if r.status_code != 200:
                        break
                    try:
                        data = r.json()
                        raw_orient = data.get("orientation")
                        if raw_orient is None:
                            break
                        current_deg = _orientation_to_degrees(raw_orient)
                        error_deg = _wrap_angle_deg(target_heading_deg - current_deg)
                        error_rad = math.radians(error_deg)
                        if abs(error_rad) <= threshold_rad:
                            await client.post(
                                f"{APP_URL}/api/control",
                                json={"linear_x": 0.0, "angular_z": 0.0},
                            )
                            return f"Turned by {angle_deg}° (reached target heading {target_heading_deg:.1f}°)."
                    except Exception:
                        break
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


_llm = ChatOpenAI(model=LLM_MODEL)

_system_message = SystemMessage(
    content=(
        "You are a helpful assistant for the ConnectX robot platform. "
        "You can query the robot's current state (battery, speed, GPS, orientation) "
        "and send velocity commands to drive the robot. "
        "For turn-by-angle commands use turn_by_degrees: e.g. 'turn right 45 degrees' -> turn_by_degrees(45), "
        "'turn left 30 degrees' -> turn_by_degrees(-30). Always use the angle in degrees as given by the user. "
        "Always confirm the robot state before issuing drive commands."
    )
)

# Support both older (state_modifier) and newer (prompt) LangGraph API
_params = inspect.signature(create_react_agent).parameters
_agent_kwargs = {"tools": [get_robot_state, send_velocity, turn_by_degrees]}
if "state_modifier" in _params:
    _agent_kwargs["state_modifier"] = _system_message
elif "prompt" in _params:
    _agent_kwargs["prompt"] = _system_message

graph = create_react_agent(_llm, **_agent_kwargs)
