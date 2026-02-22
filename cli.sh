#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use BuildKit for cache mounts (apt, pip, cv_bridge) in connectx_perception Dockerfile
export DOCKER_BUILDKIT=1

cmd="${1:-}"
shift || true

# Shared env for compose (macOS X11)
export COMPOSE_DISPLAY="${DISPLAY:-host.docker.internal:0}"

# App server (signaling) PID file for start/stop
APP_PID_FILE="${SCRIPT_DIR}/.cli-app-server.pid"
# Storybook dev server PID file for start/stop
STORYBOOK_PID_FILE="${SCRIPT_DIR}/.cli-storybook.pid"

# Start Storybook dev server in background (port 6006). No-op if already running or no pnpm.
start_storybook() {
  if command -v pnpm &>/dev/null && [[ -f app/www/package.json ]] && grep -q '"storybook"' app/www/package.json 2>/dev/null; then
    if lsof -i :6006 -t &>/dev/null; then
      echo "Storybook already running on port 6006."
    else
      (cd app/www && nohup pnpm run storybook -- --no-open > "${SCRIPT_DIR}/.storybook.log" 2>&1 &)
      echo $! > "$STORYBOOK_PID_FILE"
      echo "Started Storybook (port 6006). Log: .storybook.log"
    fi
  fi
}

# Stop Storybook dev server if we started it (PID file) or anything on 6006.
stop_storybook() {
  if [[ -f "$STORYBOOK_PID_FILE" ]]; then
    pid=$(cat "$STORYBOOK_PID_FILE" 2>/dev/null)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped Storybook (PID $pid)."
    fi
    rm -f "$STORYBOOK_PID_FILE"
  fi
  pids=$(lsof -i :6006 -t 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    for pid in $pids; do
      kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
    done
  fi
}

case "$cmd" in
  build)
    echo "Removing any existing containers that might conflict..."
    docker rm -f connectx_app connectx_sdk connectx_bridge connectx_perception connectx_webrtc connectx_shell connectx_turn connectx_mcp connectx_langgraph 2>/dev/null || true
    docker compose --profile webrtc down --remove-orphans 2>/dev/null || true
    echo ""
    if [[ -f app/www/package.json ]]; then
      echo "Cleaning React build output for a full rebuild..."
      rm -rf app/www/dist
      rm -rf app/www/node_modules/.vite
      if command -v pnpm &>/dev/null; then
        echo "Building React app (app/www) so the app image serves the latest UI..."
        (cd app/www && pnpm install && pnpm build) || { echo "Warning: pnpm build failed; :8000 may serve an old or broken UI."; }
      elif command -v npm &>/dev/null; then
        echo "Building React app (app/www) with npm..."
        (cd app/www && npm ci && npm run build) || { echo "Warning: npm run build failed; :8000 may serve an old or broken UI."; }
      else
        echo "Skipping React app build (pnpm/npm not found). Run: cd app/www && pnpm build  then rebuild for latest UI."
      fi
    fi
    echo "Building Docker images (app, bridge, SDK, ...)..."
    # Try --remove-orphans, fall back if not supported
    docker compose --profile webrtc build --remove-orphans 2>/dev/null || docker compose --profile webrtc build
    echo "Building ROS 2 workspace in container..."
    docker compose --profile webrtc run --rm connectx_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && colcon build"
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

    echo "Starting all webrtc profile services (connectx_app, connectx_turn, connectx_sdk, connectx_bridge, connectx_perception, connectx_mcp, connectx_langgraph)..."
    if [[ "$(uname)" == Darwin ]]; then
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d --remove-orphans 2>/dev/null || \
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d
    else
      docker compose --profile webrtc up -d --remove-orphans 2>/dev/null || \
      docker compose --profile webrtc up -d
    fi
    # Give connectx_sdk time to bind to 8001 before connectx_bridge hits /v2/front (depends_on only waits for start, not ready)
    echo "Waiting for services to be ready..."
    sleep 5
    if ! docker compose --profile webrtc ps connectx_sdk 2>/dev/null | grep -q Up; then
      echo ""
      echo "Warning: connectx_sdk is not running. Front camera will show no video until it is."
      echo "  Check: docker compose --profile webrtc ps connectx_sdk"
      echo "  Logs:  ./cli.sh logs sdk"
      echo "  Restart: docker compose --profile webrtc up -d connectx_sdk"
      echo ""
    fi
    if ! docker compose --profile webrtc exec -T connectx_bridge bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash 2>/dev/null && ros2 node list 2>/dev/null" 2>/dev/null | grep -q optical_flow_node; then
      echo ""
      echo "Warning: optical_flow_nav node is not running. Wander and world model need it."
      echo "  If you added or changed ros2_ws: run ./cli.sh build then ./cli.sh start again."
      echo "  To see why it failed: ./cli.sh logs webrtc   (look for [optical_flow_nav] lines)"
      echo ""
    fi
    start_storybook
    echo ""
    echo "App (signaling + www): http://localhost:8000/"
    echo "Earth Rovers SDK (front camera, /v2/front): http://localhost:8001/"
    echo "ConnectX MCP server: http://localhost:8002/mcp"
    echo "LangGraph Studio API: http://localhost:8123"
    echo "  → Open LangGraph Studio (click to chat with the robot agent):"
    echo "  https://smith.langchain.com/studio/?baseUrl=http://localhost:8123"
    echo "Storybook (React component dev): http://localhost:6006/"
    echo "  → If Storybook did not start, run: cd app/www && pnpm run storybook"
    echo ""
    echo "Foxglove Studio (ROS 2 visualization):"
    echo "  1. Open Foxglove Studio: https://app.foxglove.dev/  (or install the desktop app)"
    echo "  2. Add connection → Foxglove WebSocket"
    echo "  3. URL: ws://localhost:8765"
    echo "  4. Connect to view /cmd_vel, /camera/front/compressed, /robot/telemetry, and other ROS 2 topics."
    echo ""
    echo "Perception (optical flow, floor mask): connectx_perception runs automatically. Run once: python3 scripts/download_models.py"
    echo ""
    if [[ "$RUN_TELEOP" == true ]]; then
      echo "Opening teleop (keyboard control) — do not drive from the web UI at the same time (both use /cmd_vel)."
      RUN_CMD="docker compose --profile webrtc exec -it connectx_bridge bash -c 'source /opt/ros/kilted/setup.bash && [ -f /root/workspace/.env ] && set -a && source /root/workspace/.env && set +a; source /root/workspace/ros2_ws/install/setup.bash && (ros2 run connectx_controller manual_controller &) && sleep 0.5 && exec ros2 run connectx_teleop keyboard_node'"
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
    echo "Stopping all webrtc profile services..."
    docker compose --profile webrtc stop
    stop_storybook
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
    docker compose --profile webrtc stop 2>/dev/null || true
    stop_storybook
    if [[ -f "$APP_PID_FILE" ]]; then
      pid=$(cat "$APP_PID_FILE" 2>/dev/null)
      if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$APP_PID_FILE"
    fi
    echo ""
    if [[ -f app/www/package.json ]]; then
      echo "=== Rebuild: Cleaning React build for full Vite rebuild ==="
      rm -rf app/www/dist
      rm -rf app/www/node_modules/.vite
      if command -v pnpm &>/dev/null; then
        echo "=== Rebuild: Building React app (app/www) ==="
        (cd app/www && pnpm install && pnpm build) || { echo "Warning: pnpm build failed; :8000 may serve an old or broken UI."; }
      elif command -v npm &>/dev/null; then
        echo "=== Rebuild: Building React app (app/www) with npm ==="
        (cd app/www && npm ci && npm run build) || { echo "Warning: npm run build failed; :8000 may serve an old or broken UI."; }
      else
        echo "Skipping React app build (pnpm/npm not found). Run: cd app/www && pnpm build  then rebuild for latest UI."
      fi
    fi
    echo ""
    echo "=== Rebuild: Building Docker images and ROS 2 workspace ==="
    docker rm -f connectx_app connectx_sdk connectx_bridge connectx_perception connectx_webrtc connectx_shell connectx_turn connectx_mcp connectx_langgraph 2>/dev/null || true
    docker compose --profile webrtc down --remove-orphans 2>/dev/null || true
    export CACHEBUST="${CACHEBUST:-$(date +%s)}"
    docker compose --profile webrtc build --remove-orphans 2>/dev/null || docker compose --profile webrtc build
    docker compose --profile webrtc run --rm connectx_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && colcon build"
    echo ""
    echo "=== Rebuild: Starting all webrtc profile services (force-recreate) ==="
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
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d --force-recreate --remove-orphans 2>/dev/null || \
      DISPLAY=host.docker.internal:0 docker compose --profile webrtc up -d --force-recreate
    else
      docker compose --profile webrtc up -d --force-recreate --remove-orphans 2>/dev/null || \
      docker compose --profile webrtc up -d --force-recreate
    fi
    echo "Waiting for services to be ready..."
    sleep 5
    if ! docker compose --profile webrtc ps connectx_sdk 2>/dev/null | grep -q Up; then
      echo ""
      echo "Warning: connectx_sdk is not running. Front camera will show no video until it is."
      echo "  Check: docker compose --profile webrtc ps connectx_sdk"
      echo "  Logs:  ./cli.sh logs sdk"
      echo "  Restart: docker compose --profile webrtc up -d connectx_sdk"
      echo ""
    fi
    start_storybook
    echo ""
    echo "Rebuild complete! Services are running."
    echo ""
    echo "App (signaling + www): http://localhost:8000/"
    echo "Earth Rovers SDK (front camera, /v2/front): http://localhost:8001/"
    echo "ConnectX MCP server: http://localhost:8002/mcp"
    echo "LangGraph Studio API: http://localhost:8123"
    echo "  → Open LangGraph Studio (click to chat with the robot agent):"
    echo "  https://smith.langchain.com/studio/?baseUrl=http://localhost:8123"
    echo "Storybook (React component dev): http://localhost:6006/"
    echo "  → If Storybook did not start, run: cd app/www && pnpm run storybook"
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
    echo "Running manual_controller + keyboard_node in connectx_bridge container..."
    docker compose --profile webrtc exec -it connectx_bridge bash -c \
      'source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && (ros2 run connectx_controller manual_controller &) && sleep 0.5 && exec ros2 run connectx_teleop keyboard_node'
    ;;
  test)
    echo "Running all tests in ROS 2 workspace..."
    docker compose --profile webrtc run --rm connectx_bridge bash -c \
      "source /opt/ros/kilted/setup.bash && cd /root/workspace/ros2_ws && colcon test"
    echo "Tests complete."
    ;;
  logs)
    target="${1:-webrtc}"
    if [[ "$target" == "webrtc" ]]; then
      docker compose --profile webrtc logs -f connectx_bridge
    elif [[ "$target" == "app" ]]; then
      docker compose --profile webrtc logs -f connectx_app
    elif [[ "$target" == "sdk" ]]; then
      docker compose --profile webrtc logs -f connectx_sdk
    elif [[ "$target" == "bridge" ]]; then
      docker compose --profile webrtc logs -f connectx_bridge
    elif [[ "$target" == "perception" ]]; then
      docker compose logs -f connectx_perception
    elif [[ "$target" == "turn" ]]; then
      docker compose --profile webrtc logs -f connectx_turn
    elif [[ "$target" == "mcp" ]]; then
      docker compose --profile webrtc logs -f connectx_mcp
    elif [[ "$target" == "langgraph" ]]; then
      docker compose --profile webrtc logs -f connectx_langgraph
    elif [[ "$target" == "all" ]]; then
      docker compose --profile webrtc logs -f connectx_app connectx_turn connectx_sdk connectx_bridge connectx_perception connectx_mcp connectx_langgraph
    else
      echo "Usage: $0 logs {webrtc|app|turn|sdk|bridge|perception|mcp|langgraph|all}"
      echo "  webrtc     Follow connectx_bridge logs (WebRTC node runs there)"
      echo "  app        Follow connectx_app (signaling + www) logs"
      echo "  turn       Follow connectx_turn (TURN server) logs"
      echo "  sdk        Follow Earth Rovers SDK (connectx_sdk) logs (front camera)"
      echo "  bridge     Follow connectx_bridge logs"
      echo "  perception Follow connectx_perception logs"
      echo "  mcp        Follow connectx_mcp (MCP server) logs"
      echo "  langgraph  Follow connectx_langgraph (LangGraph Studio) logs"
      echo "  all        Follow all container logs"
      exit 1
    fi
    ;;
  *)
    echo "Usage: $0 {build|start|stop|rebuild|teleop|test|logs|clean} [options]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker images and ROS 2 workspace (run once after clone or when deps change)"
    echo "  start       Start connectx_app (signaling + www), connectx_turn, Earth Rovers SDK (connectx_sdk), connectx_bridge, connectx_perception,"
    echo "               connectx_mcp (MCP server), connectx_langgraph (LangGraph Studio chat agent)"
    echo "               By default only containers start; drive from http://localhost:8000/ (no conflict with web UI)"
    echo "               Options: --teleop  Also run CLI keyboard teleop (don't use with web UI at same time)"
    echo "                        --xterm   Run teleop in a separate xterm window (implies --teleop)"
    echo "  stop        Stop all services including connectx_mcp and connectx_langgraph"
    echo "  rebuild     Stop services, rebuild Docker images and ROS 2 workspace, then start services"
    echo "  teleop      Run manual_controller + keyboard_node in connectx_bridge (arrow key control)"
    echo "  test        Run all ROS 2 workspace tests (colcon test in connectx_bridge container)"
    echo "  logs        Follow container logs. Run in another terminal while start is running."
    echo "               $0 logs [webrtc|app|turn|sdk|bridge|perception|mcp|langgraph|all]  (default: webrtc)"
    echo "  clean       Remove orphaned containers (ros2-ws, ros2-kilted, etc.)"
    exit 1
    ;;
esac
