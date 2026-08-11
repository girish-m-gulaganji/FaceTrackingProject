import os
import sys
import time
import csv
import threading
from datetime import datetime
from collections import deque
import cv2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from insightface.app import FaceAnalysis

def get_execution_context():
    """Detect GPU availability and return ctx_id (0=GPU, -1=CPU)."""
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            return 0
    except Exception:
        pass
    return -1

def load_insightface_app(det_size=(640, 640)):
    """Initialize InsightFace FaceAnalysis engine."""
    ctx_id = get_execution_context()
    provider = "CUDAExecutionProvider" if ctx_id == 0 else "CPUExecutionProvider"
    app = FaceAnalysis(name="buffalo_l", providers=[provider])
    app.prepare(ctx_id=ctx_id, det_size=det_size)
    return app, ctx_id

def draw_fancy_label(frame, text, x, y, color, font_scale=0.65, thickness=2):
    """Draw a styled text label with a filled background rectangle."""
    # Replace unicode emoji symbols with clean ASCII labels for OpenCV compatibility
    display_text = text.replace("⚠️", "[!]").replace("😷", "[Mask]").replace("🕶️", "[Glasses]")
    display_text = "".join([c for c in display_text if ord(c) < 128]).strip()

    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(display_text, font, font_scale, thickness)
    pad = 6
    y_top = max(y - th - 2 * pad, 0)

    cv2.rectangle(
        frame,
        (x, y_top),
        (x + tw + 2 * pad, y_top + th + 2 * pad + baseline),
        color, -1
    )
    brightness = (color[0] * 0.114 + color[1] * 0.587 + color[2] * 0.299)
    txt_clr = (0, 0, 0) if brightness > 127 else (255, 255, 255)

    cv2.putText(
        frame, display_text,
        (x + pad, y_top + th + pad),
        font, font_scale, txt_clr, thickness, cv2.LINE_AA
    )

def extract_face_attributes(face, frame_shape=None):
    """Extract age, gender, and occlusion metrics from InsightFace Face object."""
    age = int(getattr(face, "age", 25))
    gender_val = getattr(face, "gender", 1)
    gender = "Male" if gender_val == 1 or gender_val > 0.5 else "Female"

    # Occlusion / Mask Check using bounding box & landmark statistics
    is_occluded = False
    bbox = getattr(face, "bbox", [0,0,0,0])
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    if w > 0 and h > 0:
        aspect_ratio = float(w) / float(h)
        if aspect_ratio < 0.65 or aspect_ratio > 1.35:
            is_occluded = True

    kps = getattr(face, "kps", None)
    if kps is not None and len(kps) >= 5:
        # Check distance between nose/mouth landmarks
        nose = kps[2]
        mouth_l = kps[3]
        mouth_r = kps[4]
        mouth_dist = np.linalg.norm(mouth_l - mouth_r)
        if mouth_dist < (w * 0.15):
            is_occluded = True

    return {
        "age": age,
        "gender": gender,
        "is_occluded": is_occluded
    }

class FaceDatabase:
    """Persistent face database with live enrollment and similarity matching."""

    def __init__(self, db_path="dataset/embeddings/embeddings.npz"):
        self.db_path = db_path
        self.embeddings = np.empty((0, 512), dtype=np.float32)
        self.names = np.array([], dtype=str)
        self.metadata = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            data = np.load(self.db_path, allow_pickle=True)
            self.embeddings = data["embeddings"]
            self.names = data["names"]
            if "metadata" in data and data["metadata"].ndim == 0:
                self.metadata = data["metadata"].item()

    def save(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        np.savez(
            self.db_path,
            embeddings=self.embeddings,
            names=self.names,
            metadata=self.metadata,
        )

    def enroll_from_image_array(self, img_bgr, person_name, app, augment: bool = True):
        """Enroll face from BGR image array with optional synthetic multi-vector data augmentation."""
        if img_bgr is None:
            return False, "Invalid image data."

        faces = app.get(img_bgr)
        if not faces:
            return False, "No face detected in the image."

        # Select largest face
        faces.sort(
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
            reverse=True,
        )

        main_face = faces[0]
        embeddings_to_add = [main_face.embedding.reshape(1, -1)]

        if augment:
            from face_augmentor import FaceAugmenter
            aug_images = FaceAugmenter.generate_augmentations(img_bgr, main_face.bbox)
            for aug_img in aug_images[1:]:  # Skip original
                aug_faces = app.get(aug_img)
                if aug_faces:
                    aug_faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
                    embeddings_to_add.append(aug_faces[0].embedding.reshape(1, -1))

        for emb in embeddings_to_add:
            if len(self.embeddings) > 0:
                self.embeddings = np.vstack([self.embeddings, emb])
                self.names = np.append(self.names, person_name)
            else:
                self.embeddings = emb
                self.names = np.array([person_name])

        self.metadata[person_name] = {
            "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_embeddings": int(np.sum(self.names == person_name)),
        }

        self.save()
        return True, f"Successfully enrolled '{person_name}' with {len(embeddings_to_add)} vector embeddings."

    def enroll_multi_angle(self, images_list, person_name, app, augment: bool = True):
        """Enroll person from multiple BGR images (3-5 multi-angle selfies)."""
        if not images_list or len(images_list) == 0:
            return False, "No image files provided."

        successful_photos = 0
        total_vectors_added = 0

        for img_bgr in images_list:
            if img_bgr is None:
                continue

            faces = app.get(img_bgr)
            if not faces:
                continue

            faces.sort(
                key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                reverse=True,
            )
            main_face = faces[0]
            embeddings_to_add = [main_face.embedding.reshape(1, -1)]

            if augment:
                from face_augmentor import FaceAugmenter
                aug_images = FaceAugmenter.generate_augmentations(img_bgr, main_face.bbox)
                for aug_img in aug_images[1:]:
                    aug_faces = app.get(aug_img)
                    if aug_faces:
                        aug_faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
                        embeddings_to_add.append(aug_faces[0].embedding.reshape(1, -1))

            for emb in embeddings_to_add:
                if len(self.embeddings) > 0:
                    self.embeddings = np.vstack([self.embeddings, emb])
                    self.names = np.append(self.names, person_name)
                else:
                    self.embeddings = emb
                    self.names = np.array([person_name])
                total_vectors_added += 1

            successful_photos += 1

        if successful_photos == 0:
            return False, "No faces detected in any of the uploaded multi-angle selfies."

        self.metadata[person_name] = {
            "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_embeddings": int(np.sum(self.names == person_name)),
            "multi_angle_photos": successful_photos
        }

        self.save()
        return True, f"Successfully enrolled '{person_name}' across {successful_photos} angles ({total_vectors_added} total vectors)."

    def remove_person(self, person_name):
        """Remove all embeddings for a person."""
        mask = self.names != person_name
        removed = np.sum(~mask)
        self.embeddings = self.embeddings[mask]
        self.names = self.names[mask]
        self.metadata.pop(person_name, None)
        self.save()
        return removed

    def recognize(self, embedding, threshold=0.50):
        """Match single face embedding against database."""
        if len(self.embeddings) == 0:
            return "Unknown", 0.0

        sims = cosine_similarity([embedding], self.embeddings)[0]
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= threshold:
            return str(self.names[best_idx]), best_sim
        return "Unknown", best_sim

class FaceTracker:
    """IoU-based face tracker for smooth track IDs."""

    def __init__(self, iou_threshold=0.3, max_disappeared=15):
        self.next_id = 0
        self.tracks = {}
        self.iou_threshold = iou_threshold
        self.max_disappeared = max_disappeared

    def _iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter = max(0, xB - xA) * max(0, yB - yA)
        areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        union = areaA + areaB - inter
        return inter / union if union > 0 else 0

    def update(self, detections):
        for tid in self.tracks:
            self.tracks[tid]["missing"] += 1

        matched_tracks = set()
        matched_dets = set()

        for d_idx, det in enumerate(detections):
            best_tid = None
            best_iou = self.iou_threshold

            for tid, track in self.tracks.items():
                if tid in matched_tracks:
                    continue
                iou = self._iou(det["bbox"], track["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

            if best_tid is not None:
                self.tracks[best_tid].update({
                    "bbox": det["bbox"],
                    "name": det["name"],
                    "score": det["score"],
                    "missing": 0,
                })
                matched_tracks.add(best_tid)
                matched_dets.add(d_idx)

        for d_idx, det in enumerate(detections):
            if d_idx not in matched_dets:
                self.tracks[self.next_id] = {
                    "bbox": det["bbox"],
                    "name": det["name"],
                    "score": det["score"],
                    "missing": 0,
                }
                self.next_id += 1

        stale = [tid for tid, t in self.tracks.items() if t["missing"] > self.max_disappeared]
        for tid in stale:
            del self.tracks[tid]

        results = []
        for tid, track in self.tracks.items():
            if track["missing"] == 0:
                results.append({
                    "track_id": tid,
                    "bbox": track["bbox"],
                    "name": track["name"],
                    "score": track["score"],
                })

        return results

from db_manager import DatabaseManager
db_sql = DatabaseManager()

class AttendanceLogger:
    """Logs person appearances with timestamps, exports to CSV, and saves to SQLite database."""

    def __init__(self, log_dir="attendance_logs"):
        self.log_dir = log_dir
        self.seen_today = {}
        os.makedirs(log_dir, exist_ok=True)

    def mark(self, name, video_time_str="N/A", frame_idx=0, source_file="N/A"):
        if not name or name == "Unknown" or "SPOOF ATTACK" in name:
            return False

        # Clean name from any formatting tags like [!], [Masked], [Glasses], etc.
        clean_name = str(name)
        if "[" in clean_name and "]" in clean_name:
            import re
            clean_name = re.sub(r"\[.*?\]", "", clean_name).strip()
        if "(" in clean_name and ")" in clean_name:
            import re
            clean_name = re.sub(r"\(.*?\)", "", clean_name).strip()

        clean_name = clean_name.strip()
        if not clean_name or clean_name == "Unknown" or "SPOOF ATTACK" in clean_name:
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        is_first_today = clean_name not in self.seen_today

        self.seen_today[clean_name] = {
            "timestamp": timestamp,
            "video_time": video_time_str,
            "frame": frame_idx,
        }

        try:
            db_sql.log_attendance(clean_name, status="Present", timestamp=timestamp, video_time=video_time_str, frame_number=frame_idx, source_file=source_file)
        except Exception as e:
            print(f"[WARN] DB logging notice: {e}")

        return is_first_today

    def save_csv(self, filename=None):
        if filename is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"attendance_{date_str}.csv"

        filepath = os.path.join(self.log_dir, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Status", "Timestamp", "Video Time", "Frame"])
            for name, info in sorted(self.seen_today.items()):
                writer.writerow([
                    name, "Present", info["timestamp"],
                    info["video_time"], info["frame"],
                ])
        return filepath

    def save_excel(self, filename=None):
        """Export attendance records as an Excel spreadsheet (.xlsx)."""
        import pandas as pd
        if filename is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"attendance_{date_str}.xlsx"

        filepath = os.path.join(self.log_dir, filename)
        records = []
        for name, info in sorted(self.seen_today.items()):
            records.append({
                "Name": name,
                "Status": "Present",
                "Timestamp": info["timestamp"],
                "Video Time": info["video_time"],
                "Frame Number": info["frame"],
            })

        df = pd.DataFrame(records)
        df.to_excel(filepath, index=False, engine="openpyxl")
        return filepath
