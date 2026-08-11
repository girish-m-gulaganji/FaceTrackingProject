import os
import json
import sqlite3
from datetime import datetime

POSTGRES_CONFIG_FILE = "postgres_config.json"
SQLITE_DB_PATH = "visiontrack.db"

class PostgresManager:
    """PostgreSQL Manager & Migration Engine for VisionTrack AI."""

    def __init__(self, config_path=POSTGRES_CONFIG_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Postgres config load error: {e}")
        return {
            "enabled": False,
            "host": "localhost",
            "port": 5432,
            "database": "visiontrack_db",
            "user": "postgres",
            "password": ""
        }

    def save_config(self, new_config: dict) -> dict:
        self.config.update(new_config)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
        return self.config

    def test_connection(self, config: dict = None) -> tuple[bool, str]:
        """Test connection to PostgreSQL server."""
        cfg = config or self.config
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=cfg.get("host", "localhost"),
                port=int(cfg.get("port", 5432)),
                dbname=cfg.get("database", "visiontrack_db"),
                user=cfg.get("user", "postgres"),
                password=cfg.get("password", ""),
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            ver = cursor.fetchone()[0]
            conn.close()
            return True, f"Successfully connected to PostgreSQL! Version: {ver.split(',')[0]}"
        except ImportError:
            return False, "psycopg2 library not installed. Install via: pip install psycopg2-binary"
        except Exception as e:
            return False, f"PostgreSQL Connection Failed: {str(e)}"

    def init_postgres_schema(self, config: dict = None) -> tuple[bool, str]:
        """Initialize PostgreSQL tables if not present."""
        cfg = config or self.config
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=cfg.get("host", "localhost"),
                port=int(cfg.get("port", 5432)),
                dbname=cfg.get("database", "visiontrack_db"),
                user=cfg.get("user", "postgres"),
                password=cfg.get("password", "")
            )
            cursor = conn.cursor()

            # 1. Persons Table
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

            # 2. Attendance Logs Table
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

            # 5. Performance Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance_logs (timestamp DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_person ON attendance_logs (person_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_confidence_status ON confidence_alerts (status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs (timestamp DESC);")

            conn.commit()
            conn.close()
            return True, "PostgreSQL schema initialized successfully."
        except Exception as e:
            return False, f"Schema initialization failed: {str(e)}"

    def migrate_from_sqlite(self, sqlite_path: str = SQLITE_DB_PATH) -> tuple[bool, str]:
        """Migrate all records from local SQLite (visiontrack.db) to PostgreSQL."""
        if not os.path.exists(sqlite_path):
            return False, f"SQLite database '{sqlite_path}' not found."

        init_ok, init_msg = self.init_postgres_schema()
        if not init_ok:
            return False, init_msg

        try:
            import psycopg2
            pg_conn = psycopg2.connect(
                host=self.config.get("host", "localhost"),
                port=int(self.config.get("port", 5432)),
                dbname=self.config.get("database", "visiontrack_db"),
                user=self.config.get("user", "postgres"),
                password=self.config.get("password", "")
            )
            pg_cursor = pg_conn.cursor()

            sq_conn = sqlite3.connect(sqlite_path)
            sq_conn.row_factory = sqlite3.Row
            sq_cursor = sq_conn.cursor()

            # 1. Migrate Persons
            sq_cursor.execute("SELECT * FROM persons")
            persons = sq_cursor.fetchall()
            person_migrated = 0
            for p in persons:
                p_dict = dict(p)
                pg_cursor.execute("""
                    INSERT INTO persons (name, department, role, vector_count, platform, profile_url, bio, location, avatar_url, consent_given)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(name) DO UPDATE SET
                        vector_count = EXCLUDED.vector_count,
                        department = COALESCE(NULLIF(EXCLUDED.department, 'General'), persons.department),
                        role = COALESCE(NULLIF(EXCLUDED.role, 'Member'), persons.role),
                        consent_given = EXCLUDED.consent_given;
                """, (
                    p_dict.get("name"),
                    p_dict.get("department", "General"),
                    p_dict.get("role", "Member"),
                    p_dict.get("vector_count", 1),
                    p_dict.get("platform", "Internal"),
                    p_dict.get("profile_url", ""),
                    p_dict.get("bio", ""),
                    p_dict.get("location", ""),
                    p_dict.get("avatar_url", ""),
                    p_dict.get("consent_given", 1)
                ))
                person_migrated += 1

            # 2. Migrate Attendance Logs
            sq_cursor.execute("SELECT * FROM attendance_logs")
            logs = sq_cursor.fetchall()
            logs_migrated = 0
            for l in logs:
                l_dict = dict(l)
                ts_val = str(l_dict["timestamp"]) if l_dict.get("timestamp") else None
                pg_cursor.execute("""
                    INSERT INTO attendance_logs (person_name, status, timestamp, video_time, frame_number, source_file, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (
                    l_dict.get("person_name"),
                    l_dict.get("status", "Present"),
                    ts_val,
                    l_dict.get("video_time"),
                    l_dict.get("frame_number"),
                    l_dict.get("source_file"),
                    l_dict.get("confidence", 1.0)
                ))
                logs_migrated += 1

            # 3. Migrate Audit Logs
            sq_cursor.execute("SELECT * FROM audit_logs")
            audits = sq_cursor.fetchall()
            audits_migrated = 0
            for a in audits:
                a_dict = dict(a)
                ts_val = str(a_dict["timestamp"]) if a_dict.get("timestamp") else None
                pg_cursor.execute("""
                    INSERT INTO audit_logs (action, details, timestamp)
                    VALUES (%s, %s, %s);
                """, (
                    a_dict.get("action"),
                    a_dict.get("details"),
                    ts_val
                ))
                audits_migrated += 1

            # 4. Migrate Confidence Alerts Queue (if exists)
            sq_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='confidence_alerts'")
            alerts_migrated = 0
            if sq_cursor.fetchone():
                sq_cursor.execute("SELECT * FROM confidence_alerts")
                alerts = sq_cursor.fetchall()
                for ca in alerts:
                    ca_dict = dict(ca)
                    ts_val = str(ca_dict["timestamp"]) if ca_dict.get("timestamp") else None
                    pg_cursor.execute("""
                        INSERT INTO confidence_alerts (person_name, confidence, status, details, timestamp)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (
                        ca_dict.get("person_name"),
                        ca_dict.get("confidence", 0.5),
                        ca_dict.get("status", "BORDERLINE"),
                        ca_dict.get("details"),
                        ts_val
                    ))
                    alerts_migrated += 1

            pg_conn.commit()
            pg_conn.close()
            sq_conn.close()

            return True, f"Successfully migrated {person_migrated} persons, {logs_migrated} attendance logs, {alerts_migrated} confidence alerts, and {audits_migrated} audit logs from SQLite to PostgreSQL!"

        except Exception as e:
            return False, f"Migration error: {str(e)}"

if __name__ == "__main__":
    pm = PostgresManager()
    print("[INFO] Postgres Manager initialized. Config:", pm.config)
