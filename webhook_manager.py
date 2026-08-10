import os
import json
import requests
import threading
from datetime import datetime

WEBHOOK_CONFIG_PATH = "webhook_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "url": "",
    "secret": "",
    "events": ["unknown_face", "spoof_attack", "attendance_marked"]
}

class WebhookManager:
    """Asynchronous HTTP Webhook dispatcher for Slack, Discord, and external API integrations."""

    def __init__(self, config_path=WEBHOOK_CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self, new_config: dict):
        self.config.update(new_config)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)
        return self.config

    def _post(self, payload: dict):
        url = self.config.get("url")
        if not url:
            return

        headers = {"Content-Type": "application/json"}
        secret = self.config.get("secret")
        if secret:
            headers["X-Webhook-Secret"] = secret

        try:
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            print(f"[WARN] Webhook dispatch error: {e}")

    def dispatch_event(self, event_type: str, data: dict):
        """Dispatch event payload to configured webhook URL asynchronously."""
        if not self.config.get("enabled"):
            return

        subscribed = self.config.get("events", [])
        if event_type not in subscribed:
            return

        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        thread = threading.Thread(target=self._post, args=(payload,), daemon=True)
        thread.start()

    def test_webhook(self) -> dict:
        """Send a test payload to verify endpoint connectivity."""
        url = self.config.get("url")
        if not url:
            return {"success": False, "message": "No Webhook URL configured."}

        payload = {
            "event": "test_event",
            "timestamp": datetime.now().isoformat(),
            "data": {"message": "VisionTrack AI Webhook Connectivity Test Success"}
        }

        try:
            res = requests.post(url, json=payload, timeout=5)
            return {"success": True, "status_code": res.status_code, "message": f"Webhook delivered with status {res.status_code}."}
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

if __name__ == "__main__":
    wm = WebhookManager()
    print("[INFO] Webhook Manager Initialized. Config:", wm.config)
