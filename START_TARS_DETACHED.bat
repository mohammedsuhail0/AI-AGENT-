@echo off
title TARS Voice Sentinel - Detached Launcher
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start_detached.ps1"
pause
