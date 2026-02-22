"""WebRTC configuration from environment (ICE servers). No rclpy/aiortc dependency."""

import os


def get_ice_servers_dict():
    """
    Build ICE server list from env for WebRTC (STUN + optional TURN).

    Returns
    -------
        List of dicts with "urls" and optionally "username" and "credential".

    """
    servers = [{"urls": os.getenv("STUN_URL", "stun:stun.l.google.com:19302")}]
    turn_url = os.getenv("TURN_URL")
    if turn_url:
        entry = {"urls": turn_url}
        if os.getenv("TURN_USERNAME"):
            entry["username"] = os.getenv("TURN_USERNAME")
        if os.getenv("TURN_CREDENTIAL"):
            entry["credential"] = os.getenv("TURN_CREDENTIAL")
        servers.append(entry)
    return servers
