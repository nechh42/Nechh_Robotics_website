"""
supervisor.py - Process-Level Auto-Restart Supervisor
=======================================================
Keeps main.py alive. Crash → restart + Telegram alert.
Run this for production instead of main.py.

Usage: python supervisor.py
"""

import subprocess
import sys
import os
import time
import signal
import logging
import requests
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "supervisor.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("supervisor")


def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = _load_env()
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")
MAX_RESTARTS = 50
RESTART_DELAY = 10
CRASH_COOLDOWN = 300
MAX_DELAY = 120


def _telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


class Supervisor:
    def __init__(self):
        self.restarts = 0
        self.proc = None
        self.running = True
        self.start_time = datetime.now()
        self.last_crash = None
        self.delay = RESTART_DELAY
        self.main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        self.engine_log = os.path.join(LOG_DIR, f"engine_{datetime.now():%Y%m%d_%H%M%S}.log")

    def run(self):
        logger.info("=" * 50)
        logger.info("SUPERVISOR STARTING")
        logger.info(f"Engine: {self.main_py}")
        logger.info(f"Telegram: {'ON' if BOT_TOKEN else 'OFF'}")
        logger.info("=" * 50)

        try:
            _telegram("🟢 <b>WAR MACHINE SUPERVISOR STARTED</b>")
        except Exception:
            pass

        signal.signal(signal.SIGINT, lambda *_: self._stop())
        signal.signal(signal.SIGTERM, lambda *_: self._stop())

        while self.running and self.restarts < MAX_RESTARTS:
            logger.info(f"Starting engine (attempt #{self.restarts + 1})")
            try:
                log_f = open(self.engine_log, "a", encoding="utf-8")
                self.proc = subprocess.Popen(
                    [sys.executable, self.main_py],
                    cwd=os.path.dirname(self.main_py),
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                )
                logger.info(f"Engine PID {self.proc.pid}")
            except Exception as e:
                logger.error(f"Failed to start: {e}")
                self.restarts += 1
                time.sleep(self.delay)
                continue

            start = datetime.now()
            while self.running:
                code = self.proc.poll()
                if code is not None:
                    runtime = (datetime.now() - start).total_seconds()
                    logger.error(f"Engine exited code={code} after {runtime:.0f}s")
                    crash_info = self._last_log_lines()
                    _telegram(
                        f"🔴 <b>ENGINE CRASHED</b>\n"
                        f"Code: {code}\nRuntime: {runtime:.0f}s\n"
                        f"Restart #{self.restarts+1}\n"
                        f"<code>{crash_info[:200]}</code>"
                    )
                    break
                time.sleep(5)

            if not self.running:
                break

            # Backoff
            now = datetime.now()
            if self.last_crash and (now - self.last_crash).total_seconds() < CRASH_COOLDOWN:
                self.delay = min(self.delay * 2, MAX_DELAY)
            else:
                self.delay = RESTART_DELAY
            self.last_crash = now
            self.restarts += 1

            self.engine_log = os.path.join(LOG_DIR, f"engine_{datetime.now():%Y%m%d_%H%M%S}.log")
            logger.info(f"Restarting in {self.delay}s (#{self.restarts}/{MAX_RESTARTS})")
            time.sleep(self.delay)

        if self.restarts >= MAX_RESTARTS:
            _telegram(f"🚨 <b>SUPERVISOR STOPPED - MAX RESTARTS ({MAX_RESTARTS})</b>")
        else:
            _telegram("🟡 <b>SUPERVISOR STOPPED BY USER</b>")

        self._kill()
        logger.info("Supervisor exited")

    def _stop(self):
        self.running = False
        self._kill()

    def _kill(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _last_log_lines(self):
        try:
            with open(self.engine_log, "r", encoding="utf-8") as f:
                return "\n".join(f.readlines()[-5:]).strip()
        except Exception:
            return "No log"


if __name__ == "__main__":
    Supervisor().run()
