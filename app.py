import os
import sys
import time
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from face_tracker_engine import (
    FaceDatabase,
    FaceTracker,
    AttendanceLogger,
    load_insightface_app,
    get_execution_context,
    draw_fancy_label,
)

# Page configuration
st.set_page_config(
    page_title="VisionTrack AI — Emerald Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modern Dark Emerald Glassmorphism Styling
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #022c22 0%, #064e3b 50%, #021f17 100%);
        color: #ecfdf5;
    }

    .hero-card {
        background: rgba(6, 78, 59, 0.5);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(52, 211, 153, 0.2);
        border-radius: 16px;
        padding: 1.8rem 2.2rem;
        margin-bottom: 2rem;
        box-shadow: 0 12px 32px 0 rgba(0, 0, 0, 0.4);
        background-image: radial-gradient(at 0% 0%, rgba(16, 185, 129, 0.25) 0px, transparent 50%),
                          radial-gradient(at 100% 100%, rgba(5, 150, 105, 0.25) 0px, transparent 50%);
    }

    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6ee7b7 0%, #34d399 50%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #a7f3d0;
        margin-top: 0.4rem;
        font-weight: 400;
    }

    .stat-box {
        background: rgba(6, 78, 59, 0.5);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(52, 211, 153, 0.15);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stat-box:hover {
        transform: translateY(-3px);
        border-color: rgba(52, 211, 153, 0.5);
        box-shadow: 0 8px 24px rgba(16, 185, 129, 0.25);
    }
    .stat-num {
        font-size: 2.2rem;
        font-weight: 700;
        color: #34d399;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #a7f3d0;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }

    [data-testid="stSidebar"] {
        background: rgba(2, 44, 34, 0.95);
        border-right: 1px solid rgba(52, 211, 153, 0.15);
    }

    .stButton>button {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: #ffffff;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.4rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 14px 0 rgba(16, 185, 129, 0.35);
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #047857 0%, #059669 100%);
        box-shadow: 0 6px 20px 0 rgba(16, 185, 129, 0.5);
        transform: translateY(-1px);
    }

    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(52, 211, 153, 0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource
def get_engine():
    app, ctx_id = load_insightface_app()
    db = FaceDatabase()
    return app, db, ctx_id

app, db, ctx_id = get_engine()

# Sidebar Navigation
st.sidebar.markdown(
    """
    <div style="text-align: center; padding: 1rem 0;">
        <span style="font-size: 2.5rem;">🌿</span>
        <h2 style="margin: 0.2rem 0 0 0; font-size: 1.4rem; font-weight: 700; color: #ecfdf5;">VisionTrack AI</h2>
        <span style="font-size: 0.8rem; color: #34d399; font-weight: 600; letter-spacing: 1px;">EMERALD FACE INTELLIGENCE</span>
    </div>
    """,
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigation Menu",
    [
        "📊 System Dashboard",
        "👤 Face Registration & DB",
        "🎬 Video Tracking Engine",
        "📷 Live Camera Surveillance",
        "📄 Attendance Reports",
    ],
)

device_status = "🟢 NVIDIA CUDA (GPU)" if ctx_id == 0 else "🟡 CPU Inference Mode"
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Hardware Engine:** {device_status}")
st.sidebar.markdown(f"**Registered Persons:** `{len(np.unique(db.names))}`")
st.sidebar.markdown(f"**Total Face Vectors:** `{len(db.embeddings)}`")

# PAGE 1: SYSTEM DASHBOARD
if page == "📊 System Dashboard":
    st.markdown(
        """
        <div class="hero-card">
            <h1 class="hero-title">🌿 VisionTrack Emerald Dashboard</h1>
            <p class="hero-subtitle">Real-time InsightFace Recognition • IoU Multi-Object Tracking • Automated Attendance System</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-box"><div class="stat-num">{ "GPU CUDA" if ctx_id == 0 else "CPU" }</div><div class="stat-label">Inference Engine</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-box"><div class="stat-num">{ len(np.unique(db.names)) }</div><div class="stat-label">Enrolled Individuals</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-box"><div class="stat-num">{ len(db.embeddings) }</div><div class="stat-label">512-D ArcFace Vectors</div></div>', unsafe_allow_html=True)
    with col4:
        log_files = [f for f in os.listdir("attendance_logs") if f.endswith(".csv")] if os.path.exists("attendance_logs") else []
        st.markdown(f'<div class="stat-box"><div class="stat-num">{ len(log_files) }</div><div class="stat-label">Generated CSV Reports</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 Registered Face Database Summary")

    if len(db.names) > 0:
        unique_persons = np.unique(db.names)
        records = []
        for person in unique_persons:
            count = int(np.sum(db.names == person))
            meta = db.metadata.get(person, {})
            enrolled = meta.get("enrolled_at", "N/A")
            records.append({
                "Person Name": person,
                "Embedding Samples": count,
                "Registration Timestamp": enrolled,
            })
        df_persons = pd.DataFrame(records)
        st.dataframe(df_persons, use_container_width=True)
    else:
        st.info("No persons currently registered. Navigate to 'Face Registration & DB' to enroll faces.")

# PAGE 2: FACE REGISTRATION
elif page == "👤 Face Registration & DB":
    st.markdown(
        """
        <div class="hero-card">
            <h1 class="hero-title">👤 Face Enrollment & Management</h1>
            <p class="hero-subtitle">Extract 512-D facial embeddings from high-res photos or live webcam snapshots</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["📁 Upload Image", "📸 Webcam Capture", "🗑️ Manage Registered Database"])

    with tab1:
        col_in, col_pv = st.columns([1, 1])
        with col_in:
            person_name = st.text_input("Enter Person Full Name", key="upload_name", placeholder="e.g. Alice Smith")
            uploaded_file = st.file_uploader("Upload Clear Face Photo (JPG, PNG, JPEG)", type=["jpg", "png", "jpeg"])
            btn_enroll = st.button("✨ Register & Extract Embedding", key="btn_file_enroll")

        with col_pv:
            if uploaded_file is not None:
                img_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                img_bgr = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
                st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), caption="Photo Preview", width=320)

                if btn_enroll:
                    if not person_name.strip():
                        st.error("Please enter a valid person name.")
                    else:
                        success, msg = db.enroll_from_image_array(img_bgr, person_name.strip(), app)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    with tab2:
        col_w_in, col_w_pv = st.columns([1, 1])
        with col_w_in:
            webcam_name = st.text_input("Enter Person Full Name", key="webcam_name", placeholder="e.g. Bob Johnson")
            cam_photo = st.camera_input("Take Snapshot")

        with col_w_pv:
            if cam_photo is not None and webcam_name.strip() != "":
                img_bytes = np.asarray(bytearray(cam_photo.read()), dtype=np.uint8)
                img_bgr = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
                if st.button("✨ Register Webcam Snapshot"):
                    success, msg = db.enroll_from_image_array(img_bgr, webcam_name.strip(), app)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab3:
        st.subheader("Manage Database Records")
        if len(db.names) > 0:
            unique_persons = sorted(list(np.unique(db.names)))
            to_remove = st.selectbox("Select Enrolled Person to Delete", unique_persons)
            if st.button("🗑️ Remove Person from Database", type="primary"):
                removed_count = db.remove_person(to_remove)
                st.success(f"Removed '{to_remove}' ({removed_count} face vectors deleted).")
                st.rerun()
        else:
            st.info("Database is empty.")

# PAGE 3: VIDEO TRACKING
elif page == "🎬 Video Tracking Engine":
    st.markdown(
        """
        <div class="hero-card">
            <h1 class="hero-title">🎬 Video Multi-Object Tracking</h1>
            <p class="hero-subtitle">High-speed InsightFace detection with IoU object tracking & timestamped attendance</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    os.makedirs("input_videos", exist_ok=True)
    os.makedirs("output_videos", exist_ok=True)
    existing_videos = [f for f in os.listdir("input_videos") if f.endswith((".mp4", ".avi", ".mkv", ".mov"))]

    col_opt1, col_opt2 = st.columns([1, 1])
    with col_opt1:
        video_choice = st.radio("Source Video Option", ["Select Existing Video", "Upload New Video File"])

    if video_choice == "Upload New Video File":
        uploaded_vid = st.file_uploader("Upload Video (MP4, AVI, MKV, MOV)", type=["mp4", "avi", "mkv", "mov"])
        if uploaded_vid is not None:
            save_path = os.path.join("input_videos", uploaded_vid.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_vid.read())
            st.success(f"File uploaded: {uploaded_vid.name}")
            target_video_path = save_path
        else:
            target_video_path = None
    else:
        if existing_videos:
            selected_vid = st.selectbox("Choose Input Video", existing_videos)
            target_video_path = os.path.join("input_videos", selected_vid)
        else:
            st.warning("No existing videos found in 'input_videos/'. Upload a video to start.")
            target_video_path = None

    if target_video_path and os.path.exists(target_video_path):
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("⚙️ Processing Parameters")
        c1, c2 = st.columns(2)
        with c1:
            threshold = st.slider("Cosine Similarity Threshold", 0.30, 0.85, 0.50, 0.05)
        with c2:
            submit_every_n = st.slider("Detection Frame Interval (Skip factor)", 1, 5, 2)

        if st.button("🚀 Start Video Analysis Engine", type="primary"):
            cap = cv2.VideoCapture(target_video_path)
            if not cap.isOpened():
                st.error("Cannot open selected video file.")
            else:
                fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                out_filename = f"annotated_{os.path.basename(target_video_path)}"
                out_path = os.path.join("output_videos", out_filename)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

                tracker = FaceTracker(iou_threshold=0.3)
                logger = AttendanceLogger()

                st_progress = st.progress(0.0)
                st_status = st.empty()
                st_frame_view = st.empty()

                frame_idx = 0
                cached_dets = []
                t_start = time.time()

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_idx % submit_every_n == 0:
                        faces = app.get(frame)
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

                    progress_val = min(1.0, frame_idx / max(1, total_frames))
                    st_progress.progress(progress_val)
                    st_status.text(f"Processing Frame {frame_idx}/{total_frames} ({progress_val:.0%})...")

                    if frame_idx % 30 == 0 or frame_idx == total_frames:
                        preview_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        st_frame_view.image(preview_rgb, caption=f"Processing Frame {frame_idx}", width=640)

                cap.release()
                out.release()

                csv_file = logger.save_csv()
                total_time = time.time() - t_start

                st.success(f"Processing Complete! Output saved to '{out_path}' ({total_time:.1f}s)")
                st.subheader("Attendance Logged")
                st.dataframe(pd.DataFrame.from_dict(logger.seen_today, orient="index"))

# PAGE 4: LIVE CAMERA
elif page == "📷 Live Camera Surveillance":
    st.markdown(
        """
        <div class="hero-card">
            <h1 class="hero-title">📷 Live Webcam Surveillance</h1>
            <p class="hero-subtitle">Real-time camera feed recognition & instant attendance logging</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info("Toggle the checkbox below to connect to your system's default camera feed.")
    run_cam = st.checkbox("Turn On Live Camera Feed")
    cam_preview = st.empty()

    if run_cam:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            st.error("Cannot open default camera (Index 0).")
        else:
            tracker = FaceTracker()
            logger = AttendanceLogger()
            frame_idx = 0

            while run_cam:
                ret, frame = cap.read()
                if not ret:
                    st.warning("Camera stream interrupted.")
                    break

                if frame_idx % 2 == 0:
                    faces = app.get(frame)
                    raw_dets = []
                    for face in faces:
                        bbox = face.bbox.astype(int).tolist()
                        name, score = db.recognize(face.embedding, threshold=0.50)
                        raw_dets.append({"bbox": bbox, "name": name, "score": score})
                    cached_dets = tracker.update(raw_dets)
                else:
                    cached_dets = tracker.update([])

                for det in cached_dets:
                    x1, y1, x2, y2 = det["bbox"]
                    name = det["name"]
                    score = det["score"]
                    color = (0, 200, 0) if name != "Unknown" else (0, 0, 220)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    draw_fancy_label(frame, f"{name} {score:.0%}", x1, y1, color)
                    logger.mark(name, frame_idx=frame_idx)

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                cam_preview.image(frame_rgb, channels="RGB", use_container_width=True)
                frame_idx += 1
                time.sleep(0.01)

            cap.release()
            logger.save_csv()

# PAGE 5: ATTENDANCE REPORTS
elif page == "📄 Attendance Reports":
    st.markdown(
        """
        <div class="hero-card">
            <h1 class="hero-title">📄 Attendance Log Records</h1>
            <p class="hero-subtitle">Inspect, filter, and export CSV attendance sheets</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    log_dir = "attendance_logs"
    os.makedirs(log_dir, exist_ok=True)
    csv_files = [f for f in os.listdir(log_dir) if f.endswith(".csv")]

    if csv_files:
        selected_file = st.selectbox("Select CSV Attendance Report", sorted(csv_files, reverse=True))
        file_path = os.path.join(log_dir, selected_file)

        df = pd.read_csv(file_path)
        st.subheader(f"Report Details: `{selected_file}`")
        st.dataframe(df, use_container_width=True)

        with open(file_path, "rb") as f:
            st.download_button(
                label="📥 Download CSV Sheet",
                data=f.read(),
                file_name=selected_file,
                mime="text/csv",
            )
    else:
        st.info("No attendance CSV records found yet. Process a video or run live webcam tracking to log attendance.")
