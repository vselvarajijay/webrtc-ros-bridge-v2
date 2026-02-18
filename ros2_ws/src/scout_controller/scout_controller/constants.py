"""Topic names and controller defaults for scout_controller (no bridge dependency)."""

# ROS topic names (must match bridge for /cmd_vel and /robot/telemetry)
CMD_VEL_TOPIC = "/cmd_vel"
ROBOT_TELEMETRY_TOPIC = "/robot/telemetry"
AUTONOMY_COMMAND_TOPIC = "/autonomy/command"

# Velocity limits (m/s, rad/s) - bridge will scale to robot range
DEFAULT_MAX_LINEAR_SPEED = 0.5
DEFAULT_MAX_ANGULAR_SPEED = 0.8

# Control loop
DEFAULT_CONTROL_HZ = 30

# Tolerances
DEFAULT_DISTANCE_TOLERANCE_M = 0.02
DEFAULT_ANGLE_TOLERANCE_DEG = 2.0

# Step timeout (s) - abort single goal if not reached
DEFAULT_STEP_TIMEOUT_S = 15.0

# P gains (first version; PID can be added later)
DEFAULT_LINEAR_P_GAIN = 0.8
DEFAULT_ANGULAR_P_GAIN = 0.02  # rad/s per degree error

# Manual teleop: topic for keyboard_node target velocities
TELEOP_VELOCITY_TARGET_TOPIC = "/teleop/velocity_target"

# Telemetry-aware teleop safety (manual_controller)
TELEOP_BATTERY_WARNING_THRESHOLD = 20.0  # percent
TELEOP_BATTERY_SPEED_REDUCTION = 0.5  # multiplier (50% speed when battery low)
TELEOP_GPS_WARNING_THRESHOLD = 10.0  # GPS signal strength threshold
TELEOP_GPS_SPEED_REDUCTION = 0.7  # multiplier (70% speed when GPS weak)
TELEOP_STUCK_VELOCITY_THRESHOLD = 0.3  # min velocity to check for stuck condition
TELEOP_STUCK_RPM_THRESHOLD = 1.0  # max RPM to consider stuck (when velocity > threshold)
