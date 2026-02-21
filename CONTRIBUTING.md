# Contributing to ConnectX

Thank you for your interest in contributing to ConnectX. This document explains how to get set up, run the project, and submit changes.

---

## Prerequisites

- **Docker & Docker Compose** — Used for the app, bridge, SDK, TURN server, and perception services.
- **pnpm** — For building the React app (`app/www`). Install from [pnpm.io](https://pnpm.io) or your package manager.
- **Python 3.10+** — For local scripts (e.g. `scripts/download_models.py`).
- **Git** — For cloning and branching.

Familiarity with **ROS 2** and **WebRTC** is helpful but not required for frontend or app-server changes.

---

## Development Setup

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd connectX
```

Copy the example env file and edit as needed (never commit `.env` or secrets):

```bash
cp .env.example .env
# Edit .env — set ROBOT_TYPE and any API keys for your robot/SDK.
```

### 2. Build and run

```bash
./cli.sh build
./cli.sh start
```

Then open **http://localhost:8000** for the live view (video, controls, telemetry, perception).

- **Stop:** `./cli.sh stop`
- **Rebuild and restart:** `./cli.sh rebuild`
- **View logs:** `./cli.sh logs [webrtc|app|sdk|bridge|perception|all]`

### 3. Perception (optional)

To use optical flow and floor mask overlays:

```bash
python3 scripts/download_models.py   # once
./scripts/test_perception.sh        # verify
```

Perception runs automatically when you `./cli.sh start`.

---

## Project Structure

| Area | Description |
|------|-------------|
| `app/www` | React + TypeScript + Vite frontend (Mantine, Tailwind). Built and served by the app container. |
| `app/server` | Python FastAPI app (signaling, etc.). |
| `ros2_ws/` | ROS 2 workspace: bridge, controller, planner, teleop, perception packages. |
| `scripts/` | Helpers (e.g. `download_models.py`, `test_perception.sh`). |
| `cli.sh` | Main CLI: build, start, stop, rebuild, teleop, test, logs, clean. |

---

## How to Contribute

### Reporting issues

- Open an issue with a clear title and steps to reproduce.
- Include OS, Docker version, and relevant logs if applicable.

### Submitting changes

1. **Fork** the repo and create a **branch** from `main` (e.g. `fix/typo-readme` or `feat/my-robot`).
2. **Make your changes** and keep commits focused.
3. **Run checks** (see below).
4. **Push** your branch and open a **Pull Request** against `main`.
5. In the PR, describe what changed and how to test it.

---

## Code style and tests

### Frontend (`app/www`)

- **Lint:** `cd app/www && pnpm lint`
- **Build:** `cd app/www && pnpm build`

Fix any ESLint errors before submitting. The project uses TypeScript and React with ESLint (including React hooks and refresh plugins).

### ROS 2 workspace

- **Tests:** Run inside the bridge container:

  ```bash
  ./cli.sh test
  ```

  This runs `colcon test` in the ROS 2 workspace. Ensure tests pass before opening a PR.

### Python (app/server, scripts)

- Use Python 3.10+.
- Follow existing style (e.g. consistent naming and docstrings). No formal linter is required; keep code readable and consistent with the rest of the repo.

---

## Adding a new robot

See the **Adding a New Robot** section in [README.md](README.md). In short:

1. Implement `RobotBase` in `ros2_ws/src/connectx_robot_bridge/.../robots/my_robot.py`.
2. Register the robot in `connectx_robot_bridge/core/robot_factory.py`.
3. Add any needed config to `.env` (use `.env.example` as reference).

---

## Quick reference

| Task | Command |
|------|---------|
| Build images & ROS 2 workspace | `./cli.sh build` |
| Start services | `./cli.sh start` |
| Stop services | `./cli.sh stop` |
| Rebuild and start | `./cli.sh rebuild` |
| Run ROS 2 tests | `./cli.sh test` |
| Lint frontend | `cd app/www && pnpm lint` |
| Build frontend | `cd app/www && pnpm build` |
| Keyboard teleop | `./cli.sh teleop` or `./cli.sh start --teleop` |

---

If you have questions, open an issue and we’ll do our best to help.
