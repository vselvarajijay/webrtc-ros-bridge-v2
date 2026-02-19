#!/usr/bin/env bash
# Run da3_node and the depth relay together so the UI receives depth images.
# Use from the scout_perception container or on the host with ROS2 workspace sourced.
#
# Prerequisites: app running (port 8000). Set APP_URL if app is not at http://127.0.0.1:8000.
#
# Example (inside perception container):
#   cd /root/workspace && source /opt/ros/kilted/setup.bash && source ros2_ws/install/setup.bash
#   ./scripts/run_perception_with_relay.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Source ROS first so relay and node have rclpy and native libs
source /opt/ros/kilted/setup.bash
[ -f ros2_ws/install/setup.bash ] && source ros2_ws/install/setup.bash
# Prepend base ROS lib so shared libs (e.g. librcl_action.so) are found when workspace setup overwrites LD_LIBRARY_PATH
export LD_LIBRARY_PATH="/opt/ros/kilted/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Start depth relay in background (subscribes to /da3/depth_colored, POSTs to app)
python3 scripts/depth_relay_to_app.py &
RELAY_PID=$!
trap 'kill $RELAY_PID 2>/dev/null' EXIT

# Run da3_node in foreground
if command -v da3_node &>/dev/null; then
  exec da3_node
fi
# Fallback: run from source when package executable not installed (e.g. colcon build skipped or failed for this pkg)
ROS_PYTHON="$(python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)' 2>/dev/null | tr ' ' '.')"
export PYTHONPATH="${REPO_ROOT}/ros2_ws/src/bunny_perception_cpp:/opt/ros/kilted/lib/python${ROS_PYTHON:-3.12}/site-packages${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m bunny_perception_cpp.nodes.da3_node
