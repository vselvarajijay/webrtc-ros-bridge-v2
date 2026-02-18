# WebRTC ROS Bridge v2

## Overview

**Write once, run on any robot.** This bridge lets you build ROS 2 control systems that work across different robot hardware without rewriting code for each platform. Connect any robot's native SDK over WebRTC, and your autonomy stack stays hardware-agnostic. Each robot maintains its own configuration while sharing the same control logic.

## What's in this repo

A ROS 2 (Kilted) workspace with WebRTC bridge, containerized with Docker. Connect your robot SDK to the bridge and your control system can communicate with that hardware.

---

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose**
- **macOS only**: [XQuartz](https://www.xquartz.org/) for GUI support (RViz, etc.)
  - Open XQuartz → **Preferences → Security**
  - Enable **"Allow connections from network clients"**
  - Restart XQuartz after changing this setting
- **Optional**: `xterm` for separate terminal windows

### Build and run

Each ROS 2 package runs in its own container. From the project root:

```bash
# Build Docker images and the ROS 2 workspace (run once after clone or when deps change)
./cli.sh build

# Start scout_bridge and scout_perception, then open a dev shell (for teleop, rqt, etc.)
./cli.sh start

# Open the dev shell in a separate xterm window
./cli.sh start --xterm

# Stop the bridge and perception containers
./cli.sh stop
```

**Containers:**

- **scout_bridge** – runs `bridge_node` (robot control and front camera).
- **scout_perception** – placeholder for the perception node (runs until you add the node).
- **scout_shell** – dev shell with ROS 2 and workspace sourced; used by `./cli.sh start` for interactive use.

The workspace is mounted in all containers, so one `./cli.sh build` is shared by every service.

### Robot controls

**Arrow keys (recommended):**

```bash
ros2 run scout_robot_bridge teleop_node
```

Use **Up** (forward), **Down** (back), **Left** / **Right** (turn). Ctrl+C to quit.

**Alternative (i/j/k/l):** `ros2 run teleop_twist_keyboard teleop_twist_keyboard`

The bridge subscribes to `/cmd_vel` and maps Twist to discrete move commands, then sends them to the robot via the Earth Rovers SDK (RTM).

**If commands don’t reach the robot** (teleop shows "Publishing" but bridge never shows "cmd_vel received"):

- **Run teleop in the same container as the bridge** so ROS 2 discovery works. In a **new terminal** on the host:

  ```bash
  docker compose exec scout_bridge bash -c 'source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && ros2 run scout_robot_bridge teleop_node'
  ```

  Watch bridge logs in another terminal: `docker compose logs -f scout_bridge` — you should see `cmd_vel received: linear.x=...` for each keypress.

- **Confirm the bridge is running:** `docker compose ps` — `scout_bridge` should be Up.

- **If you see `cmd_vel received but no robot`:** the bridge has no robot instance (check `.env`: `SDK_API_TOKEN`, `BOT_SLUG`, etc.).

- **Rebuild after code changes:** `./cli.sh build` then `./cli.sh stop` and `./cli.sh start`.

### Front camera

The bridge publishes the front camera on `/camera/front/compressed` by loading the Earth Rovers SDK page in a headless browser. If you see:

```text
Error initializing browser: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8000/sdk
```

then nothing is serving that URL. The bridge expects the **Earth Rovers SDK web app** to be running at `http://127.0.0.1:8000`. With `network_mode: host`, the container uses the host’s network, so run the SDK server on the host (or in another container with port 8000 published to the host). For example, from the repo:

```bash
cd ros2_ws/src/scout_robot_bridge/scout_robot_bridge/robot_sdk/earth_rovers_sdk
pip install -r requirements.txt   # or install deps as needed
python main.py
```

Then the bridge can load `http://127.0.0.1:8000/sdk` and publish frames. If you don’t need the camera stream, you can ignore this error; move commands and the rest of the bridge still work.

### WebRTC live view

Stream the robot's front camera to the browser over WebRTC and control the robot from the app (arrow keys).

**Startup order:**

1. **Start the stack** with the webrtc profile (app, Earth Rovers SDK, scout_bridge, scout_perception, scout_webrtc):

   ```bash
   ./cli.sh build   # if not already built
   ./cli.sh start   # starts app, SDK, bridge, perception, webrtc
   ```

2. **Open the app** in your browser at `http://localhost:8000`. The page shows a live view area and telemetry panel.

3. **Front camera source:** For the stream to show, the bridge must be publishing `/camera/front/compressed`. The **scout_sdk** container runs the Earth Rovers SDK on port 8001; the bridge uses it by default (`SDK_LOCAL_URL=http://host.docker.internal:8001`). Without the SDK running, the live view stays on "Waiting for robot stream…".

**Containers (webrtc profile):**

- **scout_app** – FastAPI app (signaling WebSocket + static page) on port 8000.
- **scout_sdk** – Earth Rovers SDK (/v2/front, /data) on port 8001; runs in Docker so no host pip install needed.
- **scout_bridge** – `bridge_node`: robot control and front camera publisher on `/camera/front/compressed` (gets frames from scout_sdk).
- **scout_webrtc** – `webrtc_node`: subscribes to the camera topic, sends video over WebRTC to the app. Uses **host network** so it shares the host ROS 2 network with scout_bridge; connects to the app at `ws://host.docker.internal:8000/ws/signaling`.

---

## Architecture

```
Robot SDK (native) ←→ WebRTC ←→ Bridge ←→ ROS 2 (your control logic)
```

The bridge handles:
- Protocol translation between robot SDK and ROS 2
- Message standardization across different platforms
- Robot-specific configuration management
- Real-time WebRTC communication

---

## Next Steps

1. **Add your robot SDK** to the bridge
2. **Configure** robot-specific parameters (topics, limits, transforms)
3. **Deploy** your ROS 2 control logic
4. **Scale** to additional robot types using the same codebase