"""
interfaces/telegram_bot.py — Telegram command interface
Send commands, receive XLSX files back
"""

import asyncio
from pathlib import Path
from loguru import logger

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed")

from core.command_parser import CommandParser
from core.queue import JobQueue, Job, JobStatus


class TelegramInterface:

    def __init__(self, token: str, queue: JobQueue, bot_engine):
        self.token      = token
        self.queue      = queue
        self.engine     = bot_engine   # BotEngine instance
        self.parser     = CommandParser()
        self.app        = None
        self._chat_ids: set[int] = set()

    async def start(self):
        if not TELEGRAM_AVAILABLE:
            logger.error("Install python-telegram-bot: pip install python-telegram-bot")
            return

        self.app = Application.builder().token(self.token).build()

        self.app.add_handler(CommandHandler("start",  self._cmd_start))
        self.app.add_handler(CommandHandler("help",   self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("stop",   self._cmd_stop))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        logger.info("Telegram bot starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.success("Telegram bot running")

    async def stop(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()

    async def send_message(self, chat_id: int, text: str):
        if self.app:
            await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

    async def send_file(self, chat_id: int, filepath: Path, caption: str = ""):
        if self.app:
            with open(filepath, "rb") as f:
                await self.app.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=filepath.name,
                    caption=caption,
                )

    async def notify_job_done(self, job: Job, chat_id: int):
        if job.status == JobStatus.DONE and job.result:
            await self.send_message(chat_id, f"✅ Job `{job.name}` done!")
            if isinstance(job.result, Path) and job.result.exists():
                await self.send_file(chat_id, job.result, f"Results: {job.name}")
        elif job.status == JobStatus.FAILED:
            await self.send_message(chat_id, f"❌ Job `{job.name}` failed: {job.error}")

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self._chat_ids.add(update.effective_chat.id)
        await update.message.reply_text(
            "🤖 *Scraper Bot Online*\n\n"
            "Just type naturally:\n"
            "• `scrape linkedin for python jobs in Nairobi`\n"
            "• `find fintech leads in Kenya`\n"
            "• `search twitter for posts about Safaricom`\n"
            "• `market research on solar energy Africa`\n"
            "• `post on twitter: Hello world`\n\n"
            "Use /help for full command list.",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "*Commands:*\n"
            "`/status` — show running jobs\n"
            "`/stop` — stop all jobs\n\n"
            "*Examples:*\n"
            "• `scrape https://example.com`\n"
            "• `find 50 software engineer jobs Nairobi`\n"
            "• `leads in real estate Kenya`\n"
            "• `research cryptocurrency market`\n"
            "• `search reddit for remote work tips`\n"
            "• `post on linkedin: Excited to share...`",
            parse_mode="Markdown",
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        jobs = self.queue.all_jobs()
        if not jobs:
            await update.message.reply_text("No jobs in queue.")
            return
        lines = []
        for j in jobs[-10:]:
            icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(j.status, "•")
            lines.append(f"{icon} `{j.id}` {j.name} — {j.status}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏹ Stopping all jobs...")
        await self.queue.stop()

    async def _handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text    = update.message.text.strip()
        self._chat_ids.add(chat_id)

        cmd = self.parser.parse(text)
        await update.message.reply_text(
            f"⚡ Got it: *{cmd.intent}* — `{cmd.query or text[:40]}`\n"
            f"Platforms: {', '.join(cmd.platforms)}\n"
            "Running in background, will send file when done...",
            parse_mode="Markdown",
        )

        async def notify(job: Job):
            await self.notify_job_done(job, chat_id)

        await self.queue.submit(
            name=f"{cmd.intent}: {cmd.query or text[:30]}",
            coro_fn=self.engine.execute,
            args=(cmd,),
            notify_fn=notify,
        )
