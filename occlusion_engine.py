import cv2
import numpy as np

class OcclusionDetector:
    """Facial mask and lower-face occlusion detection engine."""

    @staticmethod
    def detect_mask(frame: np.ndarray, bbox: list, kps: list = None) -> dict:
        """Analyze face crop for lower-face mask overlay."""
        if frame is None or len(bbox) < 4:
            return {"is_masked": False, "occlusion_score": 0.0, "details": "Invalid ROI"}

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 - x1 < 20 or y2 - y1 < 20:
            return {"is_masked": False, "occlusion_score": 0.0, "details": "ROI too small"}

        # Crop lower 45% of face bounding box
        lower_y1 = int(y1 + (y2 - y1) * 0.55)
        lower_crop = frame[lower_y1:y2, x1:x2]

        if lower_crop.size == 0:
            return {"is_masked": False, "occlusion_score": 0.0, "details": "Empty crop"}

        # 1. Texture Uniformity Analysis (Masks have low texture variance compared to lips/teeth)
        gray = cv2.cvtColor(lower_crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 2. Color Uniformity (Masks have consistent color in HSV)
        hsv = cv2.cvtColor(lower_crop, cv2.COLOR_BGR2HSV)
        h_std = np.std(hsv[:, :, 0])
        s_std = np.std(hsv[:, :, 1])

        # Mask heuristic: low Laplacian variance + low HSV std dev
        is_masked = bool(laplacian_var < 80 and s_std < 40)
        occlusion_score = round(float(max(0.0, min(100.0, (1.0 - (laplacian_var / 200.0)) * 100))), 1)

        return {
            "is_masked": is_masked,
            "occlusion_score": occlusion_score,
            "details": "Mask Detected" if is_masked else "Clear Face"
        }

if __name__ == "__main__":
    print("[INFO] Occlusion Detector Engine Initialized.")
