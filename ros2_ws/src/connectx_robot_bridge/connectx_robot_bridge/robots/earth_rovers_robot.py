import logging
import time
from typing import Dict, Iterator, Optional, Tuple

import requests  # type: ignore[import]

from connectx_robot_bridge.core.constants import (
    EARTH_ROVERS_LINEAR_SIGN,
    MAX_VELOCITY,
    MIN_VELOCITY,
    SDK_CHECK_TIMEOUT,
    SDK_DATA_ENDPOINT,
    SDK_FRONT_ENDPOINT,
    SDK_FRONT_FULL_ENDPOINT,
)
from connectx_robot_bridge.core.exceptions import AuthenticationError
from connectx_robot_bridge.core.models.telemetry import TelemetryFrame
from connectx_robot_bridge.core.robot_base import RobotBase
from connectx_robot_bridge.robot_sdk.earth_rovers_sdk import RtmClient
from connectx_robot_bridge.utils import base64_to_bytes, fetch_auth_sync


class EarthRoversRobot(RobotBase):
    """Robot implementation using Earth Rovers (FrodoBot) SDK."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize Earth Rovers robot.

        Args:
        ----
        logger : logging.Logger, optional
            Logger instance. If None, uses default logger.

        """
        self._logger = logger or logging.getLogger(__name__)
        self._rtm_client: Optional[RtmClient] = None
        self._camera_disabled = False
        self._camera_fail_count = 0
        self._camera_disabled_at: Optional[float] = None  # when we set _camera_disabled
        self._last_telemetry_warning_time = 0.0
        self._telemetry_warning_interval = 5.0  # Only log warning every 5 seconds
        self._lamp = 0  # Bitfield: 0=off, 1=front, 2=back, 3=both
        self._first_velocity_sent = False
        self._last_rtm_fail_log = 0.0

        try:
            auth = fetch_auth_sync()
            self._rtm_client = RtmClient(auth)
        except AuthenticationError as e:
            self._logger.warning(
                "Failed to authenticate: %s. Robot will operate without RTM client.", e
            )
            self._rtm_client = None

    def set_lamp(self, lamp: int) -> None:
        """Set lamp state (0=off, 1=on). Sent with next velocity command to SDK."""
        self._lamp = 1 if lamp else 0

    def _send_velocity_command(
        self, linear: float, angular: float, lamp: Optional[int] = None
    ) -> bool:
        """
        Send velocity commands to the robot via RTM.

        Returns
        -------
        bool
            True if the message was sent via RTM (HTTP 200), False otherwise.

        """
        if self._rtm_client is None:
            self._logger.warning("Cannot send velocity command: RTM client not initialized")
            return False
        lamp_val = self._lamp if lamp is None else (1 if lamp else 0)
        self._logger.debug(
            "Sending velocity: linear=%.3f, angular=%.3f, lamp=%s",
            linear, angular, lamp_val,
        )
        ok = self._rtm_client.send_message({
            "linear": linear,
            "angular": angular,
            "lamp": lamp_val
        })
        if ok and not self._first_velocity_sent:
            self._first_velocity_sent = True
            self._logger.info(
                "First velocity command sent via RTM; robot should respond to joystick."
            )
        if not ok and (abs(linear) > 0.01 or abs(angular) > 0.01):
            now = time.monotonic()
            if now - self._last_rtm_fail_log >= 5.0:
                self._last_rtm_fail_log = now
                self._logger.warning(
                    "RTM send_message returned False; robot may not be receiving commands. "
                    "Check RTM_TOKEN, BOT_UID, and that the robot is online and in the channel."
                )
        return ok

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

    def send_velocity(self, linear: float, angular: float) -> bool:
        """
        Send continuous velocity commands to the robot.

        Returns
        -------
        bool
            True if the message was sent via RTM (HTTP 200), False otherwise.

        """
        # Clamp values to valid range [-1.0, 1.0]
        linear_clamped = max(MIN_VELOCITY, min(MAX_VELOCITY, linear))
        angular_clamped = max(MIN_VELOCITY, min(MAX_VELOCITY, angular))
        # Some robots expect opposite linear sign (backward works, forward doesn't). Flip via env.
        linear_signed = linear_clamped * EARTH_ROVERS_LINEAR_SIGN
        return self._send_velocity_command(linear=linear_signed, angular=angular_clamped)

    def get_front_camera_frame(self) -> Optional[Tuple[bytes, Dict[str, float]]]:
        """
        Get latest front camera frame as raw bytes via SDK /v2/front API, with timing metrics.

        Returns
        -------
        tuple or None
            (frame_bytes, metrics) with capture_ms and fetch_ms, or None if unavailable.

        """
        # Re-enable after cooldown so temporary SDK unavailability doesn't kill video
        if self._camera_disabled:
            if (
                self._camera_disabled_at is not None
                and (time.monotonic() - self._camera_disabled_at) >= 30.0
            ):
                self._camera_disabled = False
                self._camera_fail_count = 0
                self._camera_disabled_at = None
                self._logger.info(
                    "Front camera re-enabled after 30s cooldown; retrying %s",
                    SDK_FRONT_ENDPOINT,
                )
            else:
                return None
        try:
            t0 = time.perf_counter()
            r = requests.get(SDK_FRONT_ENDPOINT, timeout=SDK_CHECK_TIMEOUT)
            fetch_ms = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            data = r.json()
            b64 = data.get("front_frame")
            if not b64:
                return None
            decoded = base64_to_bytes(b64)
            if decoded is None:
                return None
            capture_ms = float(data.get("capture_ms", 0))
            self._camera_fail_count = 0  # success: allow retries after future failures
            metrics = {"capture_ms": capture_ms, "fetch_ms": fetch_ms}
            return (decoded, metrics)
        except Exception as e:
            self._camera_fail_count += 1
            # Only disable after several consecutive failures so one timeout doesn't kill video
            if self._camera_fail_count >= 5:
                self._camera_disabled = True
                self._camera_disabled_at = time.monotonic()
                self._logger.warning(
                    "Front camera disabled after %d failures: %s (%s). "
                    "Run Earth Rovers SDK to enable.",
                    self._camera_fail_count,
                    SDK_FRONT_ENDPOINT,
                    e,
                )
            return None

    def get_front_camera_frame_full(self) -> Optional[Tuple[bytes, Dict[str, float]]]:
        """
        Get one front camera frame at full (viewport) resolution via SDK /v2/front_full.

        Use for calibration or when full-resolution image is needed; keep rate low.
        Returns (frame_bytes, metrics) or None.
        """
        if self._camera_disabled:
            return None
        try:
            t0 = time.perf_counter()
            r = requests.get(SDK_FRONT_FULL_ENDPOINT, timeout=SDK_CHECK_TIMEOUT)
            fetch_ms = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            data = r.json()
            b64 = data.get("front_frame")
            if not b64:
                return None
            decoded = base64_to_bytes(b64)
            if decoded is None:
                return None
            capture_ms = float(data.get("capture_ms", 0))
            metrics = {"capture_ms": capture_ms, "fetch_ms": fetch_ms}
            return (decoded, metrics)
        except Exception as e:
            self._logger.debug("Front camera full frame unavailable: %s", e)
            return None

    # Min delay between frame pulls; rate limited by get_front_camera_frame() (HTTP + SDK).
    CAMERA_STREAM_LOOP_SLEEP = 0.01

    def get_front_camera_stream(
        self, stop_event=None
    ) -> Iterator[Optional[Tuple[bytes, Dict[str, float]]]]:
        """
        Yield front camera frames at max sustainable rate (reuses get_front_camera_frame).

        Frame rate dominated by get_front_camera_frame() latency (HTTP + SDK).
        Yields (frame_bytes, metrics) or None.
        """
        while stop_event is None or not stop_event.is_set():
            result = self.get_front_camera_frame()
            yield result
            time.sleep(self.CAMERA_STREAM_LOOP_SLEEP)

    def get_telemetry(self) -> Optional[TelemetryFrame]:
        """
        Get latest telemetry data from the robot.

        Fetches sensor data from the SDK's /data endpoint (battery, GPS, IMU, RPMs, etc.).

        Returns
        -------
        TelemetryFrame or None
            Sensor data, or None if unavailable.

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
