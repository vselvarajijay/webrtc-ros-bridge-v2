# ConnectX MCP Server

MCP server that exposes ConnectX robot state, perception images, and (optionally) velocity control to LLM agents via the [Model Context Protocol](https://modelcontextprotocol.io/).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for running the project
- ConnectX app running (e.g. `./cli.sh start`) so `APP_URL` is reachable

## Run the server

From this directory:

```bash
uv run python server.py
```

The server listens on **http://127.0.0.1:8001** by default. Use `MCP_PORT` to change the port.

## Environment

| Variable    | Default                | Description                          |
| ----------- | ---------------------- | ------------------------------------ |
| `APP_URL`   | `http://localhost:8000` | ConnectX app base URL (telemetry, images, control API) |
| `MCP_PORT`  | `8001`                 | Port for the MCP streamable HTTP server |

From another host or Docker, set `APP_URL` to the ConnectX app (e.g. `http://host.docker.internal:8000` on Mac).

## Connect a client

- **MCP Inspector**: `npx -y @modelcontextprotocol/inspector` then connect to **http://localhost:8001/mcp**
- **Cursor**: Add MCP server with transport **HTTP** and URL **http://localhost:8001/mcp**
- **Claude Desktop**: `claude mcp add --transport http connectx http://localhost:8001/mcp`

## Tools and resources

- **get_robot_state** — Latest telemetry (battery, speed, GPS, orientation, IMU, etc.) from ConnectX.
- **get_robot_image** — Perception image: `optical_flow` or `floor_mask`.
- **connectx://robot/state** — Resource with the same state as `get_robot_state`.
- **send_velocity** — (When control API is enabled) Send linear and angular velocity to the robot. Accepts `duration_ms` (default 500): the robot moves for that many milliseconds, then receives a stop command automatically.
