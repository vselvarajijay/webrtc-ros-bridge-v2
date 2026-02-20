#!/usr/bin/env bash
# Run optical_flow_node, floor_mask_node, and their relays so the UI receives optical flow and floor mask images.
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

# Source ROS first so relays and nodes have rclpy and native libs
source /opt/ros/kilted/setup.bash
[ -f ros2_ws/install/setup.bash ] && source ros2_ws/install/setup.bash
# Prepend base ROS lib so shared libs (e.g. librcl_action.so) are found when workspace setup overwrites LD_LIBRARY_PATH
export LD_LIBRARY_PATH="/opt/ros/kilted/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Start optical flow relay in background (subscribes to /optical_flow/image/compressed, POSTs to app)
python3 scripts/optical_flow_relay_to_app.py &
OF_RELAY_PID=$!
# Start floor mask relay in background (subscribes to /perception/floor_mask/image/compressed, POSTs to app)
python3 scripts/floor_mask_relay_to_app.py &
FM_RELAY_PID=$!
trap 'kill $OF_RELAY_PID $FM_RELAY_PID 2>/dev/null' EXIT

# Run perception nodes in background so both stay up
ros2 run bunny_perception_cpp optical_flow_node &
OF_PID=$!
ros2 run bunny_perception_cpp floor_mask_node &
FM_PID=$!
trap 'kill $OF_RELAY_PID $FM_RELAY_PID $OF_PID $FM_PID 2>/dev/null' EXIT

# Wait for any process to exit (then trap will kill the rest)
wait
