import cv2
import numpy as np

class LivenessDetector:
    """Texture frequency and Laplacian variance anti-spoofing detector."""

    def __init__(self, laplacian_threshold: float = 85.0):
        self.laplacian_threshold = laplacian_threshold

    def check_liveness(self, frame: np.ndarray, bbox: list):
        """Evaluate if cropped face is a real live 3D face or a spoof paper/screen attack."""
        if frame is None or len(bbox) < 4:
            return {"is_real": True, "score": 100.0, "status": "Real Face"}

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if (x2 - x1) < 20 or (y2 - y1) < 20:
            return {"is_real": True, "score": 90.0, "status": "Real Face"}

        face_crop = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

        # 1. Laplacian Variance (High-frequency texture detail measure)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 2. Color Distribution Check (HSV Saturation Variance)
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        sat_std = float(np.std(hsv[:, :, 1]))

        # Combine metrics into liveness confidence score
        score = min(100.0, (lap_var / self.laplacian_threshold) * 85.0 + (sat_std / 50.0) * 15.0)
        is_real = lap_var >= self.laplacian_threshold and sat_std > 8.0

        return {
            "is_real": is_real,
            "score": round(score, 1),
            "laplacian_var": round(lap_var, 2),
            "status": "Real Face" if is_real else "Spoof / Screen Attack"
        }

if __name__ == "__main__":
    detector = LivenessDetector()
    print("[INFO] Anti-Spoofing Liveness Engine Initialized.")
