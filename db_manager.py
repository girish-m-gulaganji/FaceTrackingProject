import sqlite3
import os
from datetime import datetime

DB_PATH = "visiontrack.db"

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database schema if not exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Enrolled Persons Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    department TEXT DEFAULT 'General',
                    role TEXT DEFAULT 'Member',
                    vector_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Attendance History Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_name TEXT NOT NULL,
                    status TEXT DEFAULT 'Present',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    video_time TEXT,
                    frame_number INTEGER,
                    source_file TEXT,
                    confidence REAL DEFAULT 1.0
                )
            """)

            # 3. Audit Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    # --- Person Management ---
    def upsert_person(self, name: str, department: str = 'General', role: str = 'Member', vector_count: int = 1):
        """Insert or update person record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO persons (name, department, role, vector_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    vector_count = excluded.vector_count,
                    department = COALESCE(NULLIF(excluded.department, 'General'), persons.department),
                    role = COALESCE(NULLIF(excluded.role, 'Member'), persons.role)
            """, (name, department, role, vector_count))
            conn.commit()

    def get_all_persons(self):
        """Retrieve all enrolled persons."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM persons ORDER BY name ASC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_person(self, name: str):
        """Delete person record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM persons WHERE name = ?", (name,))
            conn.commit()

    # --- Attendance Logging ---
    def log_attendance(self, person_name: str, status: str = 'Present', timestamp: str = None, video_time: str = None, frame_number: int = None, source_file: str = None, confidence: float = 1.0):
        """Record attendance entry into SQLite database."""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attendance_logs (person_name, status, timestamp, video_time, frame_number, source_file, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (person_name, status, timestamp, video_time, frame_number, source_file, confidence))
            conn.commit()

    def get_attendance_logs(self, limit: int = 100, person_name: str = None):
        """Retrieve attendance records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if person_name:
                cursor.execute("SELECT * FROM attendance_logs WHERE person_name = ? ORDER BY id DESC LIMIT ?", (person_name, limit))
            else:
                cursor.execute("SELECT * FROM attendance_logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_summary_stats(self):
        """Retrieve summary analytics from database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT name) as total_persons FROM persons")
            total_persons = cursor.fetchone()["total_persons"]

            cursor.execute("SELECT COUNT(*) as total_attendance FROM attendance_logs")
            total_attendance = cursor.fetchone()["total_attendance"]

            cursor.execute("SELECT COUNT(DISTINCT person_name) as today_present FROM attendance_logs WHERE DATE(timestamp) = DATE('now')")
            today_present = cursor.fetchone()["today_present"]

            return {
                "total_persons": total_persons,
                "total_attendance": total_attendance,
                "today_present": today_present
            }

    def get_daily_attendance_trend(self, days: int = 7):
        """Retrieve daily attendance count for the last N days."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DATE(timestamp) as date, COUNT(DISTINCT person_name) as count
                FROM attendance_logs
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT ?
            """, (days,))
            rows = cursor.fetchall()
            return [{"date": row["date"], "count": row["count"]} for row in reversed(rows)]

    def get_department_breakdown(self):
        """Retrieve count of present persons grouped by department."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(p.department, 'General') as department, COUNT(DISTINCT a.person_name) as count
                FROM attendance_logs a
                LEFT JOIN persons p ON a.person_name = p.name
                GROUP BY department
            """);
            rows = cursor.fetchall()
            return [{"department": row["department"], "count": row["count"]} for row in rows]

    # --- Audit Logging ---
    def log_audit(self, action: str, details: str = None):
        """Log system audit event."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO audit_logs (action, details) VALUES (?, ?)", (action, details))
            conn.commit()

if __name__ == "__main__":
    db = DatabaseManager()
    db.upsert_person("Girish", "AI Engineering", "Lead Developer", 6)
    print("[INFO] Database Initialized & Seeded successfully!")
    print("[INFO] Persons in DB:", db.get_all_persons())
    print("[INFO] Stats:", db.get_summary_stats())
