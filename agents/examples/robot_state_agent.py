"""
Example LangGraph agent that calls the ConnectX MCP server (get_robot_state).

Run from repo root: uv run python examples/robot_state_agent.py
Requires the ConnectX MCP server to be running (e.g. from mcp/: uv run python server.py).
"""

import asyncio
import os
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import mcp.types as types

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")


class AgentState(TypedDict):
    """State passed through the graph."""
    robot_state: str
    message: str


async def fetch_robot_state(state: AgentState) -> dict:
    """Connect to the ConnectX MCP server and call get_robot_state."""
    try:
        async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("get_robot_state", arguments={})
                text_parts = []
                for content in result.content:
                    if isinstance(content, types.TextContent):
                        text_parts.append(content.text)
                robot_state = "\n".join(text_parts) if text_parts else str(result)
                return {"robot_state": robot_state}
    except Exception as e:
        return {
            "robot_state": f"Robot not connected or MCP server not running: {e!s}. "
            f"Ensure the MCP server is running at {MCP_SERVER_URL}."
        }


def report(state: AgentState) -> dict:
    """Produce a final message from the fetched state (no LLM)."""
    return {"message": state.get("robot_state", "No state.")}


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("fetch_robot_state", fetch_robot_state)
    graph.add_node("report", report)
    graph.add_edge(START, "fetch_robot_state")
    graph.add_edge("fetch_robot_state", "report")
    graph.add_edge("report", END)
    return graph


async def main() -> None:
    graph = build_graph().compile()
    initial: AgentState = {"robot_state": "", "message": ""}
    result = await graph.ainvoke(initial)
    print(result.get("message", result))


if __name__ == "__main__":
    asyncio.run(main())
