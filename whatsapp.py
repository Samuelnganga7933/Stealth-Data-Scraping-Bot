"""
interfaces/whatsapp.py — WhatsApp interface via WPPConnect
Connects YOUR WhatsApp number directly (scan QR once)
Receives commands, sends back XLSX files
Requires: Node.js + WPPConnect server running locally

SETUP:
1. Install Node.js (https://nodejs.org)
2. In a terminal run:
      npx @wppconnect-team/wppconnect-server
3. Scan the QR code with your WhatsApp
4. Run this bot — it connects to the local WPPConnect server
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from core.command_parser import CommandParser
from core.queue import JobQueue, Job, JobStatus


WPPCONNECT_BASE = "http://localhost:21465"
SESSION_NAME    = "scraperbot"


class WhatsAppInterface:
    """
    Polls WPPConnect server for new messages,
    parses them as commands, sends back XLSX files.
    """

    def __init__(self, queue: JobQueue, bot_engine, secret_key: str = "THISISMYSECURETOKEN"):
        self.queue      = queue
        self.engine     = bot_engine
        self.parser     = CommandParser()
        self.secret     = secret_key
        self._token: Optional[str] = None
        self._running   = False
        self._seen_ids: set = set()

    async def start(self):
        if not HTTPX_AVAILABLE:
            logger.error("httpx not installed")
            return

        logger.info("Starting WhatsApp interface (WPPConnect)...")

        # Generate session token
        await self._generate_token()
        if not self._token:
            logger.error("Could not get WPPConnect token. Is the server running?")
            logger.info("Start it with: npx @wppconnect-team/wppconnect-server")
            return

        # Start the session (shows QR if not already connected)
        await self._start_session()
        self._running = True

        logger.success("WhatsApp interface running — polling for messages")
        await self._poll_loop()

    async def stop(self):
        self._running = False

    # ── Token + session ───────────────────────────────────────────────────────

    async def _generate_token(self):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/{self.secret}/generate-token"
                )
                data = r.json()
                self._token = data.get("token")
                logger.info(f"WPPConnect token: {'OK' if self._token else 'FAILED'}")
        except Exception as e:
            logger.error(f"WPPConnect token error: {e}")

    async def _start_session(self):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/start-session",
                    headers=self._headers(),
                    json={"webhook": None, "waitQrCode": True},
                )
                data = r.json()
                status = data.get("status", "")
                logger.info(f"WPPConnect session status: {status}")
                if status == "QRCODE":
                    logger.info("Scan the QR code in your terminal / WPPConnect UI")
        except Exception as e:
            logger.error(f"WPPConnect session start error: {e}")

    # ── Message polling ───────────────────────────────────────────────────────

    async def _poll_loop(self):
        """Poll for new messages every 3 seconds."""
        while self._running:
            try:
                messages = await self._fetch_unread()
                for msg in messages:
                    await self._handle_message(msg)
            except Exception as e:
                logger.error(f"Poll error: {e}")
            await asyncio.sleep(3)

    async def _fetch_unread(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/get-all-messages-in-chat",
                    headers=self._headers(),
                    params={"id": "status@broadcast", "isGroup": False, "includeMe": False},
                )
                # Try unread messages endpoint
                r2 = await client.get(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/check-connection-session",
                    headers=self._headers(),
                )
                if r2.json().get("status") != "Connected":
                    return []

                # Get all chats with unread
                r3 = await client.get(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/get-all-chats-with-messages",
                    headers=self._headers(),
                )
                chats = r3.json().get("response", [])
                messages = []
                for chat in chats:
                    for msg in chat.get("messages", {}).get("messages", []):
                        mid = msg.get("id", {}).get("id", "")
                        if mid and mid not in self._seen_ids and not msg.get("fromMe"):
                            self._seen_ids.add(mid)
                            messages.append({
                                "id":      mid,
                                "from":    msg.get("from", ""),
                                "body":    msg.get("body", ""),
                                "chat_id": chat.get("id", {}).get("_serialized", ""),
                            })
                return messages
        except Exception as e:
            logger.debug(f"Fetch messages error: {e}")
            return []

    async def _handle_message(self, msg: dict):
        text    = msg.get("body", "").strip()
        chat_id = msg.get("chat_id", "") or msg.get("from", "")

        if not text or not chat_id:
            return

        logger.info(f"WhatsApp message from {chat_id}: {text[:60]}")

        # Parse command
        cmd = self.parser.parse(text)

        # Send acknowledgement
        await self._send_message(
            chat_id,
            f"⚡ On it: *{cmd.intent}* — _{cmd.query or text[:40]}_\n"
            f"Platforms: {', '.join(cmd.platforms)}\n"
            "Working on it, will send file when done..."
        )

        async def notify(job: Job):
            await self._notify_job_done(job, chat_id)

        await self.queue.submit(
            name=f"{cmd.intent}: {cmd.query or text[:30]}",
            coro_fn=self.engine.execute,
            args=(cmd,),
            notify_fn=notify,
        )

    async def _notify_job_done(self, job: Job, chat_id: str):
        if job.status == JobStatus.DONE and job.result:
            await self._send_message(chat_id, f"✅ Done: *{job.name}*")
            if isinstance(job.result, Path) and job.result.exists():
                await self._send_file(chat_id, job.result)
        elif job.status == JobStatus.FAILED:
            await self._send_message(chat_id, f"❌ Failed: *{job.name}*\n{job.error}")

    async def _send_message(self, chat_id: str, text: str):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/send-message",
                    headers=self._headers(),
                    json={"phone": chat_id, "message": text, "isGroup": False},
                )
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")

    async def _send_file(self, chat_id: str, filepath: Path):
        """Send an XLSX file back via WhatsApp."""
        try:
            import base64
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{WPPCONNECT_BASE}/api/{SESSION_NAME}/send-file-base64",
                    headers=self._headers(),
                    json={
                        "phone":    chat_id,
                        "filename": filepath.name,
                        "base64":   f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}",
                        "caption":  f"📊 {filepath.stem}",
                    },
                )
            logger.success(f"WhatsApp file sent: {filepath.name} → {chat_id}")
        except Exception as e:
            logger.error(f"WhatsApp file send error: {e}")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type":  "application/json",
        }
