"""ConnectX chat agent: a LangGraph ReAct agent that queries robot state and
sends velocity commands via the ConnectX app HTTP API.

Exported: graph  (consumed by LangGraph Studio via langgraph.json)

Environment variables:
  APP_URL         – ConnectX app base URL (default: http://app:8000 in Docker)
  OPENAI_API_KEY  – OpenAI API key for the LLM
  LLM_MODEL       – OpenAI model name (default: gpt-4o-mini)
"""

import inspect
import os

import httpx
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
            r = await client.get(f"{APP_URL}/data")
            r.raise_for_status()
            return r.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return "Robot not connected. Ensure the ConnectX bridge is running and the robot has connected via signaling."
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


@tool
async def send_velocity(linear_x: float = 0.0, angular_z: float = 0.0) -> str:
    """Send a velocity command to the ConnectX robot.

    Args:
        linear_x: Forward (+) or backward (-) speed in m/s. Range: -1.0 to 1.0.
        angular_z: Turn left (+) or right (-) in rad/s. Range: -1.0 to 1.0.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{APP_URL}/api/control",
                json={"linear_x": linear_x, "angular_z": angular_z},
            )
            if r.status_code == 200:
                return f"Sent velocity linear_x={linear_x} angular_z={angular_z}"
            if r.status_code == 503:
                return "Robot not connected. Connect the robot via ConnectX signaling first."
            return f"HTTP error {r.status_code}: {r.text}"
    except httpx.RequestError as e:
        return f"Could not reach ConnectX app at {APP_URL}: {e}"


_llm = ChatOpenAI(model=LLM_MODEL)

_system_message = SystemMessage(
    content=(
        "You are a helpful assistant for the ConnectX robot platform. "
        "You can query the robot's current state (battery, speed, GPS, orientation) "
        "and send velocity commands to drive the robot. "
        "Always confirm the robot state before issuing drive commands."
    )
)

# Support both older (state_modifier) and newer (prompt) LangGraph API
_params = inspect.signature(create_react_agent).parameters
_agent_kwargs = {"tools": [get_robot_state, send_velocity]}
if "state_modifier" in _params:
    _agent_kwargs["state_modifier"] = _system_message
elif "prompt" in _params:
    _agent_kwargs["prompt"] = _system_message

graph = create_react_agent(_llm, **_agent_kwargs)
