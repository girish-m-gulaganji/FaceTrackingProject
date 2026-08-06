@echo off
title VisionTrack AI - Face Tracking & Attendance Platform
echo ========================================================
echo   Starting VisionTrack AI Engine & Web Dashboard
echo ========================================================
cd /d "%~dp0"
echo [INFO] Opening Browser at http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"
echo [INFO] Starting FastAPI Uvicorn Server on port 8000 (accessible on LAN)...
uvicorn server:app --host 0.0.0.0 --port 8000
pause
