#!/usr/bin/env bash
set -e

# On macOS, allow X11 connections from Docker VM (XQuartz: Preferences → Security → "Allow connections from network clients")
# Do not export DISPLAY here — xterm runs on the host and needs the host's display (e.g. :0).
if [[ "$(uname)" == Darwin ]]; then
  if command -v xhost &>/dev/null; then
    xhost + 127.0.0.1 2>/dev/null || true
    xhost + host.docker.internal 2>/dev/null || true
  fi
else
  if command -v xhost &>/dev/null; then
    xhost +local:docker 2>/dev/null || true
  fi
fi

# Run container with a shell that has ROS 2 Kilted sourced.
# From that shell you can run: rviz2, rqt, ros2 run turtlesim turtlesim_node, etc.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if container is already running
CONTAINER_RUNNING=$(docker compose ps -q ros2-kilted 2>/dev/null | head -n 1)

if [ -n "$CONTAINER_RUNNING" ] && [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_RUNNING" 2>/dev/null)" = "true" ]; then
  # Container is running, attach to it with exec
  echo "Attaching to existing container ros2-kilted..."
  RUN_CMD="docker compose exec ros2-kilted bash -c 'source /opt/ros/kilted/setup.bash && exec bash -l'"
else
  # Container not running, start it first then attach
  echo "Starting container ros2-kilted..."
  # On macOS, ensure DISPLAY is set for the container when starting
  if [[ "$(uname)" == Darwin ]]; then
    DISPLAY=host.docker.internal:0 docker compose up -d ros2-kilted
  else
    docker compose up -d ros2-kilted
  fi
  # Wait a moment for container to be ready
  sleep 1
  RUN_CMD="docker compose exec ros2-kilted bash -c 'source /opt/ros/kilted/setup.bash && exec bash -l'"
fi

if command -v xterm &>/dev/null; then
  xterm -e "$RUN_CMD"
else
  echo "xterm not found; running in current terminal. Install xterm for a separate window."
  eval "$RUN_CMD"
fi
