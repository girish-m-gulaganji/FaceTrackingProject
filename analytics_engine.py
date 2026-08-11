from db_manager import DatabaseManager

class AnalyticsEngine:
    """Peak traffic hours and punctuality analytics calculator for PostgreSQL."""

    def __init__(self):
        self.db = DatabaseManager()

    def get_peak_hours_and_punctuality(self, cutoff_hour: int = 9, cutoff_min: int = 30):
        """Calculate peak arrival hours and punctuality percentage in PostgreSQL."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 1. Hourly Distribution Breakdown
        cursor.execute("""
            SELECT TO_CHAR(timestamp, 'HH24') as hour, COUNT(*) as count
            FROM attendance_logs
            WHERE timestamp IS NOT NULL
            GROUP BY hour
            ORDER BY count DESC;
        """)
        hourly_rows = cursor.fetchall()

        peak_hour = "N/A"
        if hourly_rows and hourly_rows[0]["hour"]:
            top_h = int(hourly_rows[0]["hour"])
            peak_hour = f"{top_h:02d}:00 - {top_h+1:02d}:00"

        hourly_distribution = [
            {"hour": f"{int(r['hour']):02d}:00", "count": r["count"]}
            for r in hourly_rows if r["hour"] is not None
        ]

        # 2. Punctuality Ratio Calculation
        cursor.execute("SELECT timestamp FROM attendance_logs WHERE timestamp IS NOT NULL;")
        all_logs = cursor.fetchall()
        conn.close()

        total = len(all_logs)
        on_time = 0

        for row in all_logs:
            try:
                ts_str = str(row["timestamp"])
                if " " in ts_str:
                    time_part = ts_str.split(" ")[1]
                elif "T" in ts_str:
                    time_part = ts_str.split("T")[1]
                else:
                    time_part = ts_str

                h, m = int(time_part[:2]), int(time_part[3:5])

                if h < cutoff_hour or (h == cutoff_hour and m <= cutoff_min):
                    on_time += 1
            except Exception:
                on_time += 1

        punctuality_pct = round((on_time / total * 100), 1) if total > 0 else 100.0

        late_arrivals = self.db.get_late_arrivals(cutoff_hour=cutoff_hour, cutoff_min=cutoff_min)
        absence_streaks = self.db.get_absence_streaks()

        return {
            "peak_hour": peak_hour,
            "punctuality_pct": punctuality_pct,
            "on_time_count": on_time,
            "late_count": len(late_arrivals),
            "total_logs": total,
            "hourly_distribution": hourly_distribution,
            "late_arrivals": late_arrivals,
            "absence_streaks": absence_streaks
        }

if __name__ == "__main__":
    analytics = AnalyticsEngine()
    print("[INFO] Analytics Engine Initialized. Metrics:", analytics.get_peak_hours_and_punctuality())
