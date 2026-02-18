"""
Parse high-level command strings into a sequence of goals (drive/turn).

No ROS dependency; pure Python for unit testing.
Input examples: "forward 1ft", "turn right 30", "forward 1m then turn left 45", "stop".
"""

import re
from typing import Any, List

# Unit conversions to meters
FT_TO_M = 0.3048

# Reserved command that means "clear queue, stop"
STOP_COMMAND = "stop"


def _parse_distance(s: str) -> float:
    """Parse a distance string like '1ft', '1.5m', '0.3m' into meters."""
    s = s.strip().lower()
    if s.endswith("ft") or s.endswith("feet"):
        base = s.replace("feet", "").replace("ft", "").strip()
        return float(base) * FT_TO_M
    if s.endswith("m") or s.endswith("meter") or s.endswith("meters"):
        base = s.rstrip("s").replace("meter", "").replace("m", "").strip()
        if not base:
            return 0.0
        return float(base)
    # Default: assume meters
    return float(s)


def _parse_angle(s: str) -> float:
    """Parse angle string like '30', '30deg', '45 degrees' into degrees (float)."""
    s = re.sub(r"(deg(rees)?|°)\s*$", "", s.strip(), flags=re.IGNORECASE).strip()
    return float(s) if s else 0.0


def parse_command(command: str) -> List[dict]:
    """
    Parse a command string into a list of goals.

    Returns:
        List of goals. Each goal is:
        - {"type": "drive", "distance_m": float, "direction": 1 or -1}
        - {"type": "turn", "angle_deg": float}  (positive = right/clockwise)
        For "stop", returns [].
    """
    if not command or not isinstance(command, str):
        return []
    raw = command.strip().lower()
    if raw == STOP_COMMAND:
        return []

    goals: List[dict] = []
    # Split on "then" or "," to get clauses
    clauses = re.split(r"\s+then\s+|\s*,\s*", raw, flags=re.IGNORECASE)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        # Turn: "turn left 30", "turn right 45", "turn left 30 deg"
        turn_match = re.match(
            r"turn\s+(left|right)\s+([\d.]+)\s*(deg(rees)?|°)?",
            clause,
            re.IGNORECASE,
        )
        if turn_match:
            direction, num, _ = turn_match.groups()
            angle = _parse_angle(num)
            if direction == "right":
                goals.append({"type": "turn", "angle_deg": angle})
            else:
                goals.append({"type": "turn", "angle_deg": -angle})
            continue

        # Drive: "forward 1ft", "fwd 1m", "back 0.5m", "backward 2ft"
        drive_match = re.match(
            r"(forward|fwd|back|backward)\s+(.+)$",
            clause,
            re.IGNORECASE,
        )
        if drive_match:
            direction_word, dist_str = drive_match.groups()
            distance_m = _parse_distance(dist_str)
            if distance_m <= 0:
                continue
            direction = -1 if direction_word in ("back", "backward") else 1
            goals.append({"type": "drive", "distance_m": distance_m, "direction": direction})
            continue

        # Optional: bare "1m" or "1ft" as forward
        bare_dist = re.match(r"^([\d.]+)\s*(ft|feet|m|meter|meters?)\s*$", clause, re.IGNORECASE)
        if bare_dist:
            num, unit = bare_dist.groups()
            dist_str = f"{num}{unit}" if unit in ("ft", "m") else f"{num} {unit}"
            distance_m = _parse_distance(dist_str)
            if distance_m > 0:
                goals.append({"type": "drive", "distance_m": distance_m, "direction": 1})

    return goals
