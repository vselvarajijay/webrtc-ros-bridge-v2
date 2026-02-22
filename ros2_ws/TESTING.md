# ROS2 workspace testing

This document describes how tests are organized and how to run them.

## Layout

- **Unit tests** (`@pytest.mark.unit`): Pure logic tests with no ROS context. Fast and suitable for CI.
- **Integration tests** (`@pytest.mark.integration`): Require `rclpy` or `ros2` CLI (e.g. launch file checks).
- **Linter tests**: `test_flake8`, `test_pep257`, `test_mypy`, `test_copyright`, `test_xmllint` in each Python package.

Package test directories:

| Package               | Unit tests                          | Integration tests              |
|-----------------------|-------------------------------------|--------------------------------|
| `connectx_planner`    | `test_wander.py`, `test_world_model.py` | —                              |
| `connectx_controller` | `test_command_parser.py`            | —                              |
| `connectx_robot_bridge` | `test_bridge_mapping.py`         | `test_config_manager.py` (rclpy) |
| `connectx_boot`      | —                                   | `test_launch_integration.py`   |
| `connectx_teleop`    | —                                   | —                              |

Shared fixtures (e.g. `rclpy_node`) live in each package’s `test/conftest.py`.

## Running tests

### Run CI locally (Docker)

To replicate the GitHub Actions ROS2 CI on your machine (same image and steps as [.github/workflows/ros2_ci.yml](../.github/workflows/ros2_ci.yml)):

```bash
# From repo root
./scripts/run_ros2_ci_local.sh
```

The script removes `ros2_ws/build`, `ros2_ws/install`, and `ros2_ws/log` (on the host and again inside the container) so the container always does a clean build. That avoids path mismatches when those directories were created with a different path (e.g. `/root/workspace/ros2_ws` from another Docker run).

If you run the Docker command yourself, clean inside the container first, e.g. start the `bash -c '...'` with `rm -rf ros2_ws/build ros2_ws/install ros2_ws/log`.

On Apple Silicon (arm64), the image runs under emulation (linux/amd64); the first run may be slower.

### From the repo root with a sourced workspace

```bash
source /opt/ros/kilted/setup.bash
cd ros2_ws
source install/setup.bash
colcon build --symlink-install
colcon test --event-handlers console_direct+
colcon test-result --verbose --all
```

Run only unit tests (faster, no rclpy):

```bash
cd ros2_ws
source install/setup.bash
# From workspace root, run pytest per package with marker
pytest src/connectx_planner/test -m unit -v
pytest src/connectx_controller/test -m unit -v
pytest src/connectx_robot_bridge/test -m unit -v
```

Or build and use the installed test runner:

```bash
colcon test --packages-select connectx_planner connectx_controller connectx_robot_bridge --event-handlers console_direct+
```

## Adding tests

1. **Unit tests**: Put pure logic tests in `test/test_<module>.py`, add `pytestmark = pytest.mark.unit` at module level, and use a single `conftest.py` in `test/` for any shared fixtures or marker registration.
2. **Integration tests**: Use `@pytest.mark.integration` and the `rclpy_node` fixture from `conftest.py` when you need a ROS node.
3. Keep tests independent: no shared mutable state, minimal env assumptions.
