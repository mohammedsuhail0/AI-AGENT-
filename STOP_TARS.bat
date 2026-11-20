@echo off
title Stopping TARS Voice Sentinel...
cd /d "%~dp0"
echo ==============================================================
echo       🛑 STOPPING TARS VOICE SENTINEL
echo ==============================================================
echo.
powershell -Command "Get-Process python*, pythonw* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*tars*' -or $_.CommandLine -like '*call_server*' } | Stop-Process -Force" >nul 2>&1

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 :5060" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ✅ TARS Voice Sentinel has been stopped.
pause
