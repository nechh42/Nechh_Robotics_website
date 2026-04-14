"""
watchdog.py - Windows Gardiyan (Task Scheduler ile çalışır)
=============================================================
Her 5 dakikada bir çalışır:
  1. supervisor.py çalışıyor mu kontrol eder
  2. Çalışmıyorsa yeniden başlatır
  3. Telegram'a bildirim gönderir

Kurulum (1 kez):
  python watchdog.py --install

Kaldırma:
  python watchdog.py --uninstall

Manuel test:
  python watchdog.py --check
"""

import subprocess
import sys
import os
import logging
import argparse
import requests
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "watchdog.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("watchdog")

TASK_NAME = "WarMachineWatchdog"
SUPERVISOR_PY = os.path.join(SCRIPT_DIR, "supervisor.py")


def _load_env():
    env_path = os.path.join(SCRIPT_DIR, ".env")
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


def is_supervisor_running() -> bool:
    """supervisor.py çalışıyor mu? (PID dosyası + proses kontrol)"""
    pid_file = os.path.join(SCRIPT_DIR, "logs", "supervisor.pid")

    # Yöntem 1: PID dosyasından kontrol
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            # PID gerçekten yaşıyor mu?
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, encoding="cp857", errors="replace", timeout=10
            )
            if str(pid) in result.stdout:
                return True
        except Exception:
            pass

    # Yöntem 2: Tüm python proseslerinde supervisor.py ara
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=15
        )
        return "supervisor.py" in result.stdout
    except Exception as e:
        logger.error(f"Process kontrol hatası: {e}")
        return False


def start_supervisor():
    """supervisor.py'yi arka planda başlat"""
    try:
        proc = subprocess.Popen(
            [sys.executable, SUPERVISOR_PY],
            cwd=SCRIPT_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"Supervisor başlatıldı PID={proc.pid}")
        return proc.pid
    except Exception as e:
        logger.error(f"Supervisor başlatma hatası: {e}")
        return None


def check_and_restart():
    """Ana kontrol döngüsü"""
    if is_supervisor_running():
        logger.info("OK - Supervisor çalışıyor")
        return

    logger.warning("ALERT - Supervisor çalışmıyor! Yeniden başlatılıyor...")
    pid = start_supervisor()

    if pid:
        _telegram(
            f"🛡️ <b>WATCHDOG: Sistem yeniden başlatıldı</b>\n"
            f"Supervisor PID: {pid}\n"
            f"Zaman: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"Sebep: Proses bulunamadı"
        )
        logger.info(f"Supervisor yeniden başlatıldı PID={pid}")
    else:
        _telegram(
            "🚨 <b>WATCHDOG: Sistem başlatılamadı!</b>\n"
            "Manuel müdahale gerekiyor."
        )
        logger.error("Supervisor başlatılamadı!")


def install_task():
    """Windows Task Scheduler'a gardiyan görevi ekle"""
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)

    # Önce varsa sil
    subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, encoding="cp857", errors="replace"
    )

    # pythonw.exe kullan (pencere açmaz)
    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = python_exe  # fallback

    # Her 5 dakikada çalışan görev oluştur (pencere açmadan)
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{ pythonw_exe}" "{script_path}" --check',
        "/SC", "MINUTE",
        "/MO", "5",
        "/F",
    ]

    result = subprocess.run(cmd, capture_output=True, encoding="cp857", errors="replace")
    if result.returncode == 0:
        logger.info(f"Task Scheduler görevi oluşturuldu: {TASK_NAME}")
        logger.info("Her 5 dakikada supervisor kontrol edilecek")
        print(f"\n✅ Gardiyan kuruldu: '{TASK_NAME}'")
        print("   Her 5 dakikada supervisor kontrol edilecek")
        print("   Sistem çöktüğünde otomatik yeniden başlatılacak")
        print("   Telegram bildirimi gönderilecek")
    else:
        logger.error(f"Task oluşturulamadı: {result.stderr}")
        print(f"\n❌ Hata: {result.stderr}")
        print("   Admin olarak çalıştırmayı deneyin")


def uninstall_task():
    """Task Scheduler'dan gardiyan görevini kaldır"""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, encoding="cp857", errors="replace"
    )
    if result.returncode == 0:
        logger.info(f"Task silindi: {TASK_NAME}")
        print(f"✅ Gardiyan kaldırıldı: '{TASK_NAME}'")
    else:
        print(f"❌ Hata: {result.stderr}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="War Machine Watchdog")
    parser.add_argument("--install", action="store_true", help="Task Scheduler'a kur")
    parser.add_argument("--uninstall", action="store_true", help="Task Scheduler'dan kaldır")
    parser.add_argument("--check", action="store_true", help="Kontrol et, gerekirse başlat")
    args = parser.parse_args()

    if args.install:
        install_task()
    elif args.uninstall:
        uninstall_task()
    elif args.check:
        check_and_restart()
    else:
        parser.print_help()
