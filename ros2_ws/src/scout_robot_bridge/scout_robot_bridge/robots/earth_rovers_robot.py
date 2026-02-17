import asyncio
import base64
import os
import sys
from typing import Optional

import requests

from scout_robot_bridge.robot_base import RobotBase
from scout_robot_bridge.robot_sdk.earth_rovers_sdk import BrowserService, RtmClient

FRODOBOTS_API_URL = os.getenv(
    "FRODOBOTS_API_URL", "https://frodobots-web-api.onrender.com/api/v1"
)


def _fetch_auth_sync() -> Optional[dict]:
    """Fetch auth data from FrodoBots API (sync). Returns dict for RtmClient or None."""
    auth_header = os.getenv("SDK_API_TOKEN")
    bot_slug = os.getenv("BOT_SLUG")
    mission_slug = os.getenv("MISSION_SLUG")
    if not auth_header or not bot_slug:
        return None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_header}",
    }
    try:
        if mission_slug:
            resp = requests.post(
                f"{FRODOBOTS_API_URL}/sdk/start_ride",
                headers=headers,
                json={"bot_slug": bot_slug, "mission_slug": mission_slug},
                timeout=15,
            )
        else:
            resp = requests.post(
                f"{FRODOBOTS_API_URL}/sdk/token",
                headers=headers,
                json={"bot_slug": bot_slug},
                timeout=15,
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        auth = {
            "CHANNEL_NAME": data.get("CHANNEL_NAME"),
            "RTM_TOKEN": data.get("RTM_TOKEN"),
            "USERID": data.get("USERID"),
            "APP_ID": data.get("APP_ID"),
            "BOT_UID": data.get("BOT_UID"),
        }
        if all(auth.get(k) for k in ("CHANNEL_NAME", "RTM_TOKEN", "USERID", "APP_ID")):
            return auth
        return None
    except Exception:
        return None


def _base64_to_bytes(data_url_or_b64: Optional[str]) -> Optional[bytes]:
    """Convert front() result (data URL or raw base64) to bytes."""
    if not data_url_or_b64:
        return None
    s = data_url_or_b64.strip()
    if s.startswith("data:"):
        # e.g. data:image/png;base64,<payload>
        idx = s.find("base64,")
        if idx == -1:
            return None
        s = s[idx + 7 :]
    try:
        return base64.b64decode(s)
    except Exception:
        return None


class EarthRoversRobot(RobotBase):
    """Robot implementation using Earth Rovers (FrodoBot) SDK."""

    def __init__(self) -> None:
        auth = _fetch_auth_sync()
        self._rtm_client: Optional[RtmClient] = RtmClient(auth) if auth else None
        self._browser_service: Optional[BrowserService] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._camera_disabled = False

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def move_forward(self) -> None:
        if self._rtm_client:
            self._rtm_client.send_message({"linear": 1, "angular": 0, "lamp": 0})

    def move_backward(self) -> None:
        if self._rtm_client:
            self._rtm_client.send_message({"linear": -1, "angular": 0, "lamp": 0})

    def move_left(self) -> None:
        if self._rtm_client:
            self._rtm_client.send_message({"linear": 0, "angular": 1, "lamp": 0})

    def move_right(self) -> None:
        if self._rtm_client:
            self._rtm_client.send_message({"linear": 0, "angular": -1, "lamp": 0})

    def stop(self) -> None:
        """Stop the robot by sending zero velocity commands."""
        if self._rtm_client:
            self._rtm_client.send_message({"linear": 0, "angular": 0, "lamp": 0})

    def send_velocity(self, linear: float, angular: float) -> None:
        """
        Send continuous velocity commands to the robot.
        linear: forward/backward speed (-1.0 to 1.0)
        angular: rotation speed left/right (-1.0 to 1.0)
        
        Clamps values to [-1.0, 1.0] range as per Frodobots SDK spec.
        """
        if self._rtm_client:
            # Clamp values to valid range [-1.0, 1.0]
            linear_clamped = max(-1.0, min(1.0, linear))
            angular_clamped = max(-1.0, min(1.0, angular))
            self._rtm_client.send_message({
                "linear": linear_clamped,
                "angular": angular_clamped,
                "lamp": 0
            })

    def get_front_camera_frame(self) -> Optional[bytes]:
        if self._camera_disabled:
            return None
        if self._browser_service is None:
            # Do not launch browser when SDK is unreachable; avoids pyppeteer cleanup crash
            try:
                r = requests.get("http://127.0.0.1:8000/sdk", timeout=1)
                r.raise_for_status()
            except Exception:
                self._camera_disabled = True
                print("Front camera disabled: SDK not reachable at http://127.0.0.1:8000 (run Earth Rovers SDK there to enable)", file=sys.stderr)
                return None
            self._browser_service = BrowserService()
        loop = self._ensure_loop()
        try:
            result = loop.run_until_complete(self._browser_service.front())
            return _base64_to_bytes(result)
        except Exception:
            self._camera_disabled = True
            self._browser_service = None
            return None
