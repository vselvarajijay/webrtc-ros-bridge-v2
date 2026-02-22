"""Constants for connectx_teleop (topic names, video/encoding, signaling). No bridge dependency."""

# ROS topic names (must match bridge and connectx_controller)
CMD_VEL_TOPIC = "/cmd_vel"
LAMP_TOPIC = "/robot/lamp"
ROBOT_TELEMETRY_TOPIC = "/robot/telemetry"
AUTONOMY_COMMAND_TOPIC = "/autonomy/command"
CAMERA_FRONT_COMPRESSED_TOPIC = "/camera/front/compressed"
CAMERA_FRAME_ID = "camera_front"
NAVIGATION_STATE_TOPIC = "/navigation_state"
TELEOP_VELOCITY_TARGET_TOPIC = "/teleop/velocity_target"

# WebRTC video output size (lower = faster decode/encode and less bandwidth)
VIDEO_OUTPUT_WIDTH = 320
VIDEO_OUTPUT_HEIGHT = 240

# Image format for encoding
DEFAULT_IMAGE_FORMAT = "jpeg"
