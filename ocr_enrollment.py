import cv2
import re
import numpy as np

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import fitz  # PyMuPDF for PDF parsing
except ImportError:
    fitz = None

class PaperOCREnroller:
    """Optical Character Recognition (OCR) paper document & PDF face auto-enrollment engine."""

    @staticmethod
    def extract_text_from_image(img_bgr: np.ndarray) -> str:
        """Extract text written or printed on paper document using Tesseract or OpenCV OCR heuristics."""
        if img_bgr is None:
            return ""

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Preprocessing: Adaptive Thresholding for crisp text extraction
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        if pytesseract is not None:
            try:
                text = pytesseract.image_to_string(thresh)
                clean_text = re.sub(r'[^a-zA-Z\s]', '', text).strip()
                words = [w for w in clean_text.split() if len(w) > 2]
                if words:
                    return " ".join(words[:3]).title()
            except Exception:
                pass

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
            person_name = ocr_name if ocr_name else (fallback_name if fallback_name else f"Paper_Subject_{idx+1}")
            person_name = person_name.title().strip()

            faces = ai_app.get(img)
            if not faces:
                continue

            success, msg = db.enroll_from_image_array(img, person_name, ai_app, augment=True)
            if success:
                db_sql.upsert_person(person_name, vector_count=int(np.sum(db.names == person_name)))
                results.append({
                    "page": idx + 1,
                    "extracted_name": person_name,
                    "ocr_detected": bool(ocr_name),
                    "success": True,
                    "message": msg
                })

        if not results:
            return {"success": False, "message": "No face detected in uploaded paper document/PDF."}

        return {
            "success": True,
            "filename": filename,
            "enrolled": results
        }

if __name__ == "__main__":
    print("[INFO] Paper OCR Enrollment Engine Initialized.")
