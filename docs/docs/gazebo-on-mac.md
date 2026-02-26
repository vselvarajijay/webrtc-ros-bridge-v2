# Running Gazebo on Mac (Docker)

## Why the GUI fails with XQuartz

When you run `gz sim shapes.sdf` in a container with `DISPLAY=host.docker.internal:0`, you see:

```text
No matching fbConfigs or visuals found
glx: failed to create drisw screen
```

**Cause:** XQuartz (the X11 server on macOS) only supports **OpenGL 1.4 / 2.1**. Gazebo Sim needs **OpenGL 3.3+**. So the container cannot create a compatible GL context through X11 forwarding to the Mac. This is a limitation of XQuartz, not something that can be fixed with env vars or software rendering in the container.

## What works

### 1. Headless in Docker (recommended on Mac)

Run Gazebo **without a display** using EGL (no X server). The simulation runs; you just don't get a 3D window.

**One-off run:**

```bash
docker run -it --rm \
  -e DISPLAY= \
  osrf/ros:kilted-desktop-full \
  bash -c "gz sim -s -r --headless-rendering shapes.sdf"
```

Or with docker compose (if the `gazebo` service is defined):

```bash
docker compose --profile gazebo up gazebo
```

Flags:

- `-s`: server-only
- `-r`: run simulation (required so it starts without a GUI)
- `--headless-rendering`: use EGL instead of X11/GLX

Use this for testing, CI, or when you don't need to see the scene (e.g. sensors, logging).

### 2. GUI via Robostack (native, no Docker)

For a **visible** Gazebo window on Mac M4, run ROS + Gazebo natively with [Robostack](https://github.com/RoboStack/robostack) (conda). No XQuartz, no Docker display forwarding; the app uses the Mac display and OpenGL directly.

```bash
conda install -c robostack-staging ros-kilted-desktop
conda install -c robostack-staging ros-kilted-gz-sim-vendor  # or the Kilted-equivalent gz package
# then run gz sim in that environment
```

### 3. GUI via VNC (advanced)

Run an X server + VNC **inside** the container so OpenGL is used inside the container (e.g. Mesa software rendering), and you connect with a VNC client. This requires a custom image or installing TigerVNC + Xvfb and a desktop in the container, then exposing a VNC port. Not covered here.

## Image note

`osrf/ros:kilted-desktop-full` is published only for **linux/amd64**. On Apple Silicon (M4), Docker runs it under emulation. That’s fine for headless; for a responsive GUI, prefer Robostack (native arm64).
