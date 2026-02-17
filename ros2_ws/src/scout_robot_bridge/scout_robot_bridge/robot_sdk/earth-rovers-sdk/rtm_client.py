import requests
import json

class RtmClient:
    def __init__(self, auth_response_data):
        self.app_id = auth_response_data.get("APP_ID")
        self.channel = auth_response_data.get("CHANNEL_NAME")
        self.token = auth_response_data.get("RTM_TOKEN")
        self.uid = str(auth_response_data.get("USERID"))
        # Peer messages must be sent to the bot's UID (the robot); SDK uses sendMessageToPeer(botUid)
        bot_uid = auth_response_data.get("BOT_UID")
        self.destination = str(bot_uid) if bot_uid is not None and str(bot_uid).strip() else self.channel.replace("sdk_", "", 1)

    def send_message(self, message: dict):
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

        response = requests.post(url, headers=headers, json=payload)
        # Non-200 is logged by the bridge if needed; avoid printing to keep logs clean
