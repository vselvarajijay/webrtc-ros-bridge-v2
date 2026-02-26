# Gazebo Simulation Pipeline (ConnectX)

This doc describes the full simulation pipeline: Gazebo Ionic (headless) in Docker, ros_gz_bridge, and Foxglove Studio for 3D visualization on Mac M4 (Apple Silicon).

## Build and run

**1. Build the image (first time or after changing the simulation package):**

```bash
cd /path/to/connectX
docker compose --profile gazebo build gazebo
```

**2. Start the simulation:**

```bash
docker compose --profile gazebo up gazebo
```

**3. Connect Foxglove Studio:**

- Run `./scripts/open-foxglove-gazebo.sh` to open the desktop app and connect to `ws://localhost:8766`, or
- Open Foxglove Studio (desktop or [app.foxglove.dev](https://app.foxglove.dev)) → **Open connection** → **Foxglove WebSocket** → URL: **`ws://localhost:8766`** → **Open**.
- For the full setup (3D panel with robot URDF, IMU, TF): see **foxglove/README.md** — first-time setup creates the layout, then export as `foxglove/connectx-gazebo-layout.json`; others import that file to get the same panels.

**4. (Optional) Verify ROS topics inside the container:**

```bash
docker exec -it gazebo_sim bash
source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash
ros2 topic list
# Expect: /clock, /imu/data, /joint_states, /model_pose, /robot_description, /room_walls, /urdf/robot_description, /tf (no camera in headless)
ros2 node list | grep -E "room_walls|pose_to_tf"
# If /room_walls is missing, check: docker compose --profile gazebo logs gazebo 2>&1 | grep -E "room_walls|error"
```

**Stop:** `Ctrl+C` in the terminal, or `docker compose --profile gazebo down`.

**5. Drive the sim from the web UI:**

- Open the app (e.g. http://localhost:8000). In the **Drive** section, set **Drive target** to **Simulator** (not Physical). Then use the arrow keys or on-screen controls; commands are sent to the Gazebo sim via `sim_control_relay`. If the robot does not move, confirm the target is **Simulator** and that the `gazebo_sim` container is running.

---

## Pipeline

```
Gazebo Ionic (headless, Docker)
        ↓  gz topics (camera, IMU, pose, joints)
  ros_gz_bridge (parameter bridge)
        ↓  ROS 2 topics
  foxglove_bridge (port 8766 in gazebo container)
        ↓  WebSocket ws://localhost:8766
  Foxglove Studio (desktop app, Mac)
```

## Quick start

```bash
# Build and run simulation + Foxglove bridge
docker compose --profile gazebo up --build

# In Foxglove Studio: Open connection → Foxglove WebSocket → ws://localhost:8766
```

## What runs

- **Gazebo Ionic** — headless sim with a simple 4-wheel box car in a flat world (no camera in Docker to avoid Ogre2 crash). The box_car model uses the **DiffDrive** plugin and subscribes to `/model/box_car/cmd_vel` (Gazebo Transport).
- **ros_gz_bridge** — bridges `/clock`, `/imu/data`, `/joint_states` from Gazebo to ROS 2, and **ROS → GZ** `/cmd_vel_sim` → `/model/box_car/cmd_vel` for teleop (camera omitted for headless).
- **robot_state_publisher** — publishes `/robot_description` and TF for the box car URDF (for Foxglove 3D).
- **foxglove_bridge** — exposes ROS 2 topics to Foxglove Studio on port **8766** (gazebo profile only).

Gazebo uses **ROS_DOMAIN_ID** from `ROS_DOMAIN_ID_GAZEBO` (default **1**) so it does not see nodes from the webrtc profile (e.g. `/bridge_node`). That avoids Foxglove errors like "Failed to retrieve parameters from node '/bridge_node'". Set `ROS_DOMAIN_ID_GAZEBO=0` in `.env` if you need sim and bridge on the same ROS domain.

Webrtc profile uses Foxglove on port **8765** (scout_bridge). Use **8766** when only the gazebo profile is running.

## Foxglove panels

| Panel         | Config |
|--------------|--------|
| **3D**       | **Fixed frame:** `world`. Add **URDF** from **Source → URL** → **`http://localhost:8767/box_car.urdf`** (or topic `/urdf/robot_description`). Enable **Grid** for ground reference. |
| **Image**    | Not available in headless Docker (camera disabled to avoid Ogre2 crash). |
| **Raw Messages** | Topic: `/imu/data` (e.g. `linear_acceleration.z ≈ 9.8`) |
| **TF**       | Inspect chain: `chassis` → `wheel_fl`, `wheel_fr`, `wheel_rl`, `wheel_rr` |

## Verify inside container

```bash
docker exec -it gazebo_sim bash
source /opt/ros/kilted/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 topic list
# Expect: /clock, /imu/data, /joint_states, /robot_description, /urdf/robot_description, /tf (no camera in headless)
```

## File layout

- `ros2_ws/src/connectx_simulation/` — ROS 2 package (launch, config, URDF, SDF model, world).
- `docker/Dockerfile.simulation` — Image with Gazebo Ionic, ros_gz_bridge, robot_state_publisher, foxglove_bridge, and pre-built connectx_simulation.

## Troubleshooting

- **Headless in Docker:** The **camera sensor and Sensors plugin are disabled** so the sim runs without loading Ogre2 (which crashes with double-free in headless Docker). You get physics, IMU, joint states, and TF; no camera image. To use the camera, run Gazebo with a display or wait for an upstream fix in gz-rendering.
- **Joint state / TF not showing:** Confirm gz topic names with `gz topic --list` in the container and adjust `config/bridge_params.yaml` if your world/model names differ.
- **Package names:** If the image build fails on apt install, run:
  `docker run --rm osrf/ros:kilted-desktop-full apt-cache search ros-kilted-ros-gz`
  and align package names in `Dockerfile.simulation`.

## Full stack (webrtc + gazebo)

```bash
docker compose --profile webrtc --profile gazebo up --build
```

Use **ws://localhost:8766** in Foxglove for simulation topics (port 8766 is published from the gazebo container).

### Controlling the simulator from the teleop UI

When both the **webrtc** and **gazebo** profiles are running:

1. **ROS 2 network:** `scout_bridge` and `gazebo_sim` use `ROS_LOCALHOST_ONLY=0` by default (via `ROS_LOCALHOST_ONLY` in docker-compose, defaulting to `0`) so that DDS discovery works across containers. The webrtc_node in scout_bridge publishes `/cmd_vel_sim` when you select **Simulator** in the UI; ros_gz_bridge in the gazebo container subscribes to `/cmd_vel_sim` and forwards it to the box_car DiffDrive plugin.
2. In the web UI at **http://localhost:8000**, open the **Controls** panel. Use the **Physical** | **Simulator** selector: choose **Simulator** to drive the box_car in Gazebo with the joystick or arrow keys; choose **Physical** to drive the physical robot (existing behavior).
3. If the sim does not move when **Simulator** is selected, ensure both profiles are up and that `ROS_LOCALHOST_ONLY` is not set to `1` in your environment (so the two containers share the same ROS 2 network).
