#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

cmd="${1:-}"
shift || true

case "$cmd" in
  start)
    USE_XTERM=false
    for arg in "$@"; do
      if [[ "$arg" == "--xterm" ]]; then
        USE_XTERM=true
        break
      fi
    done

    # On macOS, allow X11 connections from Docker VM (XQuartz: Preferences → Security → "Allow connections from network clients")
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

    CONTAINER_RUNNING=$(docker compose ps -q ros2-ws 2>/dev/null | head -n 1)

    if [ -n "$CONTAINER_RUNNING" ] && [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_RUNNING" 2>/dev/null)" = "true" ]; then
      echo "Attaching to existing container ros2-ws..."
      RUN_CMD="docker compose exec ros2-ws bash -c 'source /opt/ros/kilted/setup.bash && exec bash -l'"
    else
      echo "Starting container ros2-ws..."
      if [[ "$(uname)" == Darwin ]]; then
        DISPLAY=host.docker.internal:0 docker compose up -d ros2-ws
      else
        docker compose up -d ros2-ws
      fi
      sleep 1
      RUN_CMD="docker compose exec ros2-ws bash -c 'source /opt/ros/kilted/setup.bash && exec bash -l'"
    fi

    if [[ "$USE_XTERM" == true ]]; then
      if command -v xterm &>/dev/null; then
        xterm -e "$RUN_CMD"
      else
        echo "xterm not found; running in current terminal. Install xterm for a separate window."
        eval "$RUN_CMD"
      fi
    else
      eval "$RUN_CMD"
    fi
    ;;
  stop)
    echo "Stopping container ros2-ws..."
    docker compose stop ros2-ws
    echo "Container stopped. Run ./cli.sh start to start it again."
    ;;
  *)
    echo "Usage: $0 {start|stop} [options]"
    echo ""
    echo "Commands:"
    echo "  start        Start (or attach to) the ros2-ws container and open a shell with ROS 2 sourced"
    echo "               Options: --xterm  Open the shell in a separate xterm window"
    echo "  stop         Stop the ros2-ws container"
    exit 1
    ;;
esac
