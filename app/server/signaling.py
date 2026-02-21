"""
WebSocket signaling for WebRTC: relay offer/answer/ICE between browser and robot.

Supports multiple concurrent robot sessions via *rooms*.  Each room is keyed by
a ``robot_id`` string (UUID or the legacy sentinel ``"default"``).  The legacy
``/ws/signaling`` endpoint continues to use the ``"default"`` room so existing
single-robot deployments remain unchanged.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_DEFAULT_ROOM = "default"


@dataclass
class _Room:
    """State for a single robot signaling session."""
    browser_ws: Optional[WebSocket] = None
    robot_ws: Optional[WebSocket] = None
    pending_offer: Optional[str] = None
    first_telemetry_relayed: bool = False
    last_telemetry: Optional[dict] = None


# Global room registry
_rooms: Dict[str, _Room] = {}


def _get_room(robot_id: str) -> _Room:
    if robot_id not in _rooms:
        _rooms[robot_id] = _Room()
    return _rooms[robot_id]


def get_last_telemetry(robot_id: str = _DEFAULT_ROOM) -> Optional[dict]:
    """Return the last telemetry dict received from the robot (for /data fallback)."""
    room = _rooms.get(robot_id)
    return room.last_telemetry if room else None


async def send_control_to_robot(
    linear_x: float, angular_z: float, robot_id: str = _DEFAULT_ROOM
) -> bool:
    """Send a velocity command to the robot via the signaling WebSocket.
    Returns True if the message was sent, False if no robot is connected."""
    room = _rooms.get(robot_id)
    if room is None or room.robot_ws is None:
        return False
    try:
        payload = json.dumps({
            "type": "control",
            "data": {"linear_x": linear_x, "angular_z": angular_z},
        })
        await room.robot_ws.send_text(payload)
        return True
    except Exception as e:
        logger.warning("Failed to send control to robot %s: %s", robot_id, e)
        return False


async def _set_connection(room: _Room, role: str, ws: WebSocket) -> None:
    if role == "browser":
        if room.browser_ws is not None:
            try:
                await room.browser_ws.close()
            except Exception:
                pass
        room.browser_ws = ws
    elif role == "robot":
        if room.robot_ws is not None:
            try:
                await room.robot_ws.close()
            except Exception:
                pass
        room.robot_ws = ws


def _clear_connection(room: _Room, role: str) -> None:
    if role == "browser":
        room.browser_ws = None
    elif role == "robot":
        room.robot_ws = None


async def handle_signaling_websocket(
    websocket: WebSocket, robot_id: str = _DEFAULT_ROOM
) -> None:
    room = _get_room(robot_id)
    await websocket.accept()
    role: Optional[str] = None

    try:
        # First message must be {"role": "robot"} or {"role": "browser"}
        raw = await websocket.receive_text()
        try:
            msg = json.loads(raw)
            r = msg.get("role")
            if r not in ("robot", "browser"):
                await websocket.close(code=4000, reason="Invalid role")
                return
            role = r
            await _set_connection(room, role, websocket)
            logger.info("Signaling[%s]: %s connected", robot_id, role)
            # So browser knows it is registered before sending offer
            if role == "browser":
                try:
                    await websocket.send_text(json.dumps({"type": "welcome", "role": "browser"}))
                except Exception as e:
                    logger.warning("Failed to send welcome to browser: %s", e)
            # If robot just connected and we have a pending offer from the browser, send it now
            if role == "robot" and room.pending_offer is not None:
                try:
                    await websocket.send_text(room.pending_offer)
                    room.pending_offer = None
                    logger.debug("Sent pending offer to robot %s", robot_id)
                except Exception as e:
                    logger.warning("Failed to send pending offer to robot: %s", e)
        except json.JSONDecodeError:
            await websocket.close(code=4000, reason="Expected JSON with role")
            return

        # Relay loop: forward messages to the other role
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Log and store telemetry from robot
            if role == "robot" and payload.get("type") == "telemetry":
                data = payload.get("data") or {}
                if isinstance(data, dict):
                    room.last_telemetry = data
                if not room.first_telemetry_relayed:
                    room.first_telemetry_relayed = True
                    logger.info(
                        "Signaling[%s]: first telemetry received from robot", robot_id
                    )
                logger.debug(
                    "telemetry[%s] | battery=%.0f%% speed=%.2f gps_signal=%.1f lat=%.4f lon=%.4f orientation=%s rpms=%s",
                    robot_id,
                    data.get("battery", 0),
                    data.get("speed", 0),
                    data.get("gps_signal", 0),
                    data.get("latitude", 0),
                    data.get("longitude", 0),
                    data.get("orientation", 0),
                    data.get("rpms", []),
                )
                if data.get("accels"):
                    logger.debug("telemetry accels=%s", data["accels"])
                if data.get("gyros"):
                    logger.debug("telemetry gyros=%s", data["gyros"])

            if role == "browser":
                target = room.robot_ws
                if target is None and payload.get("type") == "offer":
                    room.pending_offer = raw
                    logger.debug(
                        "No robot connected for %s, buffered offer", robot_id
                    )
            else:
                target = room.browser_ws

            if target is None:
                logger.debug(
                    "No peer connected for %s, dropping message from %s",
                    robot_id,
                    role,
                )
                continue

            try:
                await target.send_text(raw)
            except Exception as e:
                logger.warning("Failed to relay to peer: %s", e)
    except Exception as e:
        logger.info("Signaling[%s] connection closed: %s", robot_id, e)
    finally:
        if role is not None:
            _clear_connection(room, role)
            logger.info("Signaling[%s]: %s disconnected", robot_id, role)
            if role == "robot":
                room.first_telemetry_relayed = False
