import json
import logging
from typing import Optional

import requests

try:
    from bunny_robot_bridge.core.exceptions import ConfigurationError
except ImportError:
    class ConfigurationError(Exception):
        """Raised when configuration is invalid or missing (SDK standalone mode)."""
        pass

logger = logging.getLogger(__name__)


class RtmClient:
    """Client for sending RTM messages to Agora RTM service."""

    def __init__(self, auth_response_data: dict):
        """
        Initialize RTM client with authentication data.
        
        Args:
            auth_response_data: Dictionary containing APP_ID, CHANNEL_NAME, RTM_TOKEN, USERID, BOT_UID
            
        Raises:
            ConfigurationError: If required auth data is missing
        """
        self.app_id = auth_response_data.get("APP_ID")
        self.channel = auth_response_data.get("CHANNEL_NAME")
        self.token = auth_response_data.get("RTM_TOKEN")
        self.uid = str(auth_response_data.get("USERID"))
        
        # Validate required fields
        if not all([self.app_id, self.channel, self.token, self.uid]):
            missing = [
                k for k, v in {
                    "APP_ID": self.app_id,
                    "CHANNEL_NAME": self.channel,
                    "RTM_TOKEN": self.token,
                    "USERID": self.uid,
                }.items()
                if not v
            ]
            raise ConfigurationError(f"Missing required RTM auth fields: {', '.join(missing)}")
        
        # Peer messages must be sent to the bot's UID (the robot); SDK uses sendMessageToPeer(botUid)
        bot_uid = auth_response_data.get("BOT_UID")
        self.destination = (
            str(bot_uid) if bot_uid is not None and str(bot_uid).strip()
            else self.channel.replace("sdk_", "", 1)
        )

    def send_message(self, message: dict) -> bool:
        """
        Send a message via RTM.
        
        Args:
            message: Message dictionary to send
            
        Returns:
            True if message sent successfully, False otherwise
            
        Note:
            Errors are logged but exceptions are not raised to avoid disrupting robot control.
            Callers can check return value if needed.
        """
        try:
            # Convert the message dictionary to a JSON string
            message_json = json.dumps(message, separators=(',', ':'))

            url = f"https://api.agora.io/dev/v2/project/{self.app_id}/rtm/users/{self.uid}/peer_messages"
            headers = {
                "x-agora-uid": self.uid,
                "x-agora-token": self.token
            }

            payload = {
                "destination": self.destination,
                "enable_offline_messaging": False,
                "enable_historical_messaging": False,
                "payload": message_json
            }

            response = requests.post(url, headers=headers, json=payload, timeout=5)
            
            if response.status_code == 200:
                return True
            else:
                logger.warning(
                    f"RTM message send failed with status {response.status_code}: {response.text}"
                )
                return False
                
        except requests.RequestException as e:
            logger.warning(f"RTM message send failed due to network error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending RTM message: {e}")
            return False
