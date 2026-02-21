# ConnectX

**Write once, run on any robot.**

ConnectX lets you build control systems that work across different robot hardware without rewriting code for each platform. Connect any robot's native SDK over WebRTC and your autonomy stack stays hardware-agnostic.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=vselvarajijay/connectX&machine=basicLinux32gb&location=EastUs)

---

## Quick Start

```bash
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
