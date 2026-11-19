@echo off
setlocal
echo Stopping processes listening on ports 8000 and 5173...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Terminating backend process PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    echo Terminating frontend process PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo Services stopped.
