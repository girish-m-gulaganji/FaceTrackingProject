import os
import cv2
import numpy as np
from face_tracker_engine import FaceDatabase, load_insightface_app

def scan_and_enroll():
    print("[INFO] Loading InsightFace AI Engine...")
    app, ctx_id = load_insightface_app()
    db = FaceDatabase()

    image_dir = "dataset/images"
    supported_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    files = sorted([f for f in os.listdir(image_dir) if os.path.splitext(f)[1].lower() in supported_ext])

    print(f"\n[INFO] Found {len(files)} image(s) in '{image_dir}':")
    enrolled_count = 0

    for file in files:
        raw_name = os.path.splitext(file)[0]
        # Strip trailing numbers like _1, _2
        parts = raw_name.rsplit("_", 1)
        name = parts[0] if len(parts) == 2 and parts[1].isdigit() else raw_name

        img_path = os.path.join(image_dir, file)
        img_bgr = cv2.imread(img_path)

        if img_bgr is None:
            print(f"  [ERROR] Cannot read: {file}")
            continue

        success, msg = db.enroll_from_image_array(img_bgr, name, app)
        if success:
            print(f"  [OK] {name:<20s} (from {file})")
            enrolled_count += 1
        else:
            print(f"  [WARN] {name:<20s} ({msg})")

    print("\n" + "="*50)
    print(f"[INFO] Enrolled {enrolled_count} photo(s). Total database size: {len(db.embeddings)} vector(s)")
    print(f"[INFO] Persons in DB: {', '.join(np.unique(db.names))}")
    print("="*50)

if __name__ == "__main__":
    scan_and_enroll()
