---
title: VisionTrack AI Face Tracking Platform
emoji: ⚡
colorFrom: yellow
colorTo: amber
sdk: docker
app_port: 7860
pinned: false
---

# ⚡ VisionTrack AI — Real-Time Face Recognition, IoU Tracking & Attendance Platform

[![Python](https://img.shields.io/badge/Python-3.12-yellow.svg)](https://www.python.org/)
[![InsightFace](https://img.shields.io/badge/AI_Engine-InsightFace_ArcFace-gold.svg)](https://github.com/deepinsight/insightface)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-orange.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite_3-yellowgreen.svg)](https://sqlite.org/)
[![Hugging Face](https://img.shields.io/badge/Spaces-Hugging_Face-yellow.svg)](https://huggingface.co/spaces)

An enterprise-grade, real-time face recognition and multi-object tracking attendance platform powered by **InsightFace ArcFace (512-D deep feature embeddings)**, **IoU Multi-Object Tracking**, an **SQLite Relational Database**, **ReportLab PDF Report Generation**, and a **Gold/Cyberpunk Glassmorphic Single Page Application**.

Developed by **[Girish M Gulaganji](https://github.com/girish-m-gulaganji)**.

---

## ✨ Key Features

* **🤖 InsightFace Deep Learning Engine**: Uses 512-dimensional ArcFace cosine similarity feature vectors (`buffalo_l` model) for sub-second recognition accuracy.
* **🎯 IoU Multi-Object Tracking**: Maintains persistent tracking IDs (`#0`, `#1`, etc.) across consecutive video frames to prevent label flickering.
* **📦 Bulk Multi-File & Snapshot Registration**: Register single or bulk face photos at once with automatic name extraction from filenames.
* **📄 Automated PDF & CSV Attendance Reports**: Generate downloadable, formatted PDF summary reports with official header timestamps, attendee counts, and data tables.
* **🗄️ Dual-Database Architecture**:
  * **SQLite 3 (`visiontrack.db`)**: Stores person records (Department, Role, Vector count), attendance history logs, and system audit events.
  * **NumPy Vector Store (`embeddings.npz`)**: High-dimensional vector database for fast AI matching.
* **🔒 Admin Portal & Session Security**: Secure Admin Login Portal with session management and top-bar authentication controls.
* **🟡 Cyberpunk Gold UI Dashboard**: Modern Single Page Web UI with live camera feed recognition, video tracking progress, dark glassmorphism styling, and gold glow accents.
* **🌐 VPS & Docker Ready**: Includes 1-click Linux VPS installer (`deploy_vps.sh`) and Docker Compose configuration.

---

## 🛠️ Tech Stack

- **AI Core**: InsightFace, ONNX Runtime, OpenCV
- **Backend API**: Python 3.12, FastAPI, Uvicorn, ReportLab
- **Database**: SQLite 3, NumPy
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System), JavaScript (Fetch API / DOM)
- **Deployment**: Linux VPS (Nginx + Systemd), Hugging Face Spaces, Docker

---

## 🌐 Linux VPS Deployment (DigitalOcean / AWS / Linode / Hostinger)

Connect to your Linux server via SSH and run:

```bash
curl -sSL https://raw.githubusercontent.com/girish-m-gulaganji/FaceTrackingProject/main/deploy_vps.sh | bash
```

The script will automatically install dependencies, set up Nginx reverse proxy, configure systemd auto-restart service, and launch your dashboard live on your VPS IP address!

---

## 🚀 Local Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/girish-m-gulaganji/FaceTrackingProject.git
cd FaceTrackingProject
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Platform
```bash
# Windows 1-Click: double-click start_server.bat
uvicorn server:app --host 0.0.0.0 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 🔑 Default Admin Credentials

- **Username**: `admin`
- **Password**: `admin123`

---

## 👤 Author & Maintainer

**Girish M Gulaganji**  
* GitHub: [@girish-m-gulaganji](https://github.com/girish-m-gulaganji)
