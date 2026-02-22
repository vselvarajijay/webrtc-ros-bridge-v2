#!/usr/bin/env bash
# Run camera relay, optical_flow_nav, flow image encoder, and optical flow relay so the UI receives optical flow images.
# Use from the connectx_bridge container or on the host with ROS2 workspace sourced.
#
# Prerequisites: app running (port 8000). Set APP_URL if app is not at http://127.0.0.1:8000.
# Camera topic /camera/front/compressed must be publishing (e.g. from bridge + robot/SDK).
#
# Example (inside bridge container):
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

# Camera: compressed -> raw for optical_flow_nav
python3 scripts/camera_compressed_to_raw_relay.py &
CAM_RELAY_PID=$!
# optical_flow_nav node (publishes /navigation_state and /optical_flow_nav/debug_flow_image)
ros2 run optical_flow_nav optical_flow_node &
OFN_PID=$!
# Encode debug flow image to /optical_flow/image/compressed
python3 scripts/optical_flow_image_to_compressed.py &
ENC_PID=$!
# Relay optical flow image to app
python3 scripts/optical_flow_relay_to_app.py &
OF_RELAY_PID=$!
trap 'kill $CAM_RELAY_PID $OFN_PID $ENC_PID $OF_RELAY_PID 2>/dev/null' EXIT

# Wait for any process to exit (then trap will kill the rest)
wait
