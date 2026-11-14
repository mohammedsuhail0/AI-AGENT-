@echo off
title TARS Voice Sentinel Server (Global Cellular + Local Wi-Fi)
cd /d "%~dp0"
echo ==============================================================
echo       🚀 TARS VOICE SENTINEL - GLOBAL CELLULAR ENGINE
echo ==============================================================
echo.
echo Starting Local Backend Server on port 8080...
start /b python call_server.py

echo.
echo Starting Cloudflare Secure Global Tunnel...
echo.
"%~dp0cloudflared.exe" tunnel --url http://localhost:8080

pause
