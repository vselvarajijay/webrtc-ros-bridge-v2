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
source /opt/ros/kilted/setup.bash && source /root/ros2_ws/install/setup.bash
ros2 topic list
# Expect: /clock, /imu/data, /joint_states, /robot_description, /urdf/robot_description, /tf (no camera in headless)
```

**Stop:** `Ctrl+C` in the terminal, or `docker compose --profile gazebo down`.

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

- **Gazebo Ionic** — headless sim with a simple 4-wheel box car in a flat world (no camera in Docker to avoid Ogre2 crash).
- **ros_gz_bridge** — bridges `/clock`, `/imu/data`, `/joint_states` from Gazebo to ROS 2 (camera omitted for headless).
- **robot_state_publisher** — publishes `/robot_description` and TF for the box car URDF (for Foxglove 3D).
- **foxglove_bridge** — exposes ROS 2 topics to Foxglove Studio on port **8766** (gazebo profile only).

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
