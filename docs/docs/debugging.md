---
sidebar_position: 2
title: Debugging
---

# Debugging

Notes on how to debug the ConnectX stack: bridge, controls, and message paths.

## Joystick / controls don't move the robot

1. **Check bridge logs** — `./cli.sh logs bridge` (or `docker compose --profile webrtc logs scout_bridge`). Look for:
   - **"Robot control ready (RTM client initialized)"** — Bridge has a robot and RTM; commands should reach the robot.
   - **"Robot instance created but RTM client not initialized"** — Auth failed. Set `SDK_API_TOKEN` and `BOT_SLUG` in `.env` (see `.env.example`). Restart the bridge.
   - **"cmd_vel received but no robot"** — Bridge is getting velocity commands but has no robot instance (wrong `ROBOT_TYPE` or auth). Fix env and restart.
   - **"cmd_vel -> robot: linear=..."** — Bridge is receiving joystick input and forwarding to the robot (first few messages log immediately, then about every 2 s when you drive).
   - **"First velocity command sent via RTM"** — At least one command was sent successfully over RTM.
   - **"RTM send_message returned False"** — API or network issue; token may be expired or robot not in channel.

2. **Env for Earth Rovers** — In `.env`: `SDK_API_TOKEN`, `BOT_SLUG`, and (if using missions) `MISSION_SLUG`. The bridge fetches `RTM_TOKEN`, `CHANNEL_NAME`, etc. from the FrodoBots API using these.

3. **Robot must be in channel** — The physical robot (or Earth Rovers SDK with browser joined) must be in the same Agora RTM channel to receive peer messages. If the robot is off or not joined, velocity commands will not reach it.

4. **Backward works but forward doesn't** — Some robots/SDK use the opposite linear sign. In `.env` set `EARTH_ROVERS_LINEAR_SIGN=-1`, then restart the bridge. Forward and backward should both work.

## Control message path (WebSocket vs WebRTC)

- **Default (joystick in UI):** Control goes **browser → WebRTC data channel → webrtc_node (ROS2 bridge)**. The signaling WebSocket is only used for SDP/ICE and telemetry; you will **not** see velocity messages in the WebSocket in DevTools.
- **To see control in the WebSocket:** Open the app with `?control_via_signaling=1` (e.g. `http://localhost:8000/?control_via_signaling=1`). Control is then sent **browser → API (WebSocket) → bridge**, so you can inspect the messages under Network → WS → your signaling connection.
- **API-driven control (e.g. MCP):** `POST /api/control` sends control over the robot's signaling WebSocket (API → bridge). Same path as above, but from the server.
