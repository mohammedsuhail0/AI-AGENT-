@echo off
title Restarting TARS Voice Sentinel...
cd /d "%~dp0"
echo ==============================================================
echo       🔄 RESTARTING TARS VOICE SENTINEL (IMMORTAL)
echo ==============================================================
echo.
echo Stopping any running TARS processes...
taskkill /F /FI "WINDOWTITLE eq TARS*" >nul 2>&1

powershell -Command "Get-Process python*, pythonw* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*tars*' -or $_.CommandLine -like '*call_server*' } | Stop-Process -Force" >nul 2>&1

echo Clearing ports 8080 and 5060...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 :5060" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo Launching TARS Supervisor silently in background...
cscript //nologo "%~dp0launch_tars_silent.vbs"

echo.
echo Waiting 4 seconds for SIP registration...
timeout /t 4 /nobreak >nul

echo.
echo Checking status:
netstat -ano | findstr ":8080 :5060"
echo.
echo ==============================================================
echo  ✅ TARS Voice Sentinel is ONLINE and PERMANENT!
echo  👉 Dial 'suhail_tars' from Linphone on your phone now.
echo ==============================================================
pause
