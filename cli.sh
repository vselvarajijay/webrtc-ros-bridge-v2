#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

cmd="${1:-}"
shift || true

# Shared env for compose (macOS X11)
export COMPOSE_DISPLAY="${DISPLAY:-host.docker.internal:0}"

case "$cmd" in
  build)
    echo "Building Docker images..."
    docker compose build
    echo "Building ROS 2 workspace in container..."
    docker compose run --rm scout_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && colcon build"
    echo "Build complete. Run ./cli.sh start to start services and open a shell."
    ;;
  start)
    USE_XTERM=false
    for arg in "$@"; do
      if [[ "$arg" == "--xterm" ]]; then
        USE_XTERM=true
        break
      fi
    done

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

    echo "Starting scout_bridge and scout_perception..."
    if [[ "$(uname)" == Darwin ]]; then
      DISPLAY=host.docker.internal:0 docker compose up -d scout_bridge scout_perception
    else
      docker compose up -d scout_bridge scout_perception
    fi
    sleep 1

    echo "Opening dev shell (scout_shell)..."
    RUN_CMD="docker compose --profile shell run --rm -it scout_shell bash -c 'source /opt/ros/kilted/setup.bash && [ -f /root/workspace/.env ] && set -a && source /root/workspace/.env && set +a; source install/setup.bash 2>/dev/null || true; exec bash -l'"
    if [[ "$USE_XTERM" == true ]]; then
      if command -v xterm &>/dev/null; then
        xterm -e "$RUN_CMD"
      else
        echo "xterm not found; running in current terminal."
        eval "$RUN_CMD"
      fi
    else
      eval "$RUN_CMD"
    fi
    ;;
  stop)
    echo "Stopping scout_bridge and scout_perception..."
    docker compose stop scout_bridge scout_perception
    echo "Stopped. Run ./cli.sh start to start again."
    ;;
  *)
    echo "Usage: $0 {build|start|stop} [options]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker images and ROS 2 workspace (run once after clone or when deps change)"
    echo "  start       Start scout_bridge and scout_perception, then open a dev shell"
    echo "               Options: --xterm  Open the shell in a separate xterm window"
    echo "  stop        Stop scout_bridge and scout_perception"
    exit 1
    ;;
esac
