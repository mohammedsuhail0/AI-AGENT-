@echo off
title TARS Voice Sentinel Status
cd /d "%~dp0"
echo ==============================================================
echo       🔍 TARS VOICE SENTINEL - STATUS CHECK
echo ==============================================================
echo.
python -c "
import urllib.request, subprocess, os, socket, requests

print('1. Checking Public IP:')
try:
    ip = requests.get('https://api.ipify.org', timeout=3).text.strip()
    print('   Current Public WAN IP:', ip)
except Exception as e:
    print('   Could not get public IP:', e)

print('\n2. Checking Active Ports (8080 HTTP & 5060 SIP):')
res = subprocess.run('netstat -ano | findstr \":8080 :5060\"', shell=True, capture_output=True, text=True)
if res.stdout.strip():
    for l in res.stdout.splitlines():
        print('   ', l)
else:
    print('   ⚠️ No processes listening on 8080 or 5060!')

print('\n3. Checking WebRTC / HTTP Health (http://127.0.0.1:8080/):')
try:
    req = urllib.request.Request('http://127.0.0.1:8080/', headers={'User-Agent': 'TARS-Check'})
    code = urllib.request.urlopen(req, timeout=3).getcode()
    print(f'   ✅ Health Check: HTTP {code} OK - TARS is alive and responding!')
except Exception as e:
    print(f'   ❌ Health Check Failed: {e}')

print('\n4. Checking Startup Auto-Launch Config:')
startup_file = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TARS_Voice_Sentinel.vbs')
if os.path.exists(startup_file):
    print('   ✅ Auto-start on Windows boot: INSTALLED AND ACTIVE')
else:
    print('   ⚠️ Auto-start not found in Startup folder!')

print('\n==============================================================')
"
pause
