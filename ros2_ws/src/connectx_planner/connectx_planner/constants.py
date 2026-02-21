"""Topic names and defaults for connectx_planner (wander and planning)."""

# ROS topic names (must match rest of stack for /cmd_vel and /autonomy/command)
CMD_VEL_TOPIC = "/cmd_vel"
CMD_VEL_TARGET_TOPIC = "/cmd_vel_target"
AUTONOMY_COMMAND_TOPIC = "/autonomy/command"
OPTICAL_FLOW_TOPIC = "/optical_flow"
ROBOT_TELEMETRY_TOPIC = "/robot/telemetry"
NAVIGATION_STATE_TOPIC = "/navigation_state"

# Velocity limits (m/s, rad/s) - bridge will scale to robot range
DEFAULT_MAX_LINEAR_SPEED = 0.5
DEFAULT_MAX_ANGULAR_SPEED = 0.8
