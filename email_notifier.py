import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

CONFIG_PATH = "notification_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "receiver_email": "",
    "notify_unknown": True,
    "notify_vip": True,
    "vip_list": ["Girish"]
}

class EmailNotifier:
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

    def send_alert(self, subject: str, body: str) -> bool:
        if not self.config.get("enabled"):
            return False

        sender = self.config.get("sender_email")
        password = self.config.get("sender_password")
        receiver = self.config.get("receiver_email")
        smtp_server = self.config.get("smtp_server", "smtp.gmail.com")
        smtp_port = self.config.get("smtp_port", 587)

        if not sender or not password or not receiver:
            print("[WARN] Email notification skipped: Missing SMTP credentials.")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = receiver
            msg["Subject"] = f"[VisionTrack AI Alert] {subject}"

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, receiver, msg.as_string())

            print(f"[INFO] Email notification sent to {receiver}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send email alert: {e}")
            return False

if __name__ == "__main__":
    notifier = EmailNotifier()
    print("[INFO] Email Notifier Module Ready. Config:", notifier.config)
