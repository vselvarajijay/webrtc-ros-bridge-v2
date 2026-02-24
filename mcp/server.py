"""
ConnectX MCP server: exposes robot state, perception images, and control via MCP tools/resources.
Uses the ConnectX app HTTP API (APP_URL). Run with: uv run python server.py
"""

import asyncio
import logging
import os
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
    instructions="Tools and resources for querying ConnectX robot state, perception images, and sending velocity commands.",
    stateless_http=True,
    json_response=True,
    port=MCP_PORT,
)


@mcp.tool()
async def get_robot_state() -> str:
    """Get latest robot telemetry (battery, speed, GPS, orientation, IMU, etc.) from ConnectX."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{APP_URL}/data")
            r.raise_for_status()
            return r.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling."
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@mcp.resource("connectx://robot/state")
def robot_state_resource() -> str:
    """Get latest robot telemetry as a resource (same as get_robot_state)."""
    try:
        r = httpx.get(f"{APP_URL}/data", timeout=10.0)
        r.raise_for_status()
        return r.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling."
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


def _image_url(image_type: Literal["optical_flow", "floor_mask"]) -> str:
    if image_type == "optical_flow":
        return f"{APP_URL}/api/optical_flow_image"
    return f"{APP_URL}/api/floor_mask_image"


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
