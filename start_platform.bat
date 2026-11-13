@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   StockVision - One-Click Launcher (Desktop Mode)
echo ==========================================================
echo.

if exist .venv\Scripts\python.exe (
    start "" ".venv\Scripts\python.exe" "stage_one\backend\desktop_main.py"
) else (
    start "" python "stage_one\backend\desktop_main.py"
)
