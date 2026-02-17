"""Constants used throughout the scout_robot_bridge package."""

import os

# API URLs
FRODOBOTS_API_URL = os.getenv(
    "FRODOBOTS_API_URL", "https://frodobots-web-api.onrender.com/api/v1"
)
SDK_LOCAL_URL = "http://127.0.0.1:8000"
SDK_LOCAL_ENDPOINT = f"{SDK_LOCAL_URL}/sdk"
SDK_DATA_ENDPOINT = f"{SDK_LOCAL_URL}/data"

# Velocity limits
MIN_VELOCITY = -1.0
MAX_VELOCITY = 1.0

# Timeouts (in seconds)
AUTH_TIMEOUT = 15
SDK_CHECK_TIMEOUT = 1
BROWSER_ERROR_LOG_INTERVAL = 10.0

# Default viewport dimensions
DEFAULT_VIEWPORT_WIDTH = 3840
DEFAULT_VIEWPORT_HEIGHT = 2160
DEFAULT_VIEWPORT = {"width": DEFAULT_VIEWPORT_WIDTH, "height": DEFAULT_VIEWPORT_HEIGHT}

# Image formats
VALID_IMAGE_FORMATS = ["png", "jpeg", "webp"]
DEFAULT_IMAGE_FORMAT = "png"
DEFAULT_IMAGE_QUALITY = 1.0

# Chrome executable fallback paths
CHROME_FALLBACK_PATHS = [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ROS topic names
CMD_VEL_TOPIC = "/cmd_vel"
CAMERA_FRONT_COMPRESSED_TOPIC = "/camera/front/compressed"
CAMERA_FRAME_ID = "camera_front"

# ROS parameter defaults
DEFAULT_ROBOT_TYPE = "earth_rovers_sdk"
DEFAULT_MAX_LINEAR_SPEED = 1.0
DEFAULT_MAX_ANGULAR_SPEED = 1.0
DEFAULT_CAMERA_PUBLISH_RATE = 5.0
DEFAULT_MAP_ZOOM_LEVEL = "18"

# Required auth keys
REQUIRED_AUTH_KEYS = ("CHANNEL_NAME", "RTM_TOKEN", "USERID", "APP_ID")

# Telemetry-aware teleop parameters
TELEOP_BATTERY_WARNING_THRESHOLD = 20.0  # percent
TELEOP_BATTERY_SPEED_REDUCTION = 0.5  # multiplier (50% speed when battery low)
TELEOP_GPS_WARNING_THRESHOLD = 10.0  # GPS signal strength threshold
TELEOP_GPS_SPEED_REDUCTION = 0.7  # multiplier (70% speed when GPS weak)
TELEOP_STUCK_VELOCITY_THRESHOLD = 0.3  # min velocity to check for stuck condition
TELEOP_STUCK_RPM_THRESHOLD = 1.0  # max RPM to consider stuck (when velocity > threshold)
