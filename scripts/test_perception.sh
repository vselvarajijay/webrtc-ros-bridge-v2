#!/usr/bin/env bash
# Test the perception pipeline: camera -> optical_flow_nav -> relays -> app -> UI.
# Run from repo root. Requires: ./cli.sh start (app + bridge running).
set -e
cd "$(dirname "$0")/.."
echo "=== 1. Container status ==="
docker compose --profile webrtc ps connectx_app connectx_bridge 2>/dev/null || true
if ! docker compose --profile webrtc ps connectx_bridge 2>/dev/null | grep -q Up; then
  echo "connectx_bridge is not running. Run: ./cli.sh start"
  echo "If it exited, check: docker compose --profile webrtc logs connectx_bridge"
  exit 1
fi
echo ""
echo "=== 2. App reachable ==="
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
echo "HTTP $code (expect 200)"
echo ""
echo "=== 3. ROS topics (run with camera/bridge so /camera/front/compressed has data) ==="
echo "Camera rate:"
docker compose --profile webrtc exec -T connectx_bridge bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /camera/front/compressed 2>/dev/null || echo 'no messages in 3s'"
echo "Navigation state rate:"
docker compose --profile webrtc exec -T connectx_bridge bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /navigation_state 2>/dev/null || echo 'no messages in 3s'"
echo "Optical flow image rate:"
docker compose --profile webrtc exec -T connectx_bridge bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /optical_flow/image/compressed 2>/dev/null || echo 'no messages in 3s'"
echo ""
echo "=== 4. Perception API ==="
curl -s -o /dev/null -w "GET /api/optical_flow_image: %{http_code}\n" http://localhost:8000/api/optical_flow_image
echo ""
echo "If 503: relay may not be receiving frames or cannot reach app."
echo "  - Ensure /camera/front/compressed is publishing (bridge + robot/SDK)."
echo "  - Check: docker compose --profile webrtc logs connectx_bridge"
