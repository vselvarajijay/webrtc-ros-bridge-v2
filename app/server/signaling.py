"""
WebSocket signaling for WebRTC: relay offer/answer/ICE between browser and robot.
Single session: at most one connection per role (browser, robot).
"""

import json
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# At most one WebSocket per role
_browser_ws: Optional[WebSocket] = None
_robot_ws: Optional[WebSocket] = None
# If browser sends offer before robot connects, hold it and deliver when robot connects
_pending_offer: Optional[str] = None


def _set_connection(role: str, ws: WebSocket) -> None:
    global _browser_ws, _robot_ws
    if role == "browser":
        if _browser_ws is not None:
            try:
                _browser_ws.close()
            except Exception:
                pass
        _browser_ws = ws
    elif role == "robot":
        if _robot_ws is not None:
            try:
                _robot_ws.close()
            except Exception:
                pass
        _robot_ws = ws


def _clear_connection(role: str) -> None:
    global _browser_ws, _robot_ws
    if role == "browser":
        _browser_ws = None
    elif role == "robot":
        _robot_ws = None


async def handle_signaling_websocket(websocket: WebSocket) -> None:
    global _pending_offer
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
            _set_connection(role, websocket)
            logger.info("Signaling: %s connected", role)
            # So browser knows it is registered before sending offer
            if role == "browser":
                try:
                    await websocket.send_text(json.dumps({"type": "welcome", "role": "browser"}))
                except Exception as e:
                    logger.warning("Failed to send welcome to browser: %s", e)
            # If robot just connected and we have a pending offer from the browser, send it now
            if role == "robot" and _pending_offer is not None:
                try:
                    await websocket.send_text(_pending_offer)
                    _pending_offer = None
                    logger.debug("Sent pending offer to robot")
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

            # Log telemetry from robot (velocity, battery, GPS, IMU, etc.)
            if role == "robot" and payload.get("type") == "telemetry":
                data = payload.get("data") or {}
                logger.info(
                    "telemetry | battery=%.0f%% speed=%.2f gps_signal=%.1f lat=%.4f lon=%.4f orientation=%s rpms=%s",
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
                target = _robot_ws
                if target is None and payload.get("type") == "offer":
                    _pending_offer = raw
                    logger.debug("No robot connected, buffered offer for when robot connects")
            else:
                target = _browser_ws

            if target is None:
                logger.debug("No peer connected, dropping message from %s", role)
                continue

            try:
                await target.send_text(raw)
            except Exception as e:
                logger.warning("Failed to relay to peer: %s", e)
    except Exception as e:
        logger.info("Signaling connection closed: %s", e)
    finally:
        if role is not None:
            _clear_connection(role)
            logger.info("Signaling: %s disconnected", role)
