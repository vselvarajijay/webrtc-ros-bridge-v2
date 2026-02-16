# WebRTC ROS Bridge v2

ROS 2 (Kilted) workspace and WebRTC bridge, run inside Docker.

## Prerequisites

- **Docker** and **Docker Compose**
- **macOS**: [XQuartz](https://www.xquartz.org/) for X11 (GUI apps like RViz). In XQuartz: **Preferences → Security** → enable **"Allow connections from network clients"**
- **Optional**: `xterm` — use with `./cli.sh start --xterm` to open the shell in a separate window

## CLI

From the project root, use `cli.sh` for all commands:

```bash
./cli.sh start          # Start (or attach to) container, open shell in current terminal
./cli.sh start --xterm  # Same, but open shell in a separate xterm window
./cli.sh stop           # Stop the container
```

**start** — Starts the `ros2-ws` container (if not already running) and opens a shell with ROS 2 sourced. From that shell you can run:

- `rviz2`, `rqt`, or any ROS 2 nodes from your workspace
- Your workspace is mounted at `/root/workspace` (e.g. `ros2_ws` at `/root/workspace/ros2_ws`)
