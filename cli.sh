#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use BuildKit for cache mounts (apt, pip, cv_bridge) in scout_perception Dockerfile
export DOCKER_BUILDKIT=1

cmd="${1:-}"
shift || true

# Shared env for compose (macOS X11)
export COMPOSE_DISPLAY="${DISPLAY:-host.docker.internal:0}"

# App server (signaling) PID file for start/stop
APP_PID_FILE="${SCRIPT_DIR}/.cli-app-server.pid"

case "$cmd" in
  build)
    echo "Removing any existing containers that might conflict..."
    docker rm -f scout_app scout_sdk scout_bridge scout_perception scout_webrtc scout_shell scout_turn 2>/dev/null || true
    docker compose --profile webrtc down --remove-orphans 2>/dev/null || true
    echo ""
    if [[ -f app/www/package.json ]]; then
      if command -v pnpm &>/dev/null; then
        echo "Building React app (app/www) so the app image serves the latest UI..."
        (cd app/www && pnpm build) || { echo "Warning: pnpm build failed; :8000 may serve an old or broken UI."; }
      else
        echo "Skipping React app build (pnpm not found). Run: cd app/www && pnpm build  then rebuild for latest UI."
      fi
    fi
    echo "Building Docker images (app, bridge, SDK, ...)..."
    # Try --remove-orphans, fall back if not supported
    docker compose --profile webrtc build --remove-orphans 2>/dev/null || docker compose --profile webrtc build
    echo "Building ROS 2 workspace in container..."
    docker compose --profile webrtc run --rm scout_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && rm -rf build/connectx_msgs install/connectx_msgs build/connectx_perception_cpp install/connectx_perception_cpp && colcon build"
    echo "Build complete. Run ./cli.sh start to start services and open a shell."
    ;;
  start)
    USE_XTERM=false
    RUN_TELEOP=false
    for arg in "$@"; do
      if [[ "$arg" == "--xterm" ]]; then
        USE_XTERM=true
        RUN_TELEOP=true
      elif [[ "$arg" == "--teleop" ]]; then
        RUN_TELEOP=true
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

    # Clear any stale host app PID (app now runs in container when using webrtc profile)
    if [[ -f "$APP_PID_FILE" ]]; then
      old_pid=$(cat "$APP_PID_FILE" 2>/dev/null)
      if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
        kill "$old_pid" 2>/dev/null || true
        sleep 1
      fi
      rm -f "$APP_PID_FILE"
    fi

    echo "Starting app (signaling + www), scout_turn, scout_sdk, scout_bridge, scout_perception..."
    if [[ "$(uname)" == Darwin ]]; then
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d --remove-orphans app scout_turn scout_sdk scout_bridge scout_perception 2>/dev/null || \
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d app scout_turn scout_sdk scout_bridge scout_perception
    else
      docker compose --profile webrtc up -d --remove-orphans app scout_turn scout_sdk scout_bridge scout_perception 2>/dev/null || \
      docker compose --profile webrtc up -d app scout_turn scout_sdk scout_bridge scout_perception
    fi
    # Give scout_sdk time to bind to 8001 before scout_bridge hits /v2/front (depends_on only waits for start, not ready)
    echo "Waiting for services to be ready..."
    sleep 5
    echo ""
    echo "App (signaling + www): http://localhost:8000/"
    echo "Earth Rovers SDK (front camera, /v2/front): http://localhost:8001/"
    echo ""
    echo "Foxglove Studio (ROS 2 visualization):"
    echo "  1. Open Foxglove Studio: https://app.foxglove.dev/  (or install the desktop app)"
    echo "  2. Add connection → Foxglove WebSocket"
    echo "  3. URL: ws://localhost:8765"
    echo "  4. Connect to view /cmd_vel, /camera/front/compressed, /robot/telemetry, and other ROS 2 topics."
    echo ""
    echo "Perception (optical flow, floor mask): scout_perception runs automatically. Run once: python3 scripts/download_models.py"
    echo ""
    if [[ "$RUN_TELEOP" == true ]]; then
      echo "Opening teleop (keyboard control) — do not drive from the web UI at the same time (both use /cmd_vel)."
      RUN_CMD="docker compose --profile webrtc exec -it scout_bridge bash -c 'source /opt/ros/kilted/setup.bash && [ -f /root/workspace/.env ] && set -a && source /root/workspace/.env && set +a; source /root/workspace/ros2_ws/install/setup.bash && (ros2 run connectx_controller manual_controller &) && sleep 0.5 && exec ros2 run connectx_teleop keyboard_node'"
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
    else
      echo "Drive from the web UI: http://localhost:8000/"
      echo "Tap on the front camera to orient the robot (rotation only; uses autonomy controller)."
      echo "Use Start wandering / Stop wandering in the Drive section (speed uses the same slider as drive)."
      echo "To use keyboard teleop instead: ./cli.sh teleop   or   ./cli.sh start --teleop"
    fi
    ;;
  stop)
    echo "Stopping app, scout_turn, scout_sdk, scout_bridge, scout_perception..."
    docker compose --profile webrtc stop app scout_turn scout_sdk scout_bridge scout_perception
    if [[ -f "$APP_PID_FILE" ]]; then
      pid=$(cat "$APP_PID_FILE" 2>/dev/null)
      if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$APP_PID_FILE"
    fi
    # Kill any process still listening on 8000 (e.g. host-run app or SDK server)
    pids=$(lsof -i :8000 -t 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "Stopping process(es) on port 8000: $pids"
      for pid in $pids; do
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
      done
    fi
    pids=$(lsof -i :8001 -t 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "Stopping process(es) on port 8001: $pids"
      for pid in $pids; do
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
      done
    fi
    echo "Stopped. Run ./cli.sh start to start again."
    ;;
  clean)
    echo "Removing orphaned containers..."
    docker compose --profile webrtc down --remove-orphans 2>/dev/null || docker compose down --remove-orphans
    echo "Orphaned containers removed."
    ;;
  rebuild)
    echo "=== Rebuild: Stopping services ==="
    docker compose --profile webrtc stop app scout_turn scout_sdk scout_bridge scout_perception 2>/dev/null || true
    if [[ -f "$APP_PID_FILE" ]]; then
      pid=$(cat "$APP_PID_FILE" 2>/dev/null)
      if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$APP_PID_FILE"
    fi
    echo ""
    if [[ -f app/www/package.json ]]; then
      if command -v pnpm &>/dev/null; then
        echo "=== Rebuild: Building React app (app/www) ==="
        (cd app/www && pnpm build) || { echo "Warning: pnpm build failed; :8000 may serve an old or broken UI."; }
      else
        echo "Skipping React app build (pnpm not found). Run: cd app/www && pnpm build  then rebuild for latest UI."
      fi
    fi
    echo ""
    echo "=== Rebuild: Building Docker images and ROS 2 workspace ==="
    docker rm -f scout_app scout_sdk scout_bridge scout_perception scout_webrtc scout_shell scout_turn 2>/dev/null || true
    docker compose --profile webrtc down --remove-orphans 2>/dev/null || true
    docker compose --profile webrtc build --remove-orphans 2>/dev/null || docker compose --profile webrtc build
    docker compose --profile webrtc run --rm scout_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && rm -rf build/connectx_msgs install/connectx_msgs build/connectx_perception_cpp install/connectx_perception_cpp && colcon build"
    echo ""
    echo "=== Rebuild: Starting services ==="
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
    if [[ "$(uname)" == Darwin ]]; then
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d --remove-orphans app scout_turn scout_sdk scout_bridge scout_perception 2>/dev/null || \
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d app scout_turn scout_sdk scout_bridge scout_perception
    else
      docker compose --profile webrtc up -d --remove-orphans app scout_turn scout_sdk scout_bridge scout_perception 2>/dev/null || \
      docker compose --profile webrtc up -d app scout_turn scout_sdk scout_bridge scout_perception
    fi
    echo "Waiting for services to be ready..."
    sleep 5
    echo ""
    echo "Rebuild complete! Services are running."
    echo ""
    echo "App (signaling + www): http://localhost:8000/"
    echo "Earth Rovers SDK (front camera, /v2/front): http://localhost:8001/"
    echo ""
    echo "Foxglove Studio (ROS 2 visualization):"
    echo "  1. Open Foxglove Studio: https://app.foxglove.dev/  (or install the desktop app)"
    echo "  2. Add connection → Foxglove WebSocket"
    echo "  3. URL: ws://localhost:8765"
    echo "  4. Connect to view /cmd_vel, /camera/front/compressed, /robot/telemetry, and other ROS 2 topics."
    echo ""
    echo "Drive from the web UI: http://localhost:8000/"
    echo "Tap on the front camera to orient the robot (rotation only; uses autonomy controller)."
    echo "Use Start wandering / Stop wandering in the Drive section (speed uses the same slider as drive)."
    echo "To use keyboard teleop instead: ./cli.sh teleop   or   ./cli.sh start --teleop"
    ;;
  teleop)
    echo "Running manual_controller + keyboard_node in scout_bridge container..."
    docker compose --profile webrtc exec -it scout_bridge bash -c \
      'source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && (ros2 run connectx_controller manual_controller &) && sleep 0.5 && exec ros2 run connectx_teleop keyboard_node'
    ;;
  test)
    echo "Running all tests in ROS 2 workspace..."
    docker compose --profile webrtc run --rm scout_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && colcon test"
    echo "Tests complete."
    ;;
  logs)
    target="${1:-webrtc}"
    if [[ "$target" == "webrtc" ]]; then
      docker compose --profile webrtc logs -f scout_bridge
    elif [[ "$target" == "app" ]]; then
      docker compose --profile webrtc logs -f app
    elif [[ "$target" == "sdk" ]]; then
      docker compose --profile webrtc logs -f scout_sdk
    elif [[ "$target" == "bridge" ]]; then
      docker compose --profile webrtc logs -f scout_bridge
    elif [[ "$target" == "perception" ]]; then
      docker compose logs -f scout_perception
    elif [[ "$target" == "turn" ]]; then
      docker compose --profile webrtc logs -f scout_turn
    elif [[ "$target" == "all" ]]; then
      docker compose --profile webrtc logs -f app scout_turn scout_sdk scout_bridge scout_perception
    else
      echo "Usage: $0 logs {webrtc|app|turn|sdk|bridge|perception|all}"
      echo "  webrtc     Follow scout_bridge logs (WebRTC node runs there)"
      echo "  app        Follow app server (signaling + www) logs"
      echo "  turn       Follow scout_turn (TURN server) logs"
      echo "  sdk        Follow Earth Rovers SDK logs (front camera)"
      echo "  bridge     Follow scout_bridge logs"
      echo "  perception Follow scout_perception logs"
      echo "  all        Follow all container logs"
      exit 1
    fi
    ;;
  *)
    echo "Usage: $0 {build|start|stop|rebuild|teleop|test|logs|clean} [options]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker images and ROS 2 workspace (run once after clone or when deps change)"
    echo "  start       Start App (signaling + www), TURN, Earth Rovers SDK, scout_bridge, scout_perception"
    echo "               By default only containers start; drive from http://localhost:8000/ (no conflict with web UI)"
    echo "               Options: --teleop  Also run CLI keyboard teleop (don't use with web UI at same time)"
    echo "                        --xterm   Run teleop in a separate xterm window (implies --teleop)"
    echo "  stop        Stop app, scout_turn, scout_sdk, scout_bridge, scout_perception, and any process on port 8000/8001"
    echo "  rebuild     Stop services, rebuild Docker images and ROS 2 workspace, then start services"
    echo "  teleop      Run manual_controller + keyboard_node in scout_bridge (arrow key control)"
    echo "  test        Run all ROS 2 workspace tests (colcon test in scout_bridge container)"
    echo "  logs        Follow container logs. Run in another terminal while start is running."
    echo "               $0 logs [webrtc|app|turn|sdk|bridge|perception|all]  (default: webrtc)"
    echo "  clean       Remove orphaned containers (ros2-ws, ros2-kilted, etc.)"
    exit 1
    ;;
esac
