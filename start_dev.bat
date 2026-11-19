@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   StockVision - Starting Web Development Environment...
echo ==========================================================
echo.

echo [1/3] Starting Backend (FastAPI @ http://127.0.0.1:8000)...
start "StockVision Backend" cmd /k "%~dp0scripts\run_backend.bat"

echo [2/3] Starting Frontend (Vite @ http://localhost:5173)...
start "StockVision Frontend" cmd /k "%~dp0scripts\run_frontend.bat"

echo [3/3] Waiting for Backend to be fully ready...
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import time, urllib.request; [time.sleep(0.5) for _ in range(20) if not (lambda: [True for _ in [1] if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1).status == 200])()]" 2>nul
) else (
    ping 127.0.0.1 -n 4 >nul
)

echo Opening browser at http://localhost:5173...
start http://localhost:5173

echo.
echo ==========================================================
echo   Web Development Environment Ready!
echo   - Frontend: http://localhost:5173
echo   - API Docs: http://127.0.0.1:8000/docs
echo ==========================================================
