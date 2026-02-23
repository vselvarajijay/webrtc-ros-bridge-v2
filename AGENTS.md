# ConnectX Agents

Single reference for AI agents and contributors working on **any part** of the ConnectX repo. For full setup and workflow, see [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Repo overview

| Area | Description |
|------|-------------|
| `app/www` | React + TypeScript + Vite frontend (Mantine, Tailwind). Built and served by the app container. |
| `app/server` | Python FastAPI app (signaling, etc.). |
| `ros2_ws/` | ROS 2 workspace: bridge, controller, planner, teleop, perception packages. See [ros2_ws/TESTING.md](ros2_ws/TESTING.md) for test layout. |
| `docker/` | Dockerfiles for app, bridge, SDK, etc. `docker-compose.yml` defines services (app, bridge, webrtc, perception, optional LangGraph/MCP). |
| `docs/` | Project documentation (e.g. debugging, intro). |
| `agents/` | LangGraph graphs using the MCP server. |
| `mcp/` | MCP server for Cursor/Claude (tools and resources). |
| `scripts/`, `cli.sh` | Helpers and main CLI: build, start, stop, test, logs, etc. |

## Checks by area

- **app (frontend):** `cd app/www && pnpm lint` (and `pnpm build` if you changed build-related code).
- **app/server, scripts:** Python 3.10+; follow existing style; no formal linter required.
- **ros2_ws:** `./cli.sh test` (runs colcon test in the bridge container). To mirror CI: `./scripts/run_ros2_ci_local.sh`. See [ros2_ws/TESTING.md](ros2_ws/TESTING.md).
- **docker:** Rebuild and smoke-test with `./cli.sh build` and `./cli.sh start` (or the services you changed).
- **docs:** Ensure links and code snippets are correct; no automated check.
- **agents:** `cd agents && uv run pytest`; run the example if you changed agent code.
- **mcp:** `cd mcp && uv run pytest`.

## PR instructions

- **Title format:** Use a scope prefix: `[app]`, `[ros2]`, `[docker]`, `[docs]`, `[agents]`, `[mcp]`, etc. (e.g. `[app] Fix telemetry panel`, `[ros2] Add planner test`, `[docker] Update bridge base image`, `[docs] Update debugging steps`).
- Run the **checks for the areas you changed** (see “Checks by area” above). See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow.
- When you add or change **agents or MCP** tools, keep this file (and the tool contract below) in sync.

## Agents & MCP (LangGraph and MCP server)

### Dev environment tips

- Use **uv** in `agents/`: `cd agents && uv run python examples/robot_state_agent.py` to run the example; `uv sync` to install deps.
- Run the **MCP server** from `mcp/`: `uv run python server.py`. It serves tools and resources for Cursor/Claude Desktop. Default URL: http://127.0.0.1:8001/mcp.
- **LangGraph Studio:** From repo root, `langgraph dev` (or use the `connectx_langgraph` Docker service). Graph entrypoints are in `agents/langgraph.json`; add new graphs there and point to `./some_agent.py:graph`.
- **Env:** Copy `.env.example` to `.env`. For agents you need `OPENAI_API_KEY`, `LLM_MODEL` (default `gpt-4o-mini`), `APP_URL`. For MCP, `APP_URL` and `MCP_PORT`. ConnectX app must be reachable at `APP_URL` for live robot data.
- Check the **package name** in `agents/pyproject.toml` (`connectx-agents`) when adding deps or publishing. MCP is in `mcp/` and has its own `pyproject.toml`.

### Tool contract (all agents)

- **Before drive:** Confirm robot state (or reason about connectivity) before sending velocity.
- **Ranges:** `linear_x`, `angular_z` in **[-1.0, 1.0]** (m/s, rad/s). Enforce in tool schemas and prompts.

### Testing (agents and MCP)

- Run the test suite: `cd agents && uv run pytest` and `cd mcp && uv run pytest`. The commit should pass all tests before you merge.
- If your repo has CI for agents, find the plan in `.github/workflows/` and run the same steps locally.
- Add or update tests when you add or change agent or MCP behavior (e.g. unit tests for tools, graph nodes, or server endpoints). Fix any test or type errors until the suite is green.
