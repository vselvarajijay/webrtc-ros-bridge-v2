# ConnectX Agents

LangGraph agents that use the [ConnectX MCP server](../mcp/) for robot state, perception images, and control.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- ConnectX MCP server running (from `mcp/`: `uv run python server.py`)
- ConnectX app running if you want live robot data (e.g. `./cli.sh start` from repo root)

## Environment

| Variable          | Default                         | Description                    |
| ----------------- | ------------------------------- | ------------------------------ |
| `MCP_SERVER_URL`  | `http://127.0.0.1:8001/mcp`     | ConnectX MCP server endpoint   |

## Run the example

From this directory (`agents/`):

```bash
uv run python examples/robot_state_agent.py
```

The example graph fetches robot telemetry via the MCP server (`get_robot_state`) and prints the result. If the MCP server or ConnectX app is not running, you will see a clear error message.
