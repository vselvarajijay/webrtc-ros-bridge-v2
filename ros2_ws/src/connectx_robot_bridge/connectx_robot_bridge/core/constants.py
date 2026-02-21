"""Constants used throughout the connectx_robot_bridge package."""

import os

# API URLs
FRODOBOTS_API_URL = os.getenv(
    "FRODOBOTS_API_URL", "https://frodobots-web-api.onrender.com/api/v1"
)
SDK_LOCAL_URL = os.getenv("SDK_LOCAL_URL", "http://127.0.0.1:8000")
SDK_LOCAL_ENDPOINT = f"{SDK_LOCAL_URL}/sdk"
SDK_FRONT_ENDPOINT = f"{SDK_LOCAL_URL}/v2/front"
SDK_FRONT_FULL_ENDPOINT = f"{SDK_LOCAL_URL}/v2/front_full"
SDK_DATA_ENDPOINT = f"{SDK_LOCAL_URL}/data"

# Velocity limits
MIN_VELOCITY = -1.0
MAX_VELOCITY = 1.0
# Some robots/SDK expect opposite linear sign (e.g. positive = backward). Set to -1 to flip.
EARTH_ROVERS_LINEAR_SIGN = int(os.getenv("EARTH_ROVERS_LINEAR_SIGN", "1"))

# Timeouts (in seconds)
AUTH_TIMEOUT = 15
SDK_CHECK_TIMEOUT = 10
BROWSER_ERROR_LOG_INTERVAL = 10.0

# Default viewport dimensions (browser capture size; smaller = faster, less data).
# Override via FRODOBOT_VIEWPORT_WIDTH / FRODOBOT_VIEWPORT_HEIGHT in .env.
DEFAULT_VIEWPORT_WIDTH = int(os.getenv("FRODOBOT_VIEWPORT_WIDTH", "3840"))
DEFAULT_VIEWPORT_HEIGHT = int(os.getenv("FRODOBOT_VIEWPORT_HEIGHT", "2160"))
DEFAULT_VIEWPORT = {"width": DEFAULT_VIEWPORT_WIDTH, "height": DEFAULT_VIEWPORT_HEIGHT}

# Image formats (jpeg is faster to encode/decode than png; use for lower latency)
VALID_IMAGE_FORMATS = ["png", "jpeg", "webp"]
DEFAULT_IMAGE_FORMAT = "jpeg"
DEFAULT_IMAGE_QUALITY = 0.85

# WebRTC video output size (lower = faster decode/encode and less bandwidth)
VIDEO_OUTPUT_WIDTH = 320
VIDEO_OUTPUT_HEIGHT = 240

# Chrome executable fallback paths
CHROME_FALLBACK_PATHS = [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ROS topic names
CMD_VEL_TOPIC = "/cmd_vel"
LAMP_TOPIC = "/robot/lamp"
CAMERA_FRONT_COMPRESSED_TOPIC = "/camera/front/compressed"
CAMERA_FRONT_FULL_COMPRESSED_TOPIC = "/camera/front/full/compressed"
CAMERA_FRAME_ID = "camera_front"
ROBOT_TELEMETRY_TOPIC = "/robot/telemetry"

# ROS parameter defaults
DEFAULT_ROBOT_TYPE = "earth_rovers_sdk"
DEFAULT_MAX_LINEAR_SPEED = 1.0
DEFAULT_MAX_ANGULAR_SPEED = 1.0
# Limited by SDK /v2/front (HTTP + Playwright capture). 5 Hz is reliable for WebRTC; increase if SDK keeps up.
DEFAULT_CAMERA_PUBLISH_RATE = 5.0
# Full-resolution front camera (viewport size); keep low to avoid overloading SDK.
DEFAULT_CAMERA_FULL_PUBLISH_RATE = 1.0
DEFAULT_TELEMETRY_PUBLISH_RATE = 10.0
DEFAULT_MAP_ZOOM_LEVEL = "18"

# Required auth keys
REQUIRED_AUTH_KEYS = ("CHANNEL_NAME", "RTM_TOKEN", "USERID", "APP_ID")
