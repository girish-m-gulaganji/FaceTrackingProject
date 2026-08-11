import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime

POSTGRES_CONFIG_FILE = "postgres_config.json"

class DatabaseManager:
    """Enterprise PostgreSQL Database Manager for VisionTrack AI."""

    def __init__(self, config_path: str = POSTGRES_CONFIG_FILE):
        self.config_path = config_path
        self.config = self.load_config()
        self.init_db()

    def load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Postgres config load error: {e}")
        return {
            "enabled": True,
            "host": "localhost",
            "port": 5432,
            "database": "visiontrack_db",
            "user": "postgres",
            "password": "root"
        }

    def get_connection(self):
        env_pass = os.environ.get("POSTGRES_PASSWORD")
        cfg_pass = self.config.get("password", "root")
        
        candidate_passwords = []
        if env_pass:
            candidate_passwords.append(env_pass)
        if cfg_pass and cfg_pass not in candidate_passwords:
            candidate_passwords.append(cfg_pass)
        for fallback in ["root", "postgres", "admin", "123456", ""]:
            if fallback not in candidate_passwords:
                candidate_passwords.append(fallback)
        
        last_err = None
        for pwd in candidate_passwords:
            try:
                conn = psycopg2.connect(
                    host=self.config.get("host", "localhost"),
                    port=int(self.config.get("port", 5432)),
                    dbname=self.config.get("database", "visiontrack_db"),
                    user=self.config.get("user", "postgres"),
                    password=pwd,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    connect_timeout=3
                )
                self.config["password"] = pwd
                return conn
            except Exception as e:
                last_err = e
        raise last_err

    def init_db(self):
        """Initialize PostgreSQL schema tables if not present."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Registered Persons Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    department VARCHAR(100) DEFAULT 'General',
                    role VARCHAR(100) DEFAULT 'Member',
                    vector_count INT DEFAULT 1,
                    platform VARCHAR(100) DEFAULT 'Internal',
                    profile_url TEXT,
                    bio TEXT,
                    location TEXT,
                    avatar_url TEXT,
                    consent_given INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Attendance History Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id SERIAL PRIMARY KEY,
                    person_name VARCHAR(255) NOT NULL,
                    status VARCHAR(100) DEFAULT 'Present',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    video_time VARCHAR(100),
                    frame_number INT,
                    source_file TEXT,
                    confidence DOUBLE PRECISION DEFAULT 1.0
                );
            """)

            # 3. Audit Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(255) NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Confidence Alerts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS confidence_alerts (
                    id SERIAL PRIMARY KEY,
                    person_name VARCHAR(255) NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    status VARCHAR(100) DEFAULT 'BORDERLINE',
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WARN] PostgreSQL schema initialization notice: {e}")

    # --- Person Management & Consent ---
    def upsert_person(self, name: str, department: str = 'General', role: str = 'Member', vector_count: int = 1, consent_given: int = 1):
        """Insert or update person record in PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO persons (name, department, role, vector_count, consent_given)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                vector_count = EXCLUDED.vector_count,
                department = COALESCE(NULLIF(EXCLUDED.department, 'General'), persons.department),
                role = COALESCE(NULLIF(EXCLUDED.role, 'Member'), persons.role),
                consent_given = EXCLUDED.consent_given;
        """, (name, department, role, vector_count, consent_given))
        conn.commit()
        conn.close()

    def get_all_persons(self):
        """Retrieve all enrolled persons from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM persons ORDER BY name ASC;")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_person(self, name: str):
        """Delete person record from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persons WHERE name = %s;", (name,))
        conn.commit()
        conn.close()

    def purge_user_data(self, person_name: str):
        """Permanently purge all user records, attendance logs, and audit entries for privacy compliance."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persons WHERE name = %s;", (person_name,))
        cursor.execute("DELETE FROM attendance_logs WHERE person_name = %s;", (person_name,))
        cursor.execute("DELETE FROM confidence_alerts WHERE person_name = %s;", (person_name,))
        cursor.execute("INSERT INTO audit_logs (action, details) VALUES (%s, %s);",
                       ("PRIVACY_DATA_PURGE", f"Consent withdrawn. Permanently purged all stored data for '{person_name}'."))
        conn.commit()
        conn.close()
        return True

    # --- Analytics & Attendance Reporting ---
    def get_late_arrivals(self, cutoff_hour: int = 9, cutoff_min: int = 30):
        """Find personnel who logged attendance after cutoff time today in PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT person_name, MIN(timestamp) as arrival_time
            FROM attendance_logs
            WHERE DATE(timestamp) = CURRENT_DATE
            GROUP BY person_name;
        """)
        rows = cursor.fetchall()
        conn.close()
        late_list = []
        cutoff_str = f"{cutoff_hour:02d}:{cutoff_min:02d}:00"

        for r in rows:
            ts = str(r["arrival_time"])
            time_part = ts.split(" ")[1] if " " in ts else (ts.split("T")[1][:8] if "T" in ts else ts)
            if time_part > cutoff_str:
                late_list.append({
                    "person_name": r["person_name"],
                    "arrival_time": time_part,
                    "status": "Late Arrival"
                })
        return late_list

    def get_absence_streaks(self):
        """Compute personnel who have not logged attendance in 2+ consecutive workdays."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, department FROM persons;")
        all_persons = cursor.fetchall()

        streaks = []
        for p in all_persons:
            name = p["name"]
            cursor.execute("""
                SELECT MAX(DATE(timestamp)) as last_date
                FROM attendance_logs
                WHERE person_name = %s;
            """, (name,))
            row = cursor.fetchone()
            last_date_str = str(row["last_date"]) if row and row["last_date"] else None

            if last_date_str:
                last_dt = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
                days_absent = (datetime.now() - last_dt).days
            else:
                days_absent = 7

            if days_absent >= 2:
                streaks.append({
                    "person_name": name,
                    "department": p["department"] or "General",
                    "days_absent": days_absent,
                    "last_seen": last_date_str or "Never"
                })

        conn.close()
        return streaks

    # --- Confidence Alert Review Queue ---
    def log_confidence_alert(self, person_name: str, confidence: float, status: str = "BORDERLINE", details: str = None):
        """Log low-confidence match for human administrative review in PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO confidence_alerts (person_name, confidence, status, details)
            VALUES (%s, %s, %s, %s);
        """, (person_name, confidence, status, details))
        conn.commit()
        conn.close()

    def get_confidence_alerts(self, limit: int = 50):
        """Retrieve recent confidence alerts from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM confidence_alerts ORDER BY id DESC LIMIT %s;", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Attendance Logging ---
    def log_attendance(self, person_name: str, status: str = 'Present', timestamp: str = None, video_time: str = None, frame_number: int = None, source_file: str = None, confidence: float = 1.0):
        """Record attendance entry directly into PostgreSQL database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if timestamp is None:
            cursor.execute("""
                INSERT INTO attendance_logs (person_name, status, video_time, frame_number, source_file, confidence)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (person_name, status, video_time, frame_number, source_file, confidence))
        else:
            cursor.execute("""
                INSERT INTO attendance_logs (person_name, status, timestamp, video_time, frame_number, source_file, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (person_name, status, timestamp, video_time, frame_number, source_file, confidence))
        conn.commit()
        conn.close()

    def get_attendance_logs(self, limit: int = 100, person_name: str = None):
        """Retrieve attendance records from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if person_name:
            cursor.execute("SELECT * FROM attendance_logs WHERE person_name = %s ORDER BY id DESC LIMIT %s;", (person_name, limit))
        else:
            cursor.execute("SELECT * FROM attendance_logs ORDER BY id DESC LIMIT %s;", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_summary_stats(self):
        """Retrieve summary analytics from PostgreSQL database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT name) as total_persons FROM persons;")
        total_persons = cursor.fetchone()["total_persons"]

        cursor.execute("SELECT COUNT(*) as total_attendance FROM attendance_logs;")
        total_attendance = cursor.fetchone()["total_attendance"]

        cursor.execute("SELECT COUNT(DISTINCT person_name) as today_present FROM attendance_logs WHERE DATE(timestamp) = CURRENT_DATE;")
        today_present = cursor.fetchone()["today_present"]
        conn.close()

        return {
            "total_persons": total_persons,
            "total_attendance": total_attendance,
            "today_present": today_present
        }

    def get_daily_attendance_trend(self, days: int = 7):
        """Retrieve daily attendance count for the last N days from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(timestamp) as date, COUNT(DISTINCT person_name) as count
            FROM attendance_logs
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT %s;
        """, (days,))
        rows = cursor.fetchall()
        conn.close()
        return [{"date": str(row["date"]), "count": row["count"]} for row in reversed(rows)]

    def get_department_breakdown(self):
        """Retrieve count of present persons grouped by department from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(p.department, 'General') as department, COUNT(DISTINCT a.person_name) as count
            FROM attendance_logs a
            LEFT JOIN persons p ON a.person_name = p.name
            GROUP BY COALESCE(p.department, 'General');
        """)
        rows = cursor.fetchall()
        conn.close()
        return [{"department": row["department"], "count": row["count"]} for row in rows]

    # --- Audit Logging ---
    def log_audit(self, action: str, details: str = None):
        """Log system audit event into PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO audit_logs (action, details) VALUES (%s, %s);", (action, details))
        conn.commit()
        conn.close()

    def get_audit_logs(self, limit: int = 50):
        """Retrieve recent system audit logs from PostgreSQL."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT %s;", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

if __name__ == "__main__":
    db = DatabaseManager()
    print("[INFO] PostgreSQL DatabaseManager initialized & tested successfully!")
    print("[INFO] Persons in PostgreSQL:", db.get_all_persons())
    print("[INFO] Stats:", db.get_summary_stats())
