"""ConnectX chat agent: a LangGraph ReAct agent that uses the ConnectX MCP server
to query robot state and send velocity commands.

Exported: graph  (consumed by LangGraph Studio via langgraph.json)

Environment variables:
  MCP_SERVER_URL  – URL of the ConnectX MCP server (default: http://connectx_mcp:8002/mcp)
  OPENAI_API_KEY  – OpenAI API key for the LLM
  LLM_MODEL       – OpenAI model name (default: gpt-4o-mini)
"""

import inspect
import os

import mcp.types as mcp_types
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://connectx_mcp:8002/mcp")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


async def _call_mcp(tool_name: str, arguments: dict) -> str:
    """Open a single-use MCP session, call tool_name, and return the text result."""
    async with streamable_http_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            parts = [
                c.text
                for c in result.content
                if isinstance(c, mcp_types.TextContent)
            ]
            return "\n".join(parts) if parts else str(result)


@tool
async def get_robot_state() -> str:
    """Get the latest ConnectX robot telemetry: battery, speed, GPS, orientation, IMU."""
    return await _call_mcp("get_robot_state", {})


@tool
async def send_velocity(linear_x: float = 0.0, angular_z: float = 0.0) -> str:
    """Send a velocity command to the ConnectX robot.

    Args:
        linear_x: Forward (+) or backward (-) speed in m/s. Range: -1.0 to 1.0.
        angular_z: Turn left (+) or right (-) in rad/s. Range: -1.0 to 1.0.
    """
    return await _call_mcp("send_velocity", {"linear_x": linear_x, "angular_z": angular_z})


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
