import os
import sys
import time
import base64
import asyncio
import cv2
import numpy as np
import pandas as pd
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from face_tracker_engine import (
    FaceDatabase,
    FaceTracker,
    AttendanceLogger,
    load_insightface_app,
    get_execution_context,
    draw_fancy_label,
)

app = FastAPI(title="VisionTrack AI API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instances
print("[INFO] Loading InsightFace AI Engine...")
ai_app, ctx_id = load_insightface_app()
db = FaceDatabase()
global_tracker = FaceTracker()
global_logger = AttendanceLogger()

# Background video task status tracking
video_jobs = {}

# Ensure static and workspace directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("input_videos", exist_ok=True)
os.makedirs("output_videos", exist_ok=True)
os.makedirs("attendance_logs", exist_ok=True)
os.makedirs("dataset/images", exist_ok=True)

# Mount static directories for frontend and video streaming
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output_videos", StaticFiles(directory="output_videos"), name="output_videos")
app.mount("/input_videos", StaticFiles(directory="input_videos"), name="input_videos")

# Admin Session Authentication Management
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
active_sessions = set()

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        token = f"sess_{int(time.time()*1000)}"
        active_sessions.add(token)
        response = JSONResponse(content={"success": True, "token": token, "username": username})
        response.set_cookie(key="admin_session", value=token, httponly=True)
        return response
    raise HTTPException(status_code=401, detail="Invalid username or password.")

@app.post("/api/logout")
def logout(session: Optional[str] = Form(None)):
    if session in active_sessions:
        active_sessions.remove(session)
    response = JSONResponse(content={"success": True, "message": "Logged out."})
    response.delete_cookie(key="admin_session")
    return response

@app.get("/api/auth-status")
def auth_status(token: Optional[str] = None):
    is_auth = (token in active_sessions) if token else False
    return {"authenticated": is_auth, "user": ADMIN_USER if is_auth else None}

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

from db_manager import DatabaseManager
db_sql = DatabaseManager()

# Seed SQLite DB with current embeddings
for person in np.unique(db.names):
    vec_count = int(np.sum(db.names == person))
    db_sql.upsert_person(person, vector_count=vec_count)

from email_notifier import EmailNotifier
email_notifier = EmailNotifier()

@app.get("/api/stats")
def get_stats():
    log_files = [f for f in os.listdir("attendance_logs") if f.endswith(".csv")] if os.path.exists("attendance_logs") else []
    sql_stats = db_sql.get_summary_stats()
    return {
        "hardware": "NVIDIA CUDA (GPU)" if ctx_id == 0 else "CPU Mode",
        "ctx_id": ctx_id,
        "enrolled_persons": len(np.unique(db.names)),
        "total_vectors": len(db.embeddings),
        "csv_reports": len(log_files),
        "db_stats": sql_stats,
    }

from analytics_engine import AnalyticsEngine
analytics_engine = AnalyticsEngine()

@app.get("/api/analytics")
def get_analytics():
    trends = db_sql.get_daily_attendance_trend(days=7)
    depts = db_sql.get_department_breakdown()
    peak = analytics_engine.get_peak_hours_and_punctuality()
    return {
        "daily_trends": trends,
        "department_breakdown": depts,
        "peak_metrics": peak
    }

@app.get("/api/analytics/peak-hours")
def get_peak_hours():
    return analytics_engine.get_peak_hours_and_punctuality()

@app.get("/api/notifications")
def get_notification_settings():
    return email_notifier.config

@app.post("/api/notifications")
def update_notification_settings(config: dict):
    updated = email_notifier.save_config(config)
    return {"success": True, "config": updated}

@app.get("/api/persons")
def get_persons():
    unique_persons = np.unique(db.names) if len(db.names) > 0 else []
    db_persons_map = {p["name"]: p for p in db_sql.get_all_persons()}
    records = []
    for person in unique_persons:
        count = int(np.sum(db.names == person))
        db_rec = db_persons_map.get(person, {})
        enrolled = db_rec.get("created_at", "N/A")
        dept = db_rec.get("department", "General")
        role = db_rec.get("role", "Member")
        records.append({
            "name": person,
            "count": count,
            "department": dept,
            "role": role,
            "enrolled_at": enrolled,
        })
    return {"persons": records}

@app.post("/api/enroll")
async def enroll_person(
    name: str = Form(...),
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")

    img_bgr = None
    if file:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif image_base64:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        img_data = base64.b64decode(image_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        raise HTTPException(status_code=400, detail="No image file or base64 data provided.")

    success, msg = db.enroll_from_image_array(img_bgr, name.strip(), ai_app)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    db_sql.upsert_person(name.strip(), vector_count=int(np.sum(db.names == name.strip())))
    return {"success": True, "message": msg}

@app.post("/api/enroll-batch")
async def enroll_batch(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        raw_name = os.path.splitext(file.filename)[0]
        parts = raw_name.rsplit("_", 1)
        person_name = parts[0] if len(parts) == 2 and parts[1].isdigit() else raw_name
        person_name = person_name.replace("-", " ").replace("_", " ").title()

        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_bgr is None:
            results.append({"filename": file.filename, "name": person_name, "success": False, "message": "Invalid image format"})
            continue

        success, msg = db.enroll_from_image_array(img_bgr, person_name, ai_app)
        if success:
            db_sql.upsert_person(person_name, vector_count=int(np.sum(db.names == person_name)))
from ocr_enrollment import PaperOCREnroller

@app.post("/api/enroll-ocr-document")
async def enroll_ocr_document(file: UploadFile = File(...), name: str = Form(None)):
    contents = await file.read()
    res = PaperOCREnroller.process_paper_document(contents, file.filename, db, ai_app, db_sql, fallback_name=name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
from osint_scraper import OSINTScraper
from liveness_detector import LivenessDetector
from telegram_notifier import TelegramNotifier
from occlusion_engine import OcclusionDetector

from scheduler_service import AttendanceReportScheduler

vector_db = VectorDBManager()
liveness_engine = LivenessDetector()
telegram_bot = TelegramNotifier()
scheduler_service = AttendanceReportScheduler()
scheduler_service.start()

@app.get("/api/telegram/settings")
def get_telegram_settings():
    return telegram_bot.config

@app.post("/api/telegram/settings")
def update_telegram_settings(config: dict):
    updated = telegram_bot.save_config(config)
    return {"success": True, "config": updated}

@app.get("/api/schedule/settings")
def get_scheduler_settings():
    return scheduler_service.config

@app.post("/api/schedule/settings")
def update_scheduler_settings(config: dict):
    updated = scheduler_service.save_config(config)
    return {"success": True, "config": updated}

@app.post("/api/schedule/trigger-now")
def trigger_manual_report_dispatch():
    res = scheduler_service.trigger_dispatch()
    return res

@app.post("/api/reverse-search")
async def reverse_facial_search(
    file: UploadFile = File(None),
    image_url: str = Form(None),
    threshold: float = Form(0.45)
):
    """Reverse facial search against indexed social media profiles & database."""
    img_bgr = None

    if file:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif image_url:
        success, _, img_bytes = OSINTScraper.fetch_url_profile("temp", "temp", "temp", image_url, image_url)
        if success:
            img_bgr = OSINTScraper.decode_image_bytes(img_bytes)

    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image input. Provide a file or image URL.")

    faces = ai_app.get(img_bgr)
    if not faces:
        return {"matches": [], "message": "No face detected in target image."}

    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    target_face = faces[0]
    target_emb = target_face.embedding

    # 1. Search against OSINT Vector Database
    osint_matches = vector_db.search_profile(target_emb, top_k=5, threshold=threshold)

    # 2. Search against Internal Database
    internal_name, internal_score = db.recognize(target_emb, threshold=threshold)

    return {
        "face_detected": True,
        "internal_match": {
            "name": internal_name,
            "similarity_score": round(internal_score * 100, 2) if internal_name != "Unknown" else 0
        },
        "osint_matches": osint_matches,
        "total_osint_indexed": len(vector_db.embeddings)
    }

@app.post("/api/osint/ingest-github")
async def osint_ingest_github(username: str = Form(...)):
    """Ingest public profile avatar and metadata from GitHub by handle."""
    success, meta, img_bytes = OSINTScraper.fetch_github_profile(username)
    if not success:
        raise HTTPException(status_code=400, detail=meta)

    img_bgr = OSINTScraper.decode_image_bytes(img_bytes)
    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Failed to decode avatar image.")

    faces = ai_app.get(img_bgr)
    if not faces:
        raise HTTPException(status_code=400, detail=f"No face detected in GitHub avatar for '{username}'.")

    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    emb = faces[0].embedding

    profile_rec = vector_db.add_profile(
        name=meta["name"],
        username=meta["username"],
        platform=meta["platform"],
        profile_url=meta["profile_url"],
        bio=meta["bio"],
        location=meta["location"],
        embedding=emb,
        avatar_url=meta["avatar_url"]
    )

    db.enroll_from_image_array(img_bgr, meta["name"], ai_app)
    db_sql.upsert_person(meta["name"], vector_count=int(np.sum(db.names == meta["name"])))

    return {
        "success": True,
        "message": f"Successfully indexed OSINT profile for '{meta['name']}' (@{username})",
        "profile": profile_rec
    }

@app.post("/api/osint/ingest-url")
async def osint_ingest_url(
    name: str = Form(...),
    username: str = Form(...),
    platform: str = Form("Web"),
    profile_url: str = Form(""),
    image_url: str = Form(...),
    bio: str = Form(""),
    location: str = Form("")
):
    """Ingest profile photo from public web image URL with custom social tags."""
    success, meta, img_bytes = OSINTScraper.fetch_url_profile(name, username, platform, profile_url, image_url, bio, location)
    if not success:
        raise HTTPException(status_code=400, detail=meta)

    img_bgr = OSINTScraper.decode_image_bytes(img_bytes)
    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Failed to decode image from URL.")

    faces = ai_app.get(img_bgr)
    if not faces:
        raise HTTPException(status_code=400, detail="No face detected in image at provided URL.")

    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    emb = faces[0].embedding

    profile_rec = vector_db.add_profile(
        name=meta["name"],
        username=meta["username"],
        platform=meta["platform"],
        profile_url=meta["profile_url"],
        bio=meta["bio"],
        location=meta["location"],
        embedding=emb,
        avatar_url=meta["avatar_url"]
    )

    db.enroll_from_image_array(img_bgr, meta["name"], ai_app)
    db_sql.upsert_person(meta["name"], vector_count=int(np.sum(db.names == meta["name"])))

    return {
        "success": True,
        "message": f"Successfully indexed public profile for '{meta['name']}'",
        "profile": profile_rec
    }

@app.delete("/api/person/{name}")
def delete_person(name: str):
    removed = db.remove_person(name)
    db_sql.delete_person(name)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Person not found.")
    return {"success": True, "message": f"Removed {removed} vector embeddings for '{name}'."}

@app.post("/api/recognize-frame")
async def recognize_frame(data: dict):
    image_base64 = data.get("image")
    threshold = data.get("threshold", 0.50)
    if not image_base64:
        raise HTTPException(status_code=400, detail="Missing frame image.")

    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]

    img_bytes = base64.b64decode(image_base64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return {"detections": []}

    faces = ai_app.get(frame)
    raw_dets = []
    for face in faces:
        bbox = face.bbox.astype(int).tolist()
        name, score = db.recognize(face.embedding, threshold=threshold)

        # Anti-Spoofing Liveness Evaluation
        liveness = liveness_engine.check_liveness(frame, bbox)
        occlusion = OcclusionDetector.detect_mask(frame, bbox)

        if not liveness["is_real"]:
            name = f"⚠️ SPOOF ATTACK ({liveness['score']}%)"
        elif name == "Unknown":
            osint_matches = vector_db.search_profile(face.embedding, top_k=1, threshold=0.45)
            if osint_matches:
                best = osint_matches[0]
                name = f"{best['name']} (@{best['username']})"
                score = best['raw_score']

        if occlusion["is_masked"] and not name.startswith("⚠️"):
            name = f"😷 {name} [Masked]"

        raw_dets.append({"bbox": bbox, "name": name, "score": score, "is_masked": occlusion["is_masked"]})

        # Telegram Security Alert Trigger
        if not liveness["is_real"]:
            telegram_bot.send_alert("Anti-Spoofing Security Alert", f"Spoof paper/screen attack detected (Liveness Score: {liveness['score']}%).", frame)
        elif "Unknown" in name:
            telegram_bot.send_alert("Unknown Person Detected", "Unrecognized person detected in camera feed.", frame)

    tracked_dets = global_tracker.update(raw_dets)

    for det in tracked_dets:
        x1, y1, x2, y2 = det["bbox"]
        name = det["name"]
        score = det["score"]
        tid = det["track_id"]

        color = (0, 200, 0) if "@" not in name and name != "Unknown" else ((245, 158, 11) if "@" in name else (0, 0, 220))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        draw_fancy_label(frame, f"#{tid} {name} {score:.0%}", x1, y1, color)
        global_logger.mark(name)

    global_logger.save_csv()

    _, buffer = cv2.imencode(".jpg", frame)
    annotated_b64 = base64.b64encode(buffer).decode("utf-8")

    return {
        "annotated_image": f"data:image/jpeg;base64,{annotated_b64}",
        "detections": tracked_dets,
    }

@app.get("/api/videos")
def get_videos():
    input_vids = [f for f in os.listdir("input_videos") if f.endswith((".mp4", ".avi", ".mkv", ".mov"))]
    output_vids = [f for f in os.listdir("output_videos") if f.endswith((".mp4", ".avi", ".mkv", ".mov"))]
    return {"input_videos": input_vids, "output_videos": output_vids}

def run_video_processing_task(job_id: str, video_filename: str, threshold: float, submit_every_n: int):
    input_path = os.path.join("input_videos", video_filename)
    out_filename = f"annotated_{video_filename}"
    out_path = os.path.join("output_videos", out_filename)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        video_jobs[job_id] = {"status": "error", "message": "Cannot open video file."}
        return

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    tracker = FaceTracker(iou_threshold=0.3)
    logger = AttendanceLogger()

    frame_idx = 0
    cached_dets = []
    t_start = time.time()

    video_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "current_frame": 0,
        "total_frames": total_frames,
        "output_file": out_filename,
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % submit_every_n == 0:
            faces = ai_app.get(frame)
            raw_dets = []
            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                name, score = db.recognize(face.embedding, threshold=threshold)
                raw_dets.append({"bbox": bbox, "name": name, "score": score})
            cached_dets = tracker.update(raw_dets)

        for det in cached_dets:
            x1, y1, x2, y2 = det["bbox"]
            name = det["name"]
            score = det["score"]
            tid = det["track_id"]

            color = (0, 200, 0) if name != "Unknown" else (0, 0, 220)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"#{tid} {name} {score:.0%}"
            draw_fancy_label(frame, label, x1, y1, color)
            logger.mark(name, video_time_str=f"{frame_idx / fps:.1f}s", frame_idx=frame_idx)

        out.write(frame)
        frame_idx += 1

        if frame_idx % 10 == 0 or frame_idx == total_frames:
            progress_pct = int((frame_idx / max(1, total_frames)) * 100)
            video_jobs[job_id].update({
                "progress": progress_pct,
                "current_frame": frame_idx,
            })

    cap.release()
    out.release()
    logger.save_csv()

    video_jobs[job_id].update({
        "status": "completed",
        "progress": 100,
        "total_time": round(time.time() - t_start, 2),
        "output_file": out_filename,
        "output_url": f"/output_videos/{out_filename}",
        "attendance": logger.seen_today,
    })

@app.post("/api/process-video")
async def process_video(
    background_tasks: BackgroundTasks = None,
    filename: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    threshold: float = Form(0.50),
    submit_every_n: int = Form(2),
):
    target_filename = None
    if file:
        target_filename = file.filename
        save_path = os.path.join("input_videos", target_filename)
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)
    elif filename:
        target_filename = filename

    if not target_filename or not os.path.exists(os.path.join("input_videos", target_filename)):
        raise HTTPException(status_code=400, detail="Target video file not found.")

    job_id = f"job_{int(time.time()*1000)}"
    asyncio.create_task(asyncio.to_thread(run_video_processing_task, job_id, target_filename, threshold, submit_every_n))

    return {"job_id": job_id, "status": "started"}

@app.get("/api/job-status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in video_jobs:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return video_jobs[job_id]

@app.get("/api/attendance")
def get_attendance():
    log_dir = "attendance_logs"
    if not os.path.exists(log_dir):
        return {"files": [], "logs": []}

    csv_files = sorted([f for f in os.listdir(log_dir) if f.endswith(".csv")], reverse=True)
    logs = []
    if csv_files:
        latest_file = os.path.join(log_dir, csv_files[0])
        df = pd.read_csv(latest_file)
        logs = df.to_dict(orient="records")

    return {"files": csv_files, "latest_logs": logs}

from pdf_generator import generate_pdf_report

@app.get("/api/download-attendance/{filename}")
def download_attendance(filename: str):
    file_path = os.path.join("attendance_logs", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found.")
    return FileResponse(file_path, media_type="text/csv", filename=filename)

@app.get("/api/generate-excel/{filename}")
def download_excel_attendance(filename: str):
    csv_path = os.path.join("attendance_logs", filename)
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found.")

    df = pd.read_csv(csv_path)
    excel_name = filename.replace(".csv", ".xlsx")
    excel_path = os.path.join("attendance_logs", excel_name)
    df.to_excel(excel_path, index=False, engine="openpyxl")
    return FileResponse(excel_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=excel_name)

@app.post("/api/process-rtsp")
async def process_rtsp_stream(
    rtsp_url: str = Form(...),
    duration_seconds: int = Form(10),
    threshold: float = Form(0.50)
):
    """Process real-time CCTV RTSP/IP camera stream."""
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail=f"Cannot connect to RTSP/IP stream: {rtsp_url}")

    start_time = time.time()
    frames_processed = 0
    tracker = FaceTracker()
    logger = AttendanceLogger()

    while (time.time() - start_time) < duration_seconds:
        ret, frame = cap.read()
        if not ret:
            break
        frames_processed += 1
        if frames_processed % 3 != 0:
            continue

        faces = ai_app.get(frame)
        raw_dets = []
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            name, score = db.recognize(face.embedding, threshold=threshold)
            raw_dets.append({"bbox": bbox, "name": name, "score": score})

        tracked_dets = tracker.update(raw_dets)
        for det in tracked_dets:
            logger.mark(det["name"], source_file=f"RTSP:{rtsp_url}")

    cap.release()
    csv_file = logger.save_csv()
    return {
        "success": True,
        "rtsp_url": rtsp_url,
        "duration_seconds": duration_seconds,
        "frames_processed": frames_processed,
        "present_persons": list(logger.seen_today.keys()),
        "report_csv": os.path.basename(csv_file)
    }

@app.get("/api/generate-pdf/{filename}")
def download_pdf_attendance(filename: str):
    csv_path = os.path.join("attendance_logs", filename)
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found.")

    pdf_path = generate_pdf_report(csv_path)
    pdf_filename = os.path.basename(pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_filename)

from id_card_generator import generate_id_card

@app.get("/api/generate-id-card/{person_name}")
def download_person_id_card(person_name: str):
    db_persons = {p["name"]: p for p in db_sql.get_all_persons()}
    p_info = db_persons.get(person_name, {})
    dept = p_info.get("department", "AI Engineering")
    role = p_info.get("role", "Member")
    created = str(p_info.get("created_at", "2026-08-10"))[:10]

    pdf_path = generate_id_card(person_name, department=dept, role=role, enrolled_date=created)
    pdf_filename = os.path.basename(pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_filename)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
