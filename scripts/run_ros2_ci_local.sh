#!/usr/bin/env bash
# Run the same build and test steps as .github/workflows/ros2_ci.yml inside Docker.
# Requires Docker. Overlay volumes for build/install/log so the container never sees
# host or stale paths (e.g. /root/workspace/ros2_ws), avoiding CMake/colcon path mismatches.

set -e
cd "$(dirname "$0")/.."

# Overlay empty volumes so container never sees host's ros2_ws/build|install|log
docker run --rm \
  -v "$(pwd):/connectX" \
  -v /connectX/ros2_ws/build \
  -v /connectX/ros2_ws/install \
  -v /connectX/ros2_ws/log \
  -w /connectX osrf/ros:humble-desktop bash -c '
  apt-get update -qq && apt-get install -y -qq python3-colcon-common-extensions python3-pytest ros-humble-ament-mypy
  source /opt/ros/humble/setup.bash
  cd ros2_ws
  colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
  source install/setup.bash
  export PYTEST_ADDOPTS='\''-m "not linter"'\''
  colcon test --event-handlers console_direct+ --python-testing pytest
  colcon test-result --verbose --all
'
