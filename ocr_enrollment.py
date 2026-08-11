import os
import cv2
import re
import base64
import numpy as np

try:
    import pytesseract
    # Auto-set Windows Tesseract PATH if present
    for t_path in [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
        if os.path.exists(t_path):
            pytesseract.pytesseract.tesseract_cmd = t_path
            break
except ImportError:
    pytesseract = None

try:
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False)
except Exception:
    reader = None

try:
    import fitz  # PyMuPDF for PDF parsing
except ImportError:
    fitz = None

class PaperOCREnroller:
    """Optical Character Recognition (OCR) paper document & PDF face auto-enrollment engine."""

    @classmethod
    def extract_text_from_image(cls, img_bgr: np.ndarray) -> str:
        """Extract written or printed name from paper document using EasyOCR / Tesseract / OpenCV text heuristics."""
        if img_bgr is None:
            return ""

        # 1. Try EasyOCR if available
        if reader is not None:
            try:
                ocr_results = reader.readtext(img_bgr, detail=0)
                full_text = " ".join(ocr_results)
                clean_text = re.sub(r'[^a-zA-Z\s]', '', full_text).strip()
                words = [w for w in clean_text.split() if len(w) >= 2 and w.lower() not in ['name', 'id', 'card', 'date', 'dept', 'role', 'person', 'signature']]
                if words:
                    return " ".join(words[:3]).title()
            except Exception as e:
                print(f"[WARN] EasyOCR error: {e}")

        # 2. Try PyTesseract
        if pytesseract is not None:
            try:
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                text = pytesseract.image_to_string(thresh)
                clean_text = re.sub(r'[^a-zA-Z\s]', '', text).strip()
                words = [w for w in clean_text.split() if len(w) >= 2 and w.lower() not in ['name', 'id', 'card', 'date', 'dept', 'role', 'person', 'signature']]
                if words:
                    return " ".join(words[:3]).title()
            except Exception as e:
                print(f"[WARN] Tesseract error: {e}")

        return ""

    @staticmethod
    def pdf_to_images(pdf_bytes: bytes) -> list:
        """Convert uploaded PDF document pages to BGR numpy image arrays."""
        images = []
        if fitz is not None:
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(dpi=150)
                    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
                    if pix.n == 4:
                        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
                    elif pix.n == 3:
                        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    images.append(img_np)
            except Exception as e:
                print(f"[WARN] PDF page extraction error: {e}")
        return images

    @classmethod
    def process_paper_document(cls, file_bytes: bytes, filename: str, db, ai_app, db_sql, fallback_name: str = None) -> dict:
        """Process paper document photo or PDF page, extract name via OCR, and auto-enroll face."""
        images = []
        filename_lower = filename.lower()

        if filename_lower.endswith(".pdf"):
            images = cls.pdf_to_images(file_bytes)
        else:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)

        if not images:
            return {"success": False, "message": "Failed to decode document image or PDF."}

        results = []

        for idx, img in enumerate(images):
            ocr_name = cls.extract_text_from_image(img)

            # Clean name from filename if OCR returns blank
            raw_file_name = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ")
            raw_file_name = re.sub(r'[^a-zA-Z\s]', '', raw_file_name).strip().title()

            if ocr_name:
                person_name = ocr_name
            elif fallback_name and len(fallback_name.strip()) > 0:
                person_name = fallback_name.strip().title()
            elif raw_file_name and len(raw_file_name) > 2 and raw_file_name.lower() not in ['document', 'scanned', 'image', 'photo', 'pdf', 'file']:
                person_name = raw_file_name
            else:
                person_name = f"Paper Subject {idx+1}"

            faces = ai_app.get(img)
            if not faces:
                continue

            # Crop face for visual verification preview
            face_bbox = faces[0].bbox.astype(int)
            x1, y1, x2, y2 = max(0, face_bbox[0]), max(0, face_bbox[1]), min(img.shape[1], face_bbox[2]), min(img.shape[0], face_bbox[3])
            face_crop = img[y1:y2, x1:x2]
            _, buffer = cv2.imencode('.jpg', face_crop)
            crop_base64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')

            success, msg = db.enroll_from_image_array(img, person_name, ai_app, augment=True)
            if success:
                db_sql.upsert_person(person_name, vector_count=int(np.sum(db.names == person_name)))
                results.append({
                    "page": idx + 1,
                    "extracted_name": person_name,
                    "ocr_detected": bool(ocr_name),
                    "face_crop": crop_base64,
                    "success": True,
                    "message": msg
                })

        if not results:
            return {"success": False, "message": "No face detected in uploaded paper document/PDF. Please ensure the document contains a clear face photo."}

        return {
            "success": True,
            "filename": filename,
            "enrolled": results
        }

if __name__ == "__main__":
    print("[INFO] Paper OCR Enrollment Engine Initialized.")
