@echo off
setlocal
title StockVision Backend [FastAPI :8000]
cd /d "%~dp0..\stage_one\backend"

echo ==========================================================
echo   StockVision Backend Service (FastAPI / Uvicorn)
echo   Listening at http://127.0.0.1:8000
echo ==========================================================
echo.

if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
)

if errorlevel 1 (
    echo.
    echo [ERROR] Backend exited unexpectedly. Press any key to close...
    pause >nul
)
