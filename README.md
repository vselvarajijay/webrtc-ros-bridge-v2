# ConnectX

**Hardware Abstraction for Embodied AI**

ConnectX is a modular control runtime that separates robot intelligence from robot hardware.

It:
- Wraps native SDKs
- Streams control over WebRTC
- Provides a unified ROS 2 interface
- Exposes robot capabilities via MCP to LLM agents or planners

**The result:** portable autonomy, interchangeable hardware, and agent-driven control.

ConnectX is for development and research. Use in a safe environment; it is not intended for safety-critical or unsupervised operation.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=vselvarajijay/connectX&machine=basicLinux32gb&location=EastUs)

---

## Requirements

- **Docker** and **Docker Compose** — Used for the app, bridge, SDK, TURN server, and perception services.
- **pnpm** — For building the React app (`app/www`). Install from [pnpm.io](https://pnpm.io) or your package manager.
- **Python 3.10+** — For local scripts (e.g. `scripts/download_models.py`).

---

## Quick Start

```bash
# Copy env and set ROBOT_TYPE + any API keys for your robot (see .env.example)
cp .env.example .env

# Build Docker images (run once after clone or when deps change)
./cli.sh build

# Start the bridge and open a dev shell
./cli.sh start

# Stop the bridge
./cli.sh stop
```

Once running, open `http://localhost:8000` to access the live view interface:

- **Live video feed** — Real-time camera stream from the robot
- **Robot controls** — Drive with keyboard or on-screen controls
- **Telemetry dashboard** — Battery, speed, heading, and signal strength
- **Perception panels** — Optical flow and floor mask overlays

---

## Perception

Run `python3 scripts/download_models.py` once to download models, then `./cli.sh start` — perception runs automatically. Use `./scripts/test_perception.sh` to verify everything is working.

> **Note (Mac):** Relays use `APP_URL=http://host.docker.internal:8000`. On Linux, set `APP_URL=http://127.0.0.1:8000` in `.env` if needed.

---

## Adding a New Robot

**Currently supported:** `earth_rovers_sdk` (Earth Rovers). Set `ROBOT_TYPE=earth_rovers_sdk` in `.env` and configure the relevant variables in `.env.example`. To add another robot type:

### 1. Implement `RobotBase`

```python
# ros2_ws/src/connectx_robot_bridge/connectx_robot_bridge/robots/my_robot.py
from connectx_robot_bridge.core.robot_base import RobotBase
from connectx_robot_bridge.core.models.telemetry import TelemetryFrame

class MyRobot(RobotBase):
    def __init__(self): ...
    def move_forward(self): ...
    def move_backward(self): ...
    def move_left(self): ...
    def move_right(self): ...
    def stop(self): ...
    def get_front_camera_frame(self): ...  # return bytes or None
    def get_telemetry(self) -> TelemetryFrame: ...  # return TelemetryFrame or None
```

Optional overrides: `send_velocity(linear, angular)` for continuous control, `set_lamp(lamp)` if supported.

### 2. Register in the factory

```python
# connectx_robot_bridge/core/robot_factory.py
elif robot_type == "my_robot":
    return MyRobot()
```

### 3. Configure `.env`

```bash
ROBOT_TYPE=my_robot
MY_ROBOT_API_KEY=your_api_key_here
```

Copy `.env.example` to `.env` to see all available options.

---

## Troubleshooting

### Joystick / controls don't move the robot

1. **Check bridge logs** — `./cli.sh logs bridge` (or `docker compose --profile webrtc logs scout_bridge`). Look for:
   - **"Robot control ready (RTM client initialized)"** — Bridge has a robot and RTM; commands should reach the robot.
   - **"Robot instance created but RTM client not initialized"** — Auth failed. Set `SDK_API_TOKEN` and `BOT_SLUG` in `.env` (see `.env.example`). Restart the bridge.
   - **"cmd_vel received but no robot"** — Bridge is getting velocity commands but has no robot instance (wrong `ROBOT_TYPE` or auth). Fix env and restart.
   - **"cmd_vel -> robot: linear=..."** — Bridge is receiving joystick input and forwarding to the robot (about every 2 s when you drive).
   - **"First velocity command sent via RTM"** — At least one command was sent successfully over RTM.
   - **"RTM send_message returned False"** — API or network issue; token may be expired or robot not in channel.

2. **Env for Earth Rovers** — In `.env`: `SDK_API_TOKEN`, `BOT_SLUG`, and (if using missions) `MISSION_SLUG`. The bridge fetches `RTM_TOKEN`, `CHANNEL_NAME`, etc. from the FrodoBots API using these.

3. **Robot must be in channel** — The physical robot (or Earth Rovers SDK with browser joined) must be in the same Agora RTM channel to receive peer messages. If the robot is off or not joined, velocity commands will not reach it.

4. **Backward works but forward doesn't** — Some robots/SDK use the opposite linear sign. In `.env` set `EARTH_ROVERS_LINEAR_SIGN=-1`, then restart the bridge. Forward and backward should both work.

### Control message path (WebSocket vs WebRTC)

- **Default (joystick in UI):** Control goes **browser → WebRTC data channel → webrtc_node (ROS2 bridge)**. The signaling WebSocket is only used for SDP/ICE and telemetry; you will **not** see velocity messages in the WebSocket in DevTools.
- **To see control in the WebSocket:** Open the app with `?control_via_signaling=1` (e.g. `http://localhost:8000/?control_via_signaling=1`). Control is then sent **browser → API (WebSocket) → bridge**, so you can inspect the messages under Network → WS → your signaling connection.
- **API-driven control (e.g. MCP):** `POST /api/control` sends control over the robot’s signaling WebSocket (API → bridge). Same path as above, but from the server.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup, development workflow, and how to submit changes.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
