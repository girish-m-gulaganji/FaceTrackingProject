import cv2
import numpy as np

class FaceAugmenter:
    """Synthetic face data augmenter for multi-embedding registration from single photos."""

    @staticmethod
    def generate_augmentations(img_bgr: np.ndarray, face_bbox: list = None):
        """Generate 3 synthetic image variations (Original, Flip+Lighting, Mask Overlay)."""
        if img_bgr is None:
            return []

        augmented = []

        # 1. Original Image
        augmented.append(img_bgr.copy())

        # 2. Horizontal Flip + Mild Contrast Enhancement
        flipped = cv2.flip(img_bgr, 1)
        brightness_adjusted = cv2.convertScaleAbs(flipped, alpha=1.1, beta=5)
        augmented.append(brightness_adjusted)

        # 3. Synthetic Lower-Face Mask Overlay
        masked_img = img_bgr.copy()
        h, w = masked_img.shape[:2]

        if face_bbox is not None and len(face_bbox) >= 4:
            fx1, fy1, fx2, fy2 = [int(v) for v in face_bbox]
            mask_top = int(fy1 + (fy2 - fy1) * 0.55)
            mask_bottom = min(h, fy2 + 5)
            mask_left = max(0, fx1 - 5)
            mask_right = min(w, fx2 + 5)
        else:
            mask_top = int(h * 0.55)
            mask_bottom = h
            mask_left = int(w * 0.2)
            mask_right = int(w * 0.8)

        # Draw a synthetic dark medical mask polygon
        pts = np.array([
            [mask_left, mask_top],
            [mask_right, mask_top],
            [int(mask_right - (mask_right - mask_left) * 0.1), mask_bottom],
            [int(mask_left + (mask_right - mask_left) * 0.1), mask_bottom]
        ], np.int32)

        cv2.fillPoly(masked_img, [pts], (60, 60, 60))
        cv2.polylines(masked_img, [pts], True, (120, 120, 120), 2)
        augmented.append(masked_img)

        return augmented

if __name__ == "__main__":
    print("[INFO] Face Augmenter Module Initialized.")
