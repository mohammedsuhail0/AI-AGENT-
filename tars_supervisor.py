"""
TARS Autonomous Supervisor & Immortal Watchdog
- Keeps TARS Voice Sentinel running 24/7/365.
- Automatically cleans stale ports (8080, 5060) on startup.
- Automatically restarts call_server.py if it exits or crashes.
- Performs periodic HTTP health-checks.
- Designed to run permanently via Windows Task Scheduler or Windows Startup.
"""

import os
import sys
import time
import socket
import logging
import subprocess
import urllib.request

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "tars_supervisor.log")
SERVER_LOG = os.path.join(LOG_DIR, "tars_server.log")

handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
try:
    if sys.stdout is not None and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        handlers.append(logging.StreamHandler(sys.stdout))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=handlers
)
logger = logging.getLogger("TARS-Supervisor")


def kill_proc_on_port(port: int):
    """Frees port if an orphaned process is holding it on Windows."""
    try:
        cmd = f'netstat -ano | findstr ":{port} "'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        my_pid = os.getpid()
        for line in res.stdout.splitlines():
            if "LISTENING" in line or f":{port}" in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != my_pid and int(pid) != 0:
                        logger.info(f"Killing stale process {pid} occupying port {port}...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception as e:
        logger.warning(f"Could not clear port {port}: {e}")


def is_server_healthy() -> bool:
    """Checks if call_server is responding on HTTP port 8080."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/", headers={"User-Agent": "TARS-Supervisor"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.getcode() == 200
    except Exception:
        return False


def main():
    logger.info("=======================================================")
    logger.info("🤖 TARS IMMORTAL SUPERVISOR ACTIVATED")
    logger.info(f"Directory: {LOG_DIR}")
    logger.info(f"Python interpreter: {sys.executable}")
    logger.info("=======================================================")

    os.chdir(LOG_DIR)
    python_exe = r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe"
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    while True:
        # 1. Clean stale ports
        kill_proc_on_port(8080)
        kill_proc_on_port(5060)
        time.sleep(1)

        logger.info("🚀 Launching TARS Voice Call Server (call_server.py)...")
        out_f = open(SERVER_LOG, "a", encoding="utf-8")
        out_f.write(f"\n--- TARS SERVER START: {time.ctime()} ---\n")
        out_f.flush()

        proc = subprocess.Popen(
            [python_exe, "-u", "call_server.py"],
            cwd=LOG_DIR,
            stdout=out_f,
            stderr=subprocess.STDOUT
        )

        logger.info(f"✅ TARS call_server.py started with PID {proc.pid}")

        # Wait a few seconds for startup
        time.sleep(8)

        failed_checks = 0
        while True:
            # Check if process is still running
            ret = proc.poll()
            if ret is not None:
                logger.error(f"⚠️ TARS call_server.py exited unexpectedly with code {ret}!")
                break

            # Health-check every 30 seconds
            time.sleep(30)
            if not is_server_healthy():
                failed_checks += 1
                logger.warning(f"Health-check failed ({failed_checks}/3)...")
                if failed_checks >= 3:
                    logger.error("❌ Server unresponsive for 3 consecutive checks. Recycling...")
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()
                    break
            else:
                failed_checks = 0

        try:
            out_f.close()
        except Exception:
            pass

        logger.info("🔄 Auto-restarting TARS in 3 seconds...")
        time.sleep(3)


if __name__ == "__main__":
    main()
