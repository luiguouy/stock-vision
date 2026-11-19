@echo off
setlocal
title StockVision Frontend [Vite :5173]
cd /d "%~dp0..\stage_one\frontend"

echo ==========================================================
echo   StockVision Frontend Service (Vite / Vue 3)
echo   Listening at http://localhost:5173
echo ==========================================================
echo.

call npm run dev

if errorlevel 1 (
    echo.
    echo [ERROR] Frontend exited unexpectedly. Press any key to close...
    pause >nul
)
