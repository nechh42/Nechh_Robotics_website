"""
main.py - War Machine Entry Point
====================================
Start the trading engine directly.
For production, use supervisor.py instead.
"""

import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from engine.orchestrator import Orchestrator

os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.LOG_DIR, "engine.log"), encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)


async def start_engine():
    orch = Orchestrator()
    try:
        await orch.start()
    except Exception as e:
        logger.error(f"Çalışma Hatası: {e}", exc_info=True)
    finally:
        await orch.stop()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(start_engine())
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)