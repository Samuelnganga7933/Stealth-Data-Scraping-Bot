"""
bot.py — Main entry point
Run with:
  python bot.py --mode cli
  python bot.py --mode telegram
  python bot.py --mode all
"""

import asyncio
import argparse
from pathlib import Path
from loguru import logger

from bot_engine import BotEngine
from core.queue import JobQueue
from interfaces.cli import CLIInterface
from interfaces.telegram_bot import TelegramInterface


# ── Config ────────────────────────────────────────────────────────────────────
# Edit this or load from .env file

CONFIG = {
    "headless": True,

    # 2captcha API key (https://2captcha.com) — $2 per 1000 CAPTCHAs
    "captcha_api_key": "",

    # Proxy list (optional — leave empty to run without proxies)
    # Format: "http://user:pass@ip:port" or "http://ip:port"
    "proxies": [],

    # Your social media credentials (add only what you need)
    "credentials": {
        "twitter": {
            "username": "",
            "password": "",
        },
        "facebook": {
            "username": "",  # email
            "password": "",
        },
        "instagram": {
            "username": "",
            "password": "",
        },
        "linkedin": {
            "username": "",  # email
            "password": "",
        },
        "youtube": {
            "username": "",  # Google email
            "password": "",
        },
    },

    # Telegram bot token (from @BotFather)
    "telegram_token": "",
}


async def main():
    parser = argparse.ArgumentParser(description="Scraper Bot")
    parser.add_argument("--mode", choices=["cli", "telegram", "all"], default="cli")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    CONFIG["headless"] = args.headless

    # Core
    queue  = JobQueue(max_workers=3)
    engine = BotEngine(CONFIG)

    await queue.start()
    await engine.start()

    logger.success("Bot started")

    try:
        if args.mode == "cli":
            cli = CLIInterface(queue, engine)
            await cli.run()

        elif args.mode == "telegram":
            if not CONFIG["telegram_token"]:
                logger.error("Set telegram_token in CONFIG")
                return
            tg = TelegramInterface(CONFIG["telegram_token"], queue, engine)
            await tg.start()
            logger.info("Press Ctrl+C to stop")
            await asyncio.Event().wait()

        elif args.mode == "all":
            tasks = []
            cli = CLIInterface(queue, engine)
            tasks.append(asyncio.create_task(cli.run()))

            if CONFIG["telegram_token"]:
                tg = TelegramInterface(CONFIG["telegram_token"], queue, engine)
                await tg.start()

            await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await queue.stop()
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
