"""
Parse /robot/telemetry JSON (same format as bridge TelemetryFrame) into a minimal
type for manual_controller safety. No dependency on connectx_robot_bridge.
"""

import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TelemetryForSafety:
    """Minimal telemetry for safety limits (battery, GPS, stuck detection)."""

    battery: float
    signal_level: int
    speed: float
    gps_signal: float
    orientation: int  # 0-360 (degrees; bridge converts from SDK 0-180)
    rpms: List[List[float]]  # [fl, fr, rl, rr, timestamp] per sample

    def orientation_degrees(self) -> float:
        return float(self.orientation % 360)

    def average_rpm(self) -> Optional[float]:
        if not self.rpms:
            return None
        try:
            rpm_values = [
                abs(rpm[0]) + abs(rpm[1]) + abs(rpm[2]) + abs(rpm[3])
                for rpm in self.rpms
                if len(rpm) >= 4
            ]
            if not rpm_values:
                return None
            return sum(rpm_values) / len(rpm_values)
        except (IndexError, ValueError):
            return None


def parse_telemetry_json(json_str: str) -> Optional[TelemetryForSafety]:
    """
    Parse /robot/telemetry JSON string (bridge publishes asdict(TelemetryFrame)).

    Returns:
        TelemetryForSafety or None if invalid/missing.
    """
    if not json_str or not json_str.strip():
        return None
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return TelemetryForSafety(
            battery=float(data.get("battery", 0)),
            signal_level=int(data.get("signal_level", 0)),
            speed=float(data.get("speed", 0)),
            gps_signal=float(data.get("gps_signal", 0)),
            orientation=int(data.get("orientation", 0)),
            rpms=list(data.get("rpms", [])) if isinstance(data.get("rpms"), list) else [],
        )
    except (TypeError, ValueError):
        return None
