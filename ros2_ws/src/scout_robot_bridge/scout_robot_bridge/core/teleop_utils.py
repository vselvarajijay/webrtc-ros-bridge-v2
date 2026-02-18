"""Utility functions for teleop display and feedback."""

from typing import Optional

from scout_robot_bridge.core.constants import (
    TELEOP_STUCK_RPM_THRESHOLD,
    TELEOP_STUCK_VELOCITY_THRESHOLD,
)
from scout_robot_bridge.core.models.telemetry import TelemetryFrame


def print_hud(
    telemetry: Optional[TelemetryFrame],
    linear_vel: float,
    angular_vel: float,
    speed_mode: int = 3,
    speed_mode_max: int = 5,
) -> None:
    """
    Print HUD overlay showing live telemetry status.

    Args:
        telemetry: Current telemetry frame (None if unavailable)
        linear_vel: Current linear velocity command
        angular_vel: Current angular velocity command
        speed_mode: Current speed mode (1=slowest, 5=fastest)
        speed_mode_max: Max speed mode (e.g. 5)
    """
    speed_str = f" S{speed_mode}/{speed_mode_max}"
    if telemetry is None:
        print(
            f"\r🔋-- | 📡-- | 🧭--° | GPS(?) | "
            f"v={linear_vel:.2f} a={angular_vel:.2f}{speed_str}    ",
            end="",
            flush=True,
        )
        return

    # Calculate stuck warning
    stuck_warn = ""
    avg_rpm = telemetry.average_rpm()
    if avg_rpm is not None and avg_rpm < TELEOP_STUCK_RPM_THRESHOLD and abs(linear_vel) > TELEOP_STUCK_VELOCITY_THRESHOLD:
        stuck_warn = " ⚠️  STUCK"

    # Convert orientation to degrees
    orientation_deg = telemetry.orientation_degrees()

    # GPS signal indicator
    gps_indicator = "✓" if telemetry.gps_signal > 15 else "✗"

    # Format and print HUD
    print(
        f"\r🔋{telemetry.battery:.0f}% | 📡{telemetry.signal_level} | "
        f"🧭{orientation_deg:.0f}° | GPS({gps_indicator}) | "
        f"v={telemetry.speed:.2f} cmd=({linear_vel:.2f},{angular_vel:.2f}){speed_str}{stuck_warn}    ",
        end="",
        flush=True,
    )
