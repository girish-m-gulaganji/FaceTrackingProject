import os
import time
import json
import threading
from datetime import datetime
from face_tracker_engine import AttendanceLogger
from pdf_generator import generate_pdf_report
from email_notifier import EmailNotifier

SCHEDULER_CONFIG_PATH = "scheduler_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "dispatch_time": "18:00",
    "recipient_email": "",
    "last_run_date": ""
}

class AttendanceReportScheduler:
    """Background service for automated daily PDF/Excel attendance report dispatch."""

    def __init__(self, config_path=SCHEDULER_CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()
        self.notifier = EmailNotifier()
        self.running = False
        self.thread = None

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

    def trigger_dispatch(self) -> dict:
        """Compile today's attendance logs into PDF & Excel and send email dispatch."""
        logger = AttendanceLogger()
        csv_file = logger.save_csv()
        excel_file = logger.save_excel()
        pdf_file = generate_pdf_report(csv_file)

        today_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"Daily Attendance Executive Summary ({today_str})"
        body = f"VisionTrack AI Automated Report Dispatch\n\nDate: {today_str}\n\nPDF & CSV reports have been generated and attached."

        sent = self.notifier.send_alert(subject, body)
        
        # Telegram Automated Summary Alert
        telegram_sent = False
        try:
            from telegram_notifier import TelegramNotifier
            telegram_bot = TelegramNotifier()
            if telegram_bot.enabled:
                tg_msg = f"📊 *Daily Attendance PDF Executive Summary*\n📅 *Date*: {today_str}\n\nPDF & CSV reports generated successfully."
                telegram_sent = telegram_bot.send_alert("Daily Report Summary", tg_msg)
        except Exception as e:
            print(f"[WARN] Telegram report dispatch error: {e}")

        self.config["last_run_date"] = today_str
        self.save_config(self.config)

        return {
            "success": True,
            "date": today_str,
            "csv": os.path.basename(csv_file),
            "excel": os.path.basename(excel_file),
            "pdf": os.path.basename(pdf_file),
            "email_sent": sent,
            "telegram_sent": telegram_sent
        }

    def _loop(self):
        while self.running:
            try:
                if self.config.get("enabled"):
                    now = datetime.now()
                    current_time = now.strftime("%H:%M")
                    today_date = now.strftime("%Y-%m-%d")
                    target_time = self.config.get("dispatch_time", "18:00")

                    if current_time == target_time and self.config.get("last_run_date") != today_date:
                        print(f"[INFO] Triggering automated daily attendance report dispatch for {today_date}...")
                        self.trigger_dispatch()

            except Exception as e:
                print(f"[WARN] Scheduler loop error: {e}")

            time.sleep(30)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("[INFO] Attendance Report Scheduler started in background.")

if __name__ == "__main__":
    scheduler = AttendanceReportScheduler()
    print("[INFO] Scheduler initialized. Config:", scheduler.config)
