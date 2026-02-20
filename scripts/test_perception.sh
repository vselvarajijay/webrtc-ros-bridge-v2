#!/usr/bin/env bash
# Test the perception pipeline: camera -> optical_flow_node / floor_mask_node -> relays -> app -> UI.
# Run from repo root. Requires: ./cli.sh start (app + bridge + perception running).
set -e
cd "$(dirname "$0")/.."
echo "=== 1. Container status ==="
docker compose --profile webrtc ps app scout_bridge scout_perception 2>/dev/null || true
if ! docker compose --profile webrtc ps scout_perception 2>/dev/null | grep -q Up; then
  echo "scout_perception is not running. Run: ./cli.sh start"
  echo "If it exited, check: docker compose --profile webrtc logs scout_perception"
  echo "Ensure models exist: python3 scripts/download_models.py"
  exit 1
fi
echo ""
echo "=== 2. App reachable from perception (relays need this) ==="
code=$(docker compose --profile webrtc exec -T scout_perception bash -c 'curl -s -o /dev/null -w "%{http_code}" ${APP_URL:-http://host.docker.internal:8000}/health' 2>/dev/null || echo "000")
echo "HTTP $code (expect 200)"
echo ""
echo "=== 3. ROS topics (run with camera/bridge so /camera/front/compressed has data) ==="
echo "Camera rate:"
docker compose --profile webrtc exec -T scout_bridge bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /camera/front/compressed 2>/dev/null || echo 'no messages in 3s'"
echo "Optical flow rate:"
docker compose --profile webrtc exec -T scout_perception bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /optical_flow/image/compressed 2>/dev/null || echo 'no messages in 3s'"
echo "Floor mask rate:"
docker compose --profile webrtc exec -T scout_perception bash -c "source /opt/ros/kilted/setup.bash && source /root/workspace/ros2_ws/install/setup.bash && timeout 3 ros2 topic hz /perception/floor_mask/image/compressed 2>/dev/null || echo 'no messages in 3s'"
echo ""
echo "=== 4. Perception APIs ==="
curl -s -o /dev/null -w "GET /api/optical_flow_image: %{http_code}\n" http://localhost:8000/api/optical_flow_image
curl -s -o /dev/null -w "GET /api/floor_mask_image: %{http_code}\n" http://localhost:8000/api/floor_mask_image
echo ""
echo "If 503: relays may not be receiving frames or cannot reach app."
echo "  - Set APP_URL in .env or docker-compose for scout_perception if not on Mac (e.g. APP_URL=http://127.0.0.1:8000)."
echo "  - Check: docker compose --profile webrtc logs scout_perception"
echo "  - Ensure /camera/front/compressed is publishing (bridge + robot/SDK)."
