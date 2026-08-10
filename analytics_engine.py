from db_manager import DatabaseManager

class AnalyticsEngine:
    """Peak traffic hours and punctuality analytics calculator."""

    def __init__(self):
        self.db = DatabaseManager()

    def get_peak_hours_and_punctuality(self, cutoff_hour: int = 9, cutoff_min: int = 30):
        """Calculate peak arrival hours and punctuality percentage."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Hourly Distribution Breakdown
            cursor.execute("""
                SELECT STRFTIME('%H', timestamp) as hour, COUNT(*) as count
                FROM attendance_logs
                GROUP BY hour
                ORDER BY count DESC
            """)
            hourly_rows = cursor.fetchall()

            peak_hour = "N/A"
            if hourly_rows:
                top_h = int(hourly_rows[0]["hour"])
                peak_hour = f"{top_h:02d}:00 - {top_h+1:02d}:00"

            hourly_distribution = [{"hour": f"{int(r['hour']):02d}:00", "count": r["count"]} for r in hourly_rows]

            # 2. Punctuality Ratio Calculation
            cursor.execute("""
                SELECT timestamp FROM attendance_logs
            """)
            all_logs = cursor.fetchall()

            total = len(all_logs)
            on_time = 0

            for row in all_logs:
                try:
                    ts_str = row["timestamp"]
                    # Handle ISO format
                    if "T" in ts_str:
                        h, m = int(ts_str.split("T")[1][:2]), int(ts_str.split("T")[1][3:5])
                    else:
                        h, m = int(ts_str.split(" ")[1][:2]), int(ts_str.split(" ")[1][3:5])

                    if h < cutoff_hour or (h == cutoff_hour and m <= cutoff_min):
                        on_time += 1
                except Exception:
                    on_time += 1

            punctuality_pct = round((on_time / total * 100), 1) if total > 0 else 100.0

            return {
                "peak_hour": peak_hour,
                "punctuality_pct": punctuality_pct,
                "on_time_count": on_time,
                "late_count": max(0, total - on_time),
                "total_logs": total,
                "hourly_distribution": hourly_distribution
            }

if __name__ == "__main__":
    analytics = AnalyticsEngine()
    print("[INFO] Analytics Engine Initialized. Metrics:", analytics.get_peak_hours_and_punctuality())
