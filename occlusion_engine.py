import cv2
import numpy as np

class OcclusionDetector:
    """Facial mask, sunglasses, and multi-region occlusion detection engine with fallback guidance."""

    @staticmethod
    def detect_occlusion(frame: np.ndarray, bbox: list, kps: list = None) -> dict:
        """Analyze face crop for upper-face (sunglasses) and lower-face (mask/scarf) occlusion."""
        if frame is None or len(bbox) < 4:
            return {
                "is_occluded": False,
                "is_masked": False,
                "has_sunglasses": False,
                "occlusion_score": 0.0,
                "occlusion_type": "none",
                "requires_manual_checkin": False,
                "details": "Invalid ROI"
            }

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_frame, w_frame = frame.shape[:2]

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_frame, x2), min(h_frame, y2)

        box_w = x2 - x1
        box_h = y2 - y1

        if box_w < 20 or box_h < 20:
            return {
                "is_occluded": False,
                "is_masked": False,
                "has_sunglasses": False,
                "occlusion_score": 0.0,
                "occlusion_type": "none",
                "requires_manual_checkin": False,
                "details": "ROI too small"
            }

        # 1. Lower Face Crop (Mask / Scarf: bottom 45% of face)
        lower_y1 = int(y1 + box_h * 0.55)
        lower_crop = frame[lower_y1:y2, x1:x2]

        # 2. Upper Face Crop (Sunglasses / Eyes region: top 18%-50% of face)
        upper_y1 = int(y1 + box_h * 0.18)
        upper_y2 = int(y1 + box_h * 0.50)
        upper_crop = frame[upper_y1:upper_y2, x1:x2]

        is_masked = False
        has_sunglasses = False
        occlusion_score = 0.0

        # --- Lower-face Mask Analysis ---
        if lower_crop.size > 0:
            gray_lower = cv2.cvtColor(lower_crop, cv2.COLOR_BGR2GRAY)
            lap_var_lower = cv2.Laplacian(gray_lower, cv2.CV_64F).var()
            hsv_lower = cv2.cvtColor(lower_crop, cv2.COLOR_BGR2HSV)
            s_std_lower = np.std(hsv_lower[:, :, 1])

            if lap_var_lower < 85 and s_std_lower < 42:
                is_masked = True
                occlusion_score += 45.0

        # --- Upper-face Sunglasses Analysis ---
        if upper_crop.size > 0:
            gray_upper = cv2.cvtColor(upper_crop, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray_upper)
            hsv_upper = cv2.cvtColor(upper_crop, cv2.COLOR_BGR2HSV)
            v_val_upper = hsv_upper[:, :, 2]
            v_std_upper = np.std(v_val_upper)

            # Dark, uniform eye region indicates dark sunglasses
            if avg_brightness < 55 and v_std_upper < 30:
                has_sunglasses = True
                occlusion_score += 45.0

        is_occluded = is_masked or has_sunglasses
        occlusion_type = "none"
        if is_masked and has_sunglasses:
            occlusion_type = "heavy_mask_and_sunglasses"
        elif is_masked:
            occlusion_type = "mask"
        elif has_sunglasses:
            occlusion_type = "sunglasses"

        requires_manual_checkin = bool(is_masked and has_sunglasses)

        details = "Clear Face"
        if occlusion_type == "heavy_mask_and_sunglasses":
            details = "Heavy Occlusion (Mask + Glasses)"
        elif occlusion_type == "mask":
            details = "Mask Detected"
        elif occlusion_type == "sunglasses":
            details = "Sunglasses Detected"

        return {
            "is_occluded": is_occluded,
            "is_masked": is_masked,
            "has_sunglasses": has_sunglasses,
            "occlusion_score": round(min(100.0, occlusion_score), 1),
            "occlusion_type": occlusion_type,
            "requires_manual_checkin": requires_manual_checkin,
            "details": details
        }

    @staticmethod
    def detect_mask(frame: np.ndarray, bbox: list, kps: list = None) -> dict:
        """Backwards compatibility wrapper for detect_mask."""
        return OcclusionDetector.detect_occlusion(frame, bbox, kps)

if __name__ == "__main__":
    print("[INFO] Multi-Region Occlusion Detector Engine Initialized.")
