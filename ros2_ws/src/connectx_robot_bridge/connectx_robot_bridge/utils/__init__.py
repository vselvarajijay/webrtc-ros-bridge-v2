"""Utility functions for connectx_robot_bridge."""

import base64
import os
from typing import Optional

import requests

from connectx_robot_bridge.core.constants import (
    AUTH_TIMEOUT,
    FRODOBOTS_API_URL,
    REQUIRED_AUTH_KEYS,
)
from connectx_robot_bridge.core.exceptions import AuthenticationError
from connectx_robot_bridge.utils.rtm_client import RtmClient

__all__ = ['RtmClient', 'fetch_auth_sync', 'base64_to_bytes']


def fetch_auth_sync() -> dict:
    """
    Fetch auth data from FrodoBots API (sync).
    
    Returns:
        dict: Auth data for RtmClient with keys: CHANNEL_NAME, RTM_TOKEN, USERID, APP_ID, BOT_UID
        
    Raises:
        AuthenticationError: If authentication fails or credentials are missing
    """
    auth_header = os.getenv("SDK_API_TOKEN")
    bot_slug = os.getenv("BOT_SLUG")
    mission_slug = os.getenv("MISSION_SLUG")
    
    if not auth_header or not bot_slug:
        raise AuthenticationError(
            "Missing required credentials: SDK_API_TOKEN and BOT_SLUG must be set"
        )
    
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
                timeout=AUTH_TIMEOUT,
            )
        else:
            resp = requests.post(
                f"{FRODOBOTS_API_URL}/sdk/token",
                headers=headers,
                json={"bot_slug": bot_slug},
                timeout=AUTH_TIMEOUT,
            )
        
        if resp.status_code != 200:
            raise AuthenticationError(
                f"Authentication failed with status {resp.status_code}: {resp.text}"
            )
        
        data = resp.json()
        auth = {
            "CHANNEL_NAME": data.get("CHANNEL_NAME"),
            "RTM_TOKEN": data.get("RTM_TOKEN"),
            "USERID": data.get("USERID"),
            "APP_ID": data.get("APP_ID"),
            "BOT_UID": data.get("BOT_UID"),
        }
        
        # Validate required keys
        missing_keys = [k for k in REQUIRED_AUTH_KEYS if not auth.get(k)]
        if missing_keys:
            raise AuthenticationError(
                f"Missing required auth keys: {', '.join(missing_keys)}"
            )
        
        return auth
        
    except requests.RequestException as e:
        raise AuthenticationError(f"Failed to connect to authentication API: {e}") from e
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        raise AuthenticationError(f"Unexpected error during authentication: {e}") from e


def base64_to_bytes(data_url_or_b64: Optional[str]) -> Optional[bytes]:
    """
    Convert front() result (data URL or raw base64) to bytes.
    
    Args:
        data_url_or_b64: Base64 string or data URL (e.g., "data:image/png;base64,...")
        
    Returns:
        Decoded bytes, or None if conversion fails
    """
    if not data_url_or_b64:
        return None
    
    s = data_url_or_b64.strip()
    if s.startswith("data:"):
        # e.g. data:image/png;base64,<payload>
        idx = s.find("base64,")
        if idx == -1:
            return None
        s = s[idx + 7:]
    
    try:
        return base64.b64decode(s)
    except Exception:
        return None
