"""
Parse high-level command strings into a sequence of goals (drive/turn).

No ROS dependency; pure Python for unit testing.
Input examples: "forward 1m", "turn right 30", "right 30 at 0.3 for 2 s",
"forward at 0.4 m/s for 5 s", "stop".
"""

import re
from typing import List, Optional

# Unit conversions to meters
FT_TO_M = 0.3048
DEG_TO_RAD = 0.017453292519943295  # pi/180

# Reserved command that means "clear queue, stop"
STOP_COMMAND = "stop"


def _parse_float(s: str, default: Optional[float] = None) -> Optional[float]:
    """Parse a string to float; return default if empty or invalid."""
    s = (s or "").strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


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


def _parse_turn_profile_suffix(clause: str) -> dict:
    """
    Parse optional turn profile from end of clause.

    [at <v> rad/s] [for <t> s] [accel <a> decel <d>].
    Angular velocity: "0.4" or "0.4 rad/s" or "30 deg/s" (converted to rad/s).
    Returns dict with optional: angular_vel_rad_s, duration_s, accel_rad_s2, decel_rad_s2.
    """
    out: dict = {}
    # at <v> [rad/s|deg/s], for <t> s, accel <a> decel <d>
    pattern = (
        r"at\s+([\d.]+)\s*(rad/s|deg/s)?\s*(?:for\s+([\d.]+)\s*s)?"
        r"\s*(?:accel\s+([\d.]+)\s+decel\s+([\d.]+))?$"
    )
    m = re.search(pattern, clause, re.IGNORECASE)
    if m:
        v_str, unit, t_str, a_str, d_str = m.groups()
        v = _parse_float(v_str)
        if v is not None and v > 0:
            if (unit or "").lower() == "deg/s":
                out["angular_vel_rad_s"] = v * DEG_TO_RAD
            else:
                out["angular_vel_rad_s"] = v
        if t_str:
            t = _parse_float(t_str)
            if t is not None and t > 0:
                out["duration_s"] = t
        if a_str and d_str:
            a, d = _parse_float(a_str), _parse_float(d_str)
            if a is not None and a > 0:
                out["accel_rad_s2"] = a
            if d is not None and d > 0:
                out["decel_rad_s2"] = d
    else:
        # Try "for X s" and "accel A decel D" without "at"
        m2 = re.search(
            r"for\s+([\d.]+)\s*s\s*(?:accel\s+([\d.]+)\s+decel\s+([\d.]+))?$",
            clause,
            re.IGNORECASE,
        )
        if m2:
            t_str, a_str, d_str = m2.groups()
            if t_str:
                t = _parse_float(t_str)
                if t is not None and t > 0:
                    out["duration_s"] = t
            if a_str and d_str:
                a, d = _parse_float(a_str), _parse_float(d_str)
                if a is not None and a > 0:
                    out["accel_rad_s2"] = a
                if d is not None and d > 0:
                    out["decel_rad_s2"] = d
        else:
            m3 = re.search(r"accel\s+([\d.]+)\s+decel\s+([\d.]+)", clause, re.IGNORECASE)
            if m3:
                a_str, d_str = m3.groups()
                a, d = _parse_float(a_str), _parse_float(d_str)
                if a is not None and a > 0:
                    out["accel_rad_s2"] = a
                if d is not None and d > 0:
                    out["decel_rad_s2"] = d
    return out


def _parse_drive_profile_suffix(clause: str) -> dict:
    """
    Parse optional drive profile: [at <v> m/s] [for <t> s] [accel <a> decel <d>].

    Returns dict with optional: linear_vel_m_s, duration_s, accel_m_s2, decel_m_s2.
    """
    out: dict = {}
    pattern = (
        r"at\s+([\d.]+)\s*(?:m/s)?\s*(?:for\s+([\d.]+)\s*s)?"
        r"\s*(?:accel\s+([\d.]+)\s+decel\s+([\d.]+))?$"
    )
    m = re.search(pattern, clause, re.IGNORECASE)
    if m:
        v_str, t_str, a_str, d_str = m.groups()
        v = _parse_float(v_str)
        if v is not None and v > 0:
            out["linear_vel_m_s"] = v
        if t_str:
            t = _parse_float(t_str)
            if t is not None and t > 0:
                out["duration_s"] = t
        if a_str and d_str:
            a, d = _parse_float(a_str), _parse_float(d_str)
            if a is not None and a > 0:
                out["accel_m_s2"] = a
            if d is not None and d > 0:
                out["decel_m_s2"] = d
    else:
        m2 = re.search(
            r"for\s+([\d.]+)\s*s\s*(?:accel\s+([\d.]+)\s+decel\s+([\d.]+))?$",
            clause,
            re.IGNORECASE,
        )
        if m2:
            t_str, a_str, d_str = m2.groups()
            if t_str:
                t = _parse_float(t_str)
                if t is not None and t > 0:
                    out["duration_s"] = t
            if a_str and d_str:
                a, d = _parse_float(a_str), _parse_float(d_str)
                if a is not None and a > 0:
                    out["accel_m_s2"] = a
                if d is not None and d > 0:
                    out["decel_m_s2"] = d
        else:
            m3 = re.search(r"accel\s+([\d.]+)\s+decel\s+([\d.]+)", clause, re.IGNORECASE)
            if m3:
                a_str, d_str = m3.groups()
                a, d = _parse_float(a_str), _parse_float(d_str)
                if a is not None and a > 0:
                    out["accel_m_s2"] = a
                if d is not None and d > 0:
                    out["decel_m_s2"] = d
    return out


def parse_command(command: str) -> List[dict]:
    """
    Parse a command string into a list of goals.

    Returns
    -------
        List of goals. Each goal is:
        - {"type": "drive", "distance_m": float, "direction": 1 or -1 [, profile]}
        - {"type": "turn", "angle_deg": float [, profile]}
        (positive angle_deg = right/clockwise). Optional profile: angular_vel_rad_s,
        duration_s, accel_rad_s2, decel_rad_s2 for turn; linear_vel_m_s, duration_s,
        accel_m_s2, decel_m_s2 for drive. For "stop", returns [].

    """
    if not command or not isinstance(command, str):
        return []
    raw = command.strip().lower()
    if raw == STOP_COMMAND:
        return []
    # "wander" and "wander <speed>" are handled by wander_planner; no goals for controller
    if raw == "wander" or raw.startswith("wander "):
        return []

    goals: List[dict] = []
    clauses = re.split(r"\s+then\s+|\s*,\s*", raw, flags=re.IGNORECASE)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        # Short turn: "left 30", "right 45", or "right 30 at 0.3 for 2 s accel 0.2 decel 0.3"
        short_turn = re.match(
            r"^(left|right)\s+([\d.]+)\s*(deg(rees)?|°)?\s*(.*)$",
            clause,
            re.IGNORECASE,
        )
        if short_turn:
            direction, num, _, _, rest = short_turn.groups()
            angle = _parse_angle(num)
            if direction.lower() == "right":
                angle_deg = angle
            else:
                angle_deg = -angle
            goal: dict = {"type": "turn", "angle_deg": angle_deg}
            profile = _parse_turn_profile_suffix(rest)
            goal.update(profile)
            goals.append(goal)
            continue

        # Full turn: "turn left 30", "turn right 30 deg at 0.4 for 2 s accel ..."
        turn_match = re.match(
            r"turn\s+(left|right)\s+([\d.]+)\s*(deg(rees)?|°)?\s*(.*)$",
            clause,
            re.IGNORECASE,
        )
        if turn_match:
            direction, num, _, _, rest = turn_match.groups()
            angle = _parse_angle(num)
            prof = _parse_turn_profile_suffix(rest)
            if direction == "right":
                goals.append({"type": "turn", "angle_deg": angle, **prof})
            else:
                goals.append({"type": "turn", "angle_deg": -angle, **prof})
            continue

        # Time-based drive: "forward at 0.4 m/s for 5 s [accel 0.2 decel 0.3]"
        time_drive = re.match(
            r"(forward|fwd|back|backward)\s+at\s+([\d.]+)\s*(?:m/s)?\s+for\s+([\d.]+)\s*s\s*(.*)$",
            clause,
            re.IGNORECASE,
        )
        if time_drive:
            direction_word, vel_str, dur_str, rest = time_drive.groups()
            vel = _parse_float(vel_str)
            dur = _parse_float(dur_str)
            if vel is not None and vel > 0 and dur is not None and dur > 0:
                direction = -1 if direction_word in ("back", "backward") else 1
                # Distance from v*t (approximate; profile will run for duration)
                distance_m = vel * dur
                goal = {
                    "type": "drive",
                    "distance_m": distance_m,
                    "direction": direction,
                    "linear_vel_m_s": vel,
                    "duration_s": dur,
                }
                goal.update(_parse_drive_profile_suffix((rest or "").strip()))
                goals.append(goal)
            continue

        # Distance-based drive: "forward 2 m", "forward 2 m at 0.3 for 7 s accel ..."
        drive_match = re.match(
            r"(forward|fwd|back|backward)\s+([\d.]+)\s*(m|meter|meters?|ft|feet)?\s*(.*)$",
            clause,
            re.IGNORECASE,
        )
        if drive_match:
            direction_word, num_str, unit, rest = drive_match.groups()
            num = _parse_float(num_str)
            if num is not None and num > 0:
                if (unit or "").lower() in ("ft", "feet"):
                    distance_m = num * FT_TO_M
                else:
                    distance_m = num
                direction = -1 if direction_word in ("back", "backward") else 1
                goal = {"type": "drive", "distance_m": distance_m, "direction": direction}
                goal.update(_parse_drive_profile_suffix(rest or ""))
                goals.append(goal)
            continue

        # Legacy: "forward 1ft", "fwd 1m" (no space before m/ft)
        drive_legacy = re.match(
            r"(forward|fwd|back|backward)\s+(.+)$",
            clause,
            re.IGNORECASE,
        )
        if drive_legacy:
            direction_word, dist_str = drive_legacy.groups()
            distance_m = _parse_distance(dist_str)
            if distance_m > 0:
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
