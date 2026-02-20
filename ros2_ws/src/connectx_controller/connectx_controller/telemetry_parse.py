"""
Parse /robot/telemetry JSON string into heading, speed, timestamp.

No dependency on connectx_robot_bridge; matches bridge telemetry JSON schema.
"""

import json
from typing import Optional, Tuple


def parse_telemetry(json_str: str) -> Optional[Tuple[float, float, float]]:
    """
    Parse telemetry JSON from /robot/telemetry.

    Returns:
        (heading_deg, speed_m_s, timestamp) or None if invalid/missing.
        heading_deg: 0--360 from orientation (0--255).
        speed_m_s: current speed (m/s).
        timestamp: Unix epoch.
    """
    if not json_str or not json_str.strip():
        return None
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    orientation = data.get("orientation")
    speed = data.get("speed")
    timestamp = data.get("timestamp")
    if orientation is None and speed is None and timestamp is None:
        return None
    heading_deg = (float(orientation) / 255.0) * 360.0 if orientation is not None else 0.0
    speed_m_s = float(speed) if speed is not None else 0.0
    ts = float(timestamp) if timestamp is not None else 0.0
    return (heading_deg, speed_m_s, ts)
