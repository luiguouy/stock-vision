@echo off
setlocal
cd /d "%~dp0"

rem 用 pythonw.exe 启动：无控制台窗口；日志写入 stage_one\backend\logs\desktop.log
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "stage_one\backend\desktop_main.py"
) else (
    start "" pythonw "stage_one\backend\desktop_main.py"
)
