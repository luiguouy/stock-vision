@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   StockVision - Windows Desktop Launcher (Edge WebView2)
echo ==========================================================
echo.

if exist .venv\Scripts\python.exe (
    start "" ".venv\Scripts\python.exe" "stage_one\backend\desktop_main.py"
) else (
    start "" python "stage_one\backend\desktop_main.py"
)
