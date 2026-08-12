import os
import sys
import time
import base64
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
import cv2
import numpy as np
import pandas as pd
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException, Request
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

# --- Authentication & Session Security Engine ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))

# Active session store: token -> {"user": username, "last_active": timestamp}
active_sessions: dict[str, dict] = {}

# Login rate limiting store: client_ip -> {"count": int, "lockout_until": timestamp}
login_failed_attempts: dict[str, dict] = {}
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes lockout

def is_valid_session(token: str) -> bool:
    """Validate token against active_sessions, enforce idle timeout, and update activity."""
    if not token or token not in active_sessions:
        return False
    
    session = active_sessions[token]
    elapsed_seconds = time.time() - session.get("last_active", 0)
    
    if elapsed_seconds > (SESSION_TIMEOUT_MINUTES * 60):
        del active_sessions[token]
        return False
    
    session["last_active"] = time.time()
    return True

@app.middleware("http")
async def enforce_auth_middleware(request: Request, call_next):
    """Enforce session authentication middleware across all endpoints except whitelisted paths."""
    path = request.url.path
    
    # Whitelisted public routes & static resources
    if (
        path == "/"
        or path == "/favicon.ico"
        or path == "/api/login"
        or path == "/api/logout"
        or path == "/api/auth-status"
        or path.startswith("/static/")
        or path.startswith("/output_videos/")
        or path.startswith("/input_videos/")
    ):
        return await call_next(request)
    
    # Extract session token from Authorization header, query param, or cookie
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
    if not token:
        token = request.query_params.get("token")
    if not token:
        token = request.cookies.get("admin_session")
        
    if not token or not is_valid_session(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Please log in to access this resource."}
        )
        
    return await call_next(request)

@app.post("/api/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    
    # Check rate limit lockout status
    rate_info = login_failed_attempts.get(client_ip, {"count": 0, "lockout_until": 0})
    if rate_info["lockout_until"] > now:
        remaining_seconds = int(rate_info["lockout_until"] - now)
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many failed login attempts. Account locked. Try again in {remaining_seconds} seconds."}
        )
    
    # Verify env-based ADMIN_USER / ADMIN_PASS credentials
    if username == ADMIN_USER and password == ADMIN_PASS:
        if client_ip in login_failed_attempts:
            del login_failed_attempts[client_ip]
            
        token = f"sess_{int(now*1000)}_{os.urandom(6).hex()}"
        active_sessions[token] = {
            "user": username,
            "last_active": now,
            "created_at": now
        }
        response = JSONResponse(content={"success": True, "token": token, "username": username})
        response.set_cookie(key="admin_session", value=token, httponly=True)
        return response
    
    # Handle failed login attempt & rate limit counter
    count = rate_info["count"] + 1
    if count >= MAX_FAILED_LOGIN_ATTEMPTS:
        lockout_until = now + LOCKOUT_DURATION_SECONDS
        login_failed_attempts[client_ip] = {"count": count, "lockout_until": lockout_until}
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many failed login attempts. Account locked out for {LOCKOUT_DURATION_SECONDS // 60} minutes."}
        )
    else:
        login_failed_attempts[client_ip] = {"count": count, "lockout_until": 0}
        attempts_left = MAX_FAILED_LOGIN_ATTEMPTS - count
        raise HTTPException(
            status_code=401,
            detail=f"Invalid username or password. ({attempts_left} attempt(s) remaining before lockout)"
        )

@app.post("/api/logout")
def logout(request: Request, session: Optional[str] = Form(None)):
    token = session
    if not token:
        token = request.cookies.get("admin_session")
    if token and token in active_sessions:
        del active_sessions[token]
    response = JSONResponse(content={"success": True, "message": "Logged out."})
    response.delete_cookie(key="admin_session")
    return response

@app.get("/api/auth-status")
def auth_status(request: Request, token: Optional[str] = None):
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
    if not token:
        token = request.cookies.get("admin_session")
        
    if token and is_valid_session(token):
        user = active_sessions[token]["user"]
        return {"authenticated": True, "user": user, "token": token}
    
    return {"authenticated": False, "user": None}

@app.get("/")
@app.head("/")
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

@app.post("/api/enroll-multi-angle")
async def enroll_multi_angle(
    files: list[UploadFile] = File(...),
    name: str = Form(...),
    department: str = Form("General"),
    role: str = Form("Member"),
    consent: bool = Form(...)
):
    """Self-enrollment endpoint accepting 3-5 multi-angle selfies with explicit consent."""
    if not consent:
        raise HTTPException(status_code=400, detail="Explicit user consent is required for biometric self-enrollment.")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Person name is required.")

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least 1 multi-angle selfie photo is required.")

    img_bgr_list = []
    for file in files:
        contents = await file.read()
        if len(contents) > 0:
            nparr = np.frombuffer(contents, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img_bgr is not None:
                img_bgr_list.append(img_bgr)

    if not img_bgr_list:
        raise HTTPException(status_code=400, detail="Failed to decode any valid face image files.")

    success, msg = db.enroll_multi_angle(img_bgr_list, name.strip(), ai_app, augment=True)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    db_sql.upsert_person(name.strip(), department.strip(), role.strip(), vector_count=int(np.sum(db.names == name.strip())), consent_given=1)
    db_sql.log_audit("MULTI_ANGLE_ENROLLMENT", f"Self-enrolled '{name}' across {len(img_bgr_list)} photo angles with explicit user consent.")

    return {"success": True, "message": msg}

@app.get("/api/my-data/{name}")
def get_my_data(name: str):
    """View stored biometric metadata, consent record, and attendance history for an enrolled user."""
    db_persons = {p["name"]: p for p in db_sql.get_all_persons()}
    if name not in db_persons and name not in db.names:
        raise HTTPException(status_code=404, detail=f"No stored records found for '{name}'.")

    p_rec = db_persons.get(name, {})
    vector_count = int(np.sum(db.names == name))
    logs = db_sql.get_attendance_logs(limit=50, person_name=name)

    return {
        "success": True,
        "person": {
            "name": name,
            "department": p_rec.get("department", "General"),
            "role": p_rec.get("role", "Member"),
            "vector_count": vector_count,
            "consent_given": bool(p_rec.get("consent_given", 1)),
            "created_at": p_rec.get("created_at", "N/A"),
        },
        "attendance_history": logs
    }

@app.delete("/api/my-data/{name}")
def delete_my_data(name: str):
    """User-requested privacy deletion: permanently purge embeddings, database records, and logs."""
    removed_embeddings = db.remove_person(name)
    vector_db.remove_profile(name)
    db_sql.purge_user_data(name)

    return {
        "success": True,
        "message": f"Consent withdrawn. Permanently purged {removed_embeddings} feature vectors and all records for '{name}'."
    }

@app.get("/api/confidence-alerts")
def get_confidence_alerts():
    """Retrieve low-confidence & borderline face recognition check-ins for admin review."""
    return {"alerts": db_sql.get_confidence_alerts(limit=50)}

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
from vector_db import VectorDBManager
from ocr_enrollment import PaperOCREnroller
from osint_scraper import OSINTScraper
from liveness_detector import LivenessDetector
from occlusion_engine import OcclusionDetector

from scheduler_service import AttendanceReportScheduler
from postgres_manager import PostgresManager

vector_db = VectorDBManager()
liveness_engine = LivenessDetector()
scheduler_service = AttendanceReportScheduler()
scheduler_service.start()
postgres_manager = PostgresManager()

@app.get("/api/postgres/settings")
def get_postgres_settings():
    cfg = postgres_manager.config.copy()
    cfg["password"] = "••••••••" if cfg.get("password") else ""
    return cfg

@app.post("/api/postgres/settings")
def update_postgres_settings(data: dict):
    new_cfg = {
        "enabled": bool(data.get("enabled", False)),
        "host": str(data.get("host", "localhost")).strip(),
        "port": int(data.get("port", 5432)),
        "database": str(data.get("database", "visiontrack_db")).strip(),
        "user": str(data.get("user", "postgres")).strip()
    }
    if "password" in data and data["password"] != "••••••••":
        new_cfg["password"] = str(data["password"])
    else:
        new_cfg["password"] = postgres_manager.config.get("password", "")

    saved = postgres_manager.save_config(new_cfg)
    return {"success": True, "message": "PostgreSQL configuration updated.", "config": saved}

@app.post("/api/postgres/test")
def test_postgres_connection(data: dict):
    cfg = {
        "host": str(data.get("host", "localhost")).strip(),
        "port": int(data.get("port", 5432)),
        "database": str(data.get("database", "visiontrack_db")).strip(),
        "user": str(data.get("user", "postgres")).strip(),
        "password": str(data.get("password", "")) if data.get("password") != "••••••••" else postgres_manager.config.get("password", "")
    }
    ok, msg = postgres_manager.test_connection(cfg)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}

@app.post("/api/postgres/migrate")
def migrate_to_postgres():
    ok, msg = postgres_manager.migrate_from_sqlite()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    db_sql.log_audit("POSTGRES_MIGRATION", msg)
    return {"success": True, "message": msg}

@app.post("/api/enroll-ocr-document")
async def enroll_ocr_document(file: UploadFile = File(...), name: str = Form(None)):
    contents = await file.read()
    res = PaperOCREnroller.process_paper_document(contents, file.filename, db, ai_app, db_sql, fallback_name=name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

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
    file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    threshold: float = Form(0.45)
):
    """Reverse facial search against indexed vector database & internal database."""
    img_bgr = None

    try:
        if file and file.filename:
            contents = await file.read()
            if len(contents) > 0:
                nparr = np.frombuffer(contents, np.uint8)
                img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif image_url and image_url.strip():
            success, _, img_bytes = OSINTScraper.fetch_url_profile("temp", "temp", "temp", image_url.strip(), image_url.strip())
            if success and img_bytes:
                img_bgr = OSINTScraper.decode_image_bytes(img_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process image: {str(e)}")

    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image file or inaccessible image URL.")

    faces = ai_app.get(img_bgr)
    if not faces:
        return {
            "face_detected": False,
            "internal_match": {"name": "Unknown", "similarity_score": 0},
            "osint_matches": [],
            "total_osint_indexed": len(vector_db.embeddings),
            "message": "No face detected in target image."
        }

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
    check_spoof = bool(data.get("check_spoof", True))
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

        # Pure Face Recognition Mode (Anti-Spoofing Bypassed)
        liveness = {"is_real": True, "score": 100.0, "status": "Real Face"}
        occlusion = OcclusionDetector.detect_occlusion(frame, bbox)

        is_borderline = False
        if name != "Unknown":
            # Confidence threshold evaluation (borderline score or heavy occlusion)
            if score < 0.52 or occlusion["requires_manual_checkin"]:
                is_borderline = True
                db_sql.log_confidence_alert(name, score, "BORDERLINE", f"Low confidence match ({score:.1%}) - {occlusion['details']}")
                if occlusion["requires_manual_checkin"]:
                    name = f"[!] {name} [Manual Check-in Needed]"
                else:
                    name = f"[!] {name} (Low Conf {score:.0%})"

            if occlusion["is_masked"] and not name.startswith("[!]"):
                name = f"[Masked] {name}"
            elif occlusion["has_sunglasses"] and not name.startswith("[!]"):
                name = f"[Glasses] {name}"

        raw_dets.append({
            "bbox": bbox,
            "name": name,
            "score": score,
            "is_masked": occlusion["is_masked"],
            "has_sunglasses": occlusion["has_sunglasses"],
            "is_borderline": is_borderline
        })

    tracked_dets = global_tracker.update(raw_dets)
    marked_names = []

    for det in tracked_dets:
        x1, y1, x2, y2 = det["bbox"]
        name = det["name"]
        score = det["score"]
        tid = det["track_id"]

        color = (0, 200, 0) if "@" not in name and name != "Unknown" else ((245, 158, 11) if "@" in name else (0, 0, 220))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        draw_fancy_label(frame, f"#{tid} {name} {score:.0%}", x1, y1, color)

        import re
        clean_n = re.sub(r"\[.*?\]", "", name).strip()
        clean_n = re.sub(r"\(.*?\)", "", clean_n).strip()
        if clean_n and clean_n != "Unknown":
            global_logger.mark(name, source_file="Live Camera Feed")
            marked_names.append(clean_n)

    try:
        global_logger.save_csv()
    except Exception as e:
        print(f"[WARN] Failed to write CSV log: {e}")

    _, buffer = cv2.imencode(".jpg", frame)
    annotated_b64 = base64.b64encode(buffer).decode("utf-8")

    return {
        "annotated_image": f"data:image/jpeg;base64,{annotated_b64}",
        "detections": tracked_dets,
        "marked_names": marked_names
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
    os.makedirs(log_dir, exist_ok=True)

    today_csv = f"attendance_{datetime.now().strftime('%Y-%m-%d')}.csv"
    today_path = os.path.join(log_dir, today_csv)
    if not os.path.exists(today_path):
        global_logger.save_csv(today_csv)

    csv_files = [f for f in os.listdir(log_dir) if f.endswith(".csv")]
    csv_files.sort(key=lambda x: (0 if x == today_csv else 1, x))

    logs = db_sql.get_attendance_logs(limit=100)
    return {"files": csv_files, "latest_logs": logs, "logs": logs}

from pdf_generator import generate_pdf_report

@app.get("/api/download-attendance/{filename}")
def download_attendance(filename: str):
    file_path = os.path.join("attendance_logs", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found.")
    return FileResponse(file_path, media_type="text/csv", filename=filename)

@app.get("/api/attendance-details/{filename}")
def get_attendance_details(filename: str):
    file_path = os.path.join("attendance_logs", filename)
    if not os.path.exists(file_path):
        logs = db_sql.get_attendance_logs(limit=100)
        return {"success": True, "records": logs}

    try:
        df = pd.read_csv(file_path)
        records = df.fillna("").to_dict(orient="records")
        return {"success": True, "records": records}
    except Exception as e:
        logs = db_sql.get_attendance_logs(limit=100)
        return {"success": True, "records": logs}

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
    if filename.lower() in ["today", "latest"]:
        filename = f"attendance_{datetime.now().strftime('%Y-%m-%d')}.csv"
        csv_path = os.path.join("attendance_logs", filename)
        if not os.path.exists(csv_path):
            global_logger.save_csv()
    else:
        csv_path = os.path.join("attendance_logs", filename)

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV report file not found.")

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
