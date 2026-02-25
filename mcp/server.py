"""
ConnectX MCP server: exposes robot state, perception images, and control via MCP tools/resources.
Uses the ConnectX app HTTP API (APP_URL). Run with: uv run python server.py
"""

import asyncio
import json
import logging
import math
import os
import time
from typing import Literal

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from mcp.server.fastmcp import FastMCP, Image

APP_URL = os.environ.get("APP_URL", "http://localhost:8000").rstrip("/")

# MCP server port (ConnectX app uses 8000)
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))

mcp = FastMCP(
    "ConnectX Robot",
    instructions=(
        "Tools and resources for querying ConnectX robot state, perception images, sending velocity commands, and rotating the robot. "
        "For 'turn right 45 degrees' or 'turn left 30 degrees' call rotate_to_heading(45, relative=True) or rotate_to_heading(-30, relative=True). "
        "For absolute heading (e.g. 'face 90 degrees', 'point north') call rotate_to_heading(90) or rotate_to_heading(0) with relative=False or omitted."
    ),
    stateless_http=True,
    json_response=True,
    port=MCP_PORT,
)


# Poll /data until payload has orientation (robot telemetry fully available)
_DATA_POLL_INTERVAL_SEC = 0.5
# Request latest telemetry (no cached response)
_DATA_NO_CACHE_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache"}


def _data_url() -> str:
    """GET /data URL with cache-busting query so we always get latest telemetry."""
    return f"{APP_URL}/data?_={time.monotonic()}"


_DATA_MAX_RETRIES = 5


async def _fetch_data_with_orientation(
    client: httpx.AsyncClient,
    max_retries: int = _DATA_MAX_RETRIES,
    interval_sec: float = _DATA_POLL_INTERVAL_SEC,
) -> tuple[dict | None, str | None]:
    """GET /data with retries until payload has orientation. Returns (data, None) or (None, error_message)."""
    for attempt in range(1, max_retries + 1):
        try:
            r = await client.get(_data_url(), headers=_DATA_NO_CACHE_HEADERS)
        except httpx.RequestError as e:
            return (None, f"Could not reach ConnectX app at {APP_URL}: {e}")
        if r.status_code == 503:
            return (
                None,
                "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling.",
            )
        if r.status_code != 200:
            return (None, f"HTTP error {r.status_code}: {r.text}")
        try:
            data = r.json()
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(interval_sec)
                continue
            return (None, "Telemetry not ready: invalid JSON from /data.")
        if data.get("orientation") is not None and isinstance(
            data["orientation"], (int, float)
        ):
            return (data, None)
        if attempt < max_retries:
            await asyncio.sleep(interval_sec)
    return (
        None,
        f"Telemetry not ready: /data did not include orientation after {max_retries} retries. "
        "Robot may still be connecting.",
    )


@mcp.tool()
async def get_robot_state() -> str:
    """Get latest robot telemetry (battery, speed, GPS, orientation, IMU, etc.) from ConnectX.
    Retries up to 5 times until the payload includes orientation; returns full telemetry when available."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data, err = await _fetch_data_with_orientation(client)
            if err:
                return err
            return json.dumps(data)
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@mcp.resource("connectx://robot/state")
def robot_state_resource() -> str:
    """Get latest robot telemetry as a resource (same as get_robot_state). Retries up to 5 times until payload has orientation."""
    try:
        for attempt in range(1, _DATA_MAX_RETRIES + 1):
            r = httpx.get(_data_url(), timeout=10.0, headers=_DATA_NO_CACHE_HEADERS)
            if r.status_code == 503:
                return "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling."
            r.raise_for_status()
            try:
                data = r.json()
            except Exception:
                if attempt < _DATA_MAX_RETRIES:
                    time.sleep(_DATA_POLL_INTERVAL_SEC)
                    continue
                return "Telemetry not ready: invalid JSON from /data."
            if data.get("orientation") is not None and isinstance(
                data["orientation"], (int, float)
            ):
                return r.text
            if attempt < _DATA_MAX_RETRIES:
                time.sleep(_DATA_POLL_INTERVAL_SEC)
        return (
            f"Telemetry not ready: /data did not include orientation after {_DATA_MAX_RETRIES} retries. "
            "Robot may still be connecting."
        )
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


def _image_url(image_type: Literal["optical_flow", "floor_mask"]) -> str:
    if image_type == "optical_flow":
        return f"{APP_URL}/api/optical_flow_image"
    return f"{APP_URL}/api/floor_mask_image"


def _wrap_angle_deg(angle_deg: float) -> float:
    """Wrap angle to [-180, 180]."""
    x = (angle_deg + 180.0) % 360.0 - 180.0
    return x


def _orientation_to_degrees(raw: int | float) -> float:
    """Return orientation as 0-360 degrees. Bridge already publishes 0-360 (converted from SDK 0-180)."""
    return float(raw) % 360.0


@mcp.tool(structured_output=False)
async def get_robot_image(
    image_type: Literal["optical_flow", "floor_mask"],
) -> Image | str:
    """Get a perception image from the robot: optical_flow visualization or floor_mask visualization."""
    url = _image_url(image_type)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return Image(data=r.content, format="jpeg")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return (
                f"{image_type.replace('_', ' ').title()} not available. "
                "Ensure the corresponding perception node is running (e.g. optical_flow_node, floor_mask_node)."
            )
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@mcp.tool()
async def send_velocity(
    linear_x: float = 0.0,
    angular_z: float = 0.0,
    duration_ms: int = 500,
) -> str:
    """Send a velocity command to the robot for a given duration, then stop.

    Direction and speed are expressed via linear_x (forward/back) and angular_z (turn).
    The robot moves with this velocity for duration_ms milliseconds, then is sent a stop
    (0, 0) automatically. Only has effect when the robot is connected via ConnectX."""
    request_timeout = max(10.0, duration_ms / 1000.0 + 5.0)
    logger.info(
        "send_velocity: linear_x=%.2f angular_z=%.2f duration_ms=%d",
        linear_x, angular_z, duration_ms,
    )
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            r = await client.post(
                f"{APP_URL}/api/control",
                json={"linear_x": linear_x, "angular_z": angular_z},
            )
            if r.status_code != 200:
                logger.warning(
                    "send_velocity: velocity POST failed status=%d body=%s",
                    r.status_code, r.text,
                )
                if r.status_code == 503:
                    return "Robot not connected. Connect the robot via ConnectX signaling first."
                return f"HTTP error {r.status_code}: {r.text}"
            logger.info("send_velocity: velocity sent, sleeping %dms", duration_ms)
            await asyncio.sleep(duration_ms / 1000.0)
            stop_r = await client.post(
                f"{APP_URL}/api/control",
                json={"linear_x": 0.0, "angular_z": 0.0},
            )
            if stop_r.status_code == 200:
                logger.info("send_velocity: stop sent successfully")
                return f"Sent velocity linear_x={linear_x} angular_z={angular_z} for {duration_ms}ms, then stopped."
            logger.warning(
                "send_velocity: stop POST failed status=%d body=%s",
                stop_r.status_code, stop_r.text,
            )
            return f"Sent velocity for {duration_ms}ms; stop command returned HTTP {stop_r.status_code}: {stop_r.text}"
    except httpx.RequestError as e:
        logger.exception("send_velocity: request error to %s", APP_URL)
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


# How often to re-fetch telemetry and re-check orientation while turning (seconds)
_ROTATE_CHECK_INTERVAL_SEC = 0.03
# Retries when reading orientation during rotate (keep getting latest)
_ROTATE_ORIENTATION_RETRIES = 3
_ROTATE_ORIENTATION_INTERVAL_SEC = 0.05


async def _rotate_to_heading_impl(
    client: httpx.AsyncClient,
    target_heading_deg: float,
    heading_error_threshold_deg: float = 10.0,
    Kp: float = 0.9,
    Kd: float = 0.2,
    max_omega_rad_s: float = 0.35,
    control_dt_sec: float = 0.05,
    timeout_sec: float = 30.0,
) -> str:
    """Shared implementation: rotate to target_heading_deg (0-360) using PD control.
    Each loop: get latest telemetry (with retries), check orientation, stop if within threshold else send command.
    Keeps fetching /data with retries so we always use the latest orientation as the robot turns.
    """
    threshold_rad = math.radians(heading_error_threshold_deg)
    prev_error_rad: float | None = None
    prev_check_time = time.monotonic()
    start = prev_check_time
    while True:
        if time.monotonic() - start > timeout_sec:
            await client.post(
                f"{APP_URL}/api/control",
                json={"linear": 0.0, "angular": 0.0},
            )
            return (
                f"Timeout after {timeout_sec}s before reaching target heading {target_heading_deg}°."
            )
        # Get latest orientation (retry so we keep getting fresh data as it turns)
        data, err = await _fetch_data_with_orientation(
            client,
            max_retries=_ROTATE_ORIENTATION_RETRIES,
            interval_sec=_ROTATE_ORIENTATION_INTERVAL_SEC,
        )
        if err:
            return err
        current_deg = _orientation_to_degrees(data["orientation"])
        error_deg = _wrap_angle_deg(target_heading_deg - current_deg)
        error_rad = math.radians(error_deg)
        if abs(error_rad) <= threshold_rad:
            await client.post(
                f"{APP_URL}/api/control",
                json={"linear": 0.0, "angular": 0.0},
            )
            return (
                f"Reached target heading {target_heading_deg}° "
                f"(current {current_deg:.1f}°, error {error_deg:.1f}° within {heading_error_threshold_deg}°)."
            )
        # Compute and send angular command; re-check after control_dt_sec
        if prev_error_rad is None:
            d_error_rad = 0.0
        else:
            dt = time.monotonic() - prev_check_time
            d_error_rad = (error_rad - prev_error_rad) / dt if dt > 0 else 0.0
        prev_error_rad = error_rad
        prev_check_time = time.monotonic()
        omega = Kp * error_rad + Kd * d_error_rad
        # Scale down max omega for small errors to avoid over-correction and overshoot
        error_deg_abs = abs(error_deg)
        scale = max(0.2, min(1.0, error_deg_abs / 45.0))  # full speed at 45°+, gentler below
        max_effective = max_omega_rad_s * scale
        omega = max(-max_effective, min(max_effective, omega))
        # ConnectX/Earth Rovers: positive angular = turn left (CCW), negative = right (CW).
        # Compass increases when turning right; positive error = need to increase heading -> turn right -> negative omega.
        omega_cmd = -omega
        ctrl_r = await client.post(
            f"{APP_URL}/api/control",
            json={"linear": 0.0, "angular": omega_cmd},
        )
        if ctrl_r.status_code == 503:
            return "Robot disconnected during rotate. Stopped."
        if ctrl_r.status_code != 200:
            return (
                f"Control API error during rotate: HTTP {ctrl_r.status_code}: {ctrl_r.text}"
            )
        # Until next control step: keep getting latest orientation and re-check so we stop as soon as on target
        next_cmd_time = time.monotonic() + control_dt_sec
        while time.monotonic() < next_cmd_time and (time.monotonic() - start) <= timeout_sec:
            await asyncio.sleep(_ROTATE_CHECK_INTERVAL_SEC)
            data, err = await _fetch_data_with_orientation(
                client,
                max_retries=_ROTATE_ORIENTATION_RETRIES,
                interval_sec=_ROTATE_ORIENTATION_INTERVAL_SEC,
            )
            if err:
                continue
            current_deg = _orientation_to_degrees(data["orientation"])
            error_deg = _wrap_angle_deg(target_heading_deg - current_deg)
            error_rad = math.radians(error_deg)
            if abs(error_rad) <= threshold_rad:
                await client.post(
                    f"{APP_URL}/api/control",
                    json={"linear_x": 0.0, "angular_z": 0.0},
                )
                return (
                    f"Reached target heading {target_heading_deg}° "
                    f"(current {current_deg:.1f}°, error {error_deg:.1f}° within {heading_error_threshold_deg}°)."
                )


@mcp.tool()
async def turn_by_degrees(
    angle_deg: float,
    heading_error_threshold_deg: float = 10.0,
    Kp: float = 0.9,
    Kd: float = 0.2,
    max_omega_rad_s: float = 0.35,
    control_dt_sec: float = 0.05,
    timeout_sec: float = 30.0,
) -> str:
    """Turn the robot by a relative angle in degrees. Use this for phrases like 'turn right 45 degrees' or 'turn left 30 degrees'.

    Positive angle_deg = turn right (clockwise). Negative = turn left (counter-clockwise).
    Fetches current orientation, computes target heading = (current + angle_deg) wrapped to 0-360,
    then rotates to that heading using a PD controller. Pure rotation, no forward motion.

    Args:
        angle_deg: Relative turn in degrees. Right = positive, left = negative. E.g. turn right 45 -> 45, turn left 30 -> -30.
        heading_error_threshold_deg: Stop when heading error is within this many degrees (default 10).
        Kp, Kd, max_omega_rad_s, control_dt_sec, timeout_sec: Same as rotate_to_heading.
    """
    logger.info("turn_by_degrees: angle_deg=%.1f", angle_deg)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data, err = await _fetch_data_with_orientation(client)
            if err:
                return err
            current_deg = _orientation_to_degrees(data["orientation"])
            target_heading_deg = (current_deg + angle_deg) % 360.0
            return await _rotate_to_heading_impl(
                client,
                target_heading_deg,
                heading_error_threshold_deg=heading_error_threshold_deg,
                Kp=Kp,
                Kd=Kd,
                max_omega_rad_s=max_omega_rad_s,
                control_dt_sec=control_dt_sec,
                timeout_sec=timeout_sec,
            )
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@mcp.tool()
async def rotate_to_heading(
    target_heading_deg: float,
    relative: bool = False,
    heading_error_threshold_deg: float = 10.0,
    Kp: float = 0.9,
    Kd: float = 0.2,
    max_omega_rad_s: float = 0.35,
    control_dt_sec: float = 0.05,
    timeout_sec: float = 30.0,
) -> str:
    """Rotate the robot to a target heading. Use for both relative and absolute turns.

    For 'turn right 45 degrees' or 'turn left 30 degrees': call rotate_to_heading(45, relative=True)
    or rotate_to_heading(-30, relative=True). The angle is in degrees (positive = right).
    For absolute heading (e.g. 'face 90 degrees'): call rotate_to_heading(90) or rotate_to_heading(90, relative=False).

    Fetches current orientation (when relative=True, adds target_heading_deg to current), then sends
    angular velocity until heading error is below threshold. Pure rotation (no forward motion).

    Args:
        target_heading_deg: Angle in degrees. If relative=True: turn by this amount (right=positive). If relative=False: absolute heading 0-360.
        relative: If True, target_heading_deg is a relative turn in degrees. If False, absolute heading 0-360.
        heading_error_threshold_deg: Stop when heading error is within this many degrees (default 10).
        Kp, Kd, max_omega_rad_s, control_dt_sec, timeout_sec: PD control and timing.
    """
    logger.info(
        "rotate_to_heading: target_deg=%.1f relative=%s threshold_deg=%.1f",
        target_heading_deg,
        relative,
        heading_error_threshold_deg,
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        if relative:
            data, err = await _fetch_data_with_orientation(client)
            if err:
                return err
            current_deg = _orientation_to_degrees(data["orientation"])
            target_heading_deg = (current_deg + target_heading_deg) % 360.0
        else:
            target_heading_deg = target_heading_deg % 360.0
        return await _rotate_to_heading_impl(
            client,
            target_heading_deg,
            heading_error_threshold_deg=heading_error_threshold_deg,
            Kp=Kp,
            Kd=Kd,
            max_omega_rad_s=max_omega_rad_s,
            control_dt_sec=control_dt_sec,
            timeout_sec=timeout_sec,
        )


if __name__ == "__main__":
    import contextlib
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(name)s %(message)s",
        datefmt="%m/%d/%y %H:%M:%S",
    )

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/mcp", mcp.streamable_http_app())],
        lifespan=lifespan,
    )
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)
