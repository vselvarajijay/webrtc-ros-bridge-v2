import logging
import time
from typing import Iterator, Optional

import requests

from scout_robot_bridge.core.constants import (
    MAX_VELOCITY,
    MIN_VELOCITY,
    SDK_CHECK_TIMEOUT,
    SDK_DATA_ENDPOINT,
    SDK_FRONT_ENDPOINT,
)
from scout_robot_bridge.core.exceptions import AuthenticationError
from scout_robot_bridge.core.models.telemetry import TelemetryFrame
from scout_robot_bridge.core.robot_base import RobotBase
from scout_robot_bridge.robot_sdk.earth_rovers_sdk import RtmClient
from scout_robot_bridge.utils import base64_to_bytes, fetch_auth_sync


class EarthRoversRobot(RobotBase):
    """Robot implementation using Earth Rovers (FrodoBot) SDK."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize Earth Rovers robot.
        
        Args:
            logger: Optional logger instance. If None, uses default logger.
        """
        self._logger = logger or logging.getLogger(__name__)
        self._rtm_client: Optional[RtmClient] = None
        self._camera_disabled = False
        self._camera_fail_count = 0
        self._last_telemetry_warning_time = 0.0
        self._telemetry_warning_interval = 5.0  # Only log warning every 5 seconds
        self._lamp = 0  # Bitfield: 0=off, 1=front, 2=back, 3=both
        
        try:
            auth = fetch_auth_sync()
            self._rtm_client = RtmClient(auth)
        except AuthenticationError as e:
            self._logger.warning(f"Failed to authenticate: {e}. Robot will operate without RTM client.")
            self._rtm_client = None

    def set_lamp(self, lamp: int) -> None:
        """Set lamp state (0=off, 1=on). Sent with next velocity command to SDK."""
        self._lamp = 1 if lamp else 0

    def _send_velocity_command(self, linear: float, angular: float, lamp: Optional[int] = None) -> None:
        """
        Internal method to send velocity commands to the robot.
        
        Args:
            linear: Forward/backward speed (-1.0 to 1.0)
            angular: Rotation speed left/right (-1.0 to 1.0)
            lamp: Lamp value (default: use current self._lamp). SDK accepts 0=off, 1=on.
        """
        if self._rtm_client is None:
            self._logger.warning("Cannot send velocity command: RTM client not initialized")
            return
        lamp_val = self._lamp if lamp is None else (1 if lamp else 0)
        self._logger.debug(f"Sending velocity command: linear={linear:.3f}, angular={angular:.3f}, lamp={lamp_val}")
        self._rtm_client.send_message({
            "linear": linear,
            "angular": angular,
            "lamp": lamp_val
        })

    def move_forward(self) -> None:
        """Move robot forward."""
        self._send_velocity_command(linear=1.0, angular=0.0)

    def move_backward(self) -> None:
        """Move robot backward."""
        self._send_velocity_command(linear=-1.0, angular=0.0)

    def move_left(self) -> None:
        """Rotate robot left."""
        self._send_velocity_command(linear=0.0, angular=1.0)

    def move_right(self) -> None:
        """Rotate robot right."""
        self._send_velocity_command(linear=0.0, angular=-1.0)

    def stop(self) -> None:
        """Stop the robot by sending zero velocity commands."""
        self._send_velocity_command(linear=0.0, angular=0.0)

    def send_velocity(self, linear: float, angular: float) -> None:
        """
        Send continuous velocity commands to the robot.
        
        Args:
            linear: Forward/backward speed (-1.0 to 1.0)
            angular: Rotation speed left/right (-1.0 to 1.0)
            
        Clamps values to [-1.0, 1.0] range as per Frodobots SDK spec.
        """
        # Clamp values to valid range [-1.0, 1.0]
        linear_clamped = max(MIN_VELOCITY, min(MAX_VELOCITY, linear))
        angular_clamped = max(MIN_VELOCITY, min(MAX_VELOCITY, angular))
        self._send_velocity_command(linear=linear_clamped, angular=angular_clamped)

    def get_front_camera_frame(self) -> Optional[bytes]:
        """
        Get latest front camera frame as raw bytes via SDK /v2/front API.

        Returns:
            Camera frame bytes, or None if unavailable or disabled.
        """
        if self._camera_disabled:
            return None
        try:
            r = requests.get(SDK_FRONT_ENDPOINT, timeout=SDK_CHECK_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            b64 = data.get("front_frame")
            if not b64:
                return None
            self._camera_fail_count = 0  # success: allow retries after future failures
            return base64_to_bytes(b64)
        except Exception as e:
            self._camera_fail_count += 1
            # Only disable after several consecutive failures so one timeout doesn't kill video
            if self._camera_fail_count >= 5:
                self._camera_disabled = True
                self._logger.warning(
                    "Front camera disabled after %d failures: %s (%s). Run Earth Rovers SDK to enable.",
                    self._camera_fail_count,
                    SDK_FRONT_ENDPOINT,
                    e,
                )
            return None

    # Minimum delay between frame pulls when using stream; actual rate limited by get_front_camera_frame() (HTTP + SDK).
    CAMERA_STREAM_LOOP_SLEEP = 0.01

    def get_front_camera_stream(self, stop_event=None) -> Iterator[Optional[bytes]]:
        """
        Yield front camera frames continuously at max sustainable rate (reuses get_front_camera_frame).
        Frame rate is dominated by get_front_camera_frame() latency (HTTP + SDK capture); loop sleep is a cap only.
        """
        while stop_event is None or not stop_event.is_set():
            frame = self.get_front_camera_frame()
            yield frame
            time.sleep(self.CAMERA_STREAM_LOOP_SLEEP)

    def get_telemetry(self) -> Optional[TelemetryFrame]:
        """
        Get latest telemetry data from the robot.
        
        Fetches sensor data from the SDK's /data endpoint, including:
        - Battery level, signal strength, speed, lamp state
        - GPS coordinates and signal quality
        - Compass orientation
        - IMU data (accelerometer, gyroscope, magnetometer)
        - Wheel RPMs for all four wheels
        
        Returns:
            TelemetryFrame containing sensor data, or None if unavailable.
        """
        try:
            r = requests.get(SDK_DATA_ENDPOINT, timeout=SDK_CHECK_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            
            # Create TelemetryFrame from JSON response
            return TelemetryFrame(
                battery=data.get("battery", 0.0),
                signal_level=data.get("signal_level", 0),
                speed=data.get("speed", 0.0),
                lamp=data.get("lamp", 0),
                latitude=data.get("latitude", 0.0),
                longitude=data.get("longitude", 0.0),
                gps_signal=data.get("gps_signal", 0.0),
                orientation=data.get("orientation", 0),
                vibration=data.get("vibration"),
                accels=data.get("accels", []),
                gyros=data.get("gyros", []),
                mags=data.get("mags", []),
                rpms=data.get("rpms", []),
                timestamp=data.get("timestamp", 0.0),
            )
        except Exception as e:
            # Rate-limit warnings to avoid spam when SDK is unavailable
            now = time.monotonic()
            if now - self._last_telemetry_warning_time >= self._telemetry_warning_interval:
                self._logger.debug(
                    f"Telemetry unavailable (SDK not running?): {type(e).__name__}. "
                    f"Will retry silently. Start SDK at {SDK_DATA_ENDPOINT} to enable telemetry."
                )
                self._last_telemetry_warning_time = now
            return None

    def cleanup(self) -> None:
        """
        Clean up resources. Call when robot is no longer needed.
        Intentionally no-op for now; RTM connection is not explicitly closed.
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()
        return False
