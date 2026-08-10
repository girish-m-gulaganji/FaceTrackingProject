import os
import json
import urllib.request
import urllib.parse
import cv2

CONFIG_PATH = "telegram_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "bot_token": "",
    "chat_id": "",
    "notify_unknown": True,
    "notify_vip": True
}

class TelegramNotifier:
    """Instant Telegram push alert notifier with face snapshot support."""

    def __init__(self, config_path=CONFIG_PATH):
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

    def send_alert(self, subject: str, message_text: str, frame_bgr=None) -> bool:
        if not self.config.get("enabled"):
            return False

        bot_token = self.config.get("bot_token")
        chat_id = self.config.get("chat_id")

        if not bot_token or not chat_id:
            print("[WARN] Telegram alert skipped: Missing bot token or chat ID.")
            return False

        text = f"🚨 *[VisionTrack AI Security Alert]* 🚨\n\n*Subject*: {subject}\n*Details*: {message_text}"

        try:
            if frame_bgr is not None:
                # Send photo with caption
                _, img_encoded = cv2.imencode('.jpg', frame_bgr)
                photo_bytes = img_encoded.tobytes()

                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="caption"\r\n\r\n{text}\r\n'
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nMarkdown\r\n'
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="photo"; filename="snapshot.jpg"\r\n'
                    f"Content-Type: image/jpeg\r\n\r\n"
                ).encode('utf-8') + photo_bytes + f"\r\n--{boundary}--\r\n".encode('utf-8')

                req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            else:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                params = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
                req = urllib.request.Request(url, data=params)

            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[INFO] Telegram alert sent successfully to Chat ID: {chat_id}")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to send Telegram alert: {e}")
            return False

if __name__ == "__main__":
    notifier = TelegramNotifier()
    print("[INFO] Telegram Notifier Module Ready. Config:", notifier.config)
