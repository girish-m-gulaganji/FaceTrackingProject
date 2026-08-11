@echo off
title VisionTrack AI - Face Intelligence Platform
color 0A

echo ===================================================================
echo   ⚡ VisionTrack AI — Enterprise Face Intelligence Platform ⚡
echo ===================================================================
echo [1/3] Checking PostgreSQL Database Service...

netstat -ano | findstr LISTENING | findstr :5432 >nul
if %errorlevel% equ 0 (
    echo [SUCCESS] PostgreSQL Database Engine is active on port 5432.
) else (
    echo [WARN] PostgreSQL service on port 5432 was not detected automatically.
    echo        Starting VisionTrack server (PostgreSQL connection will retry)...
)

echo.
echo [2/3] Starting VisionTrack Uvicorn Application Server...
start "" http://127.0.0.1:8000

echo [3/3] Running Python Server...
python server.py

pause
