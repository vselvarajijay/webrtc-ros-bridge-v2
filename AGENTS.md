# ConnectX Agents

Single reference for all agent-style interfaces: LangGraph graphs (`agents/`) and MCP server (`mcp/`) for Cursor and Claude Desktop.

## Dev environment tips

- Use **uv** in `agents/`: `cd agents && uv run python examples/robot_state_agent.py` to run the example; `uv sync` to install deps.
- Run the **MCP server** from `mcp/`: `uv run python server.py`. It serves tools and resources for Cursor/Claude Desktop. Default URL: http://127.0.0.1:8001/mcp.
- **LangGraph Studio**: From repo root, `langgraph dev` (or use the `connectx_langgraph` Docker service). Graph entrypoints are in `agents/langgraph.json`; add new graphs there and point to `./some_agent.py:graph`.
- **Env:** Copy `.env.example` to `.env`. For agents you need `OPENAI_API_KEY`, `LLM_MODEL` (default `gpt-4o-mini`), `APP_URL`. For MCP, `APP_URL` and `MCP_PORT`. ConnectX app must be reachable at `APP_URL` for live robot data.
- Check the **package name** in `agents/pyproject.toml` (`connectx-agents`) when adding deps or publishing. MCP is in `mcp/` and has its own `pyproject.toml`.

## Tool contract (all agents)

- **Before drive:** Confirm robot state (or reason about connectivity) before sending velocity.
- **Ranges:** `linear_x`, `angular_z` in **[-1.0, 1.0]** (m/s, rad/s). Enforce in tool schemas and prompts.

## Testing instructions

- Run the test suite for agents and MCP. From each package: `cd agents && uv run pytest` and `cd mcp && uv run pytest`. The commit should pass all tests before you merge.
- If your repo has CI for agents, find the plan in `.github/workflows/` and run the same steps locally.
- Add or update tests when you add or change agent or MCP behavior (e.g. unit tests for tools, graph nodes, or server endpoints). Fix any test or type errors until the suite is green.

## PR instructions

- **Title format:** `[agents] <Title>` or `[mcp] <Title>` (e.g. `[agents] Add tool X`, `[mcp] Fix state resource`).
- Run the agents example and any relevant checks before committing. If you touch the frontend or ROS 2 workspace, run `pnpm lint` / `./cli.sh test` as in [CONTRIBUTING.md](CONTRIBUTING.md).
- Keep this file (and the tool contract) in sync when you add or change agents or tools.
