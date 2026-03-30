"""
output/delivery.py — File delivery module
Send XLSX to: Google Drive, Email (SMTP), local disk
"""

import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Optional
from loguru import logger


class Delivery:
    """Send output files to configured destinations."""

    def __init__(self, config: dict):
        self.config = config

    async def deliver(self, filepath: Path, label: str = "") -> dict:
        """
        Deliver a file to all configured destinations.
        Returns dict of {destination: success/failed}
        """
        results = {}
        tasks   = []

        if self.config.get("email"):
            tasks.append(("email", self._send_email(filepath, label)))

        if self.config.get("google_drive"):
            tasks.append(("google_drive", self._upload_drive(filepath, label)))

        for name, coro in tasks:
            try:
                ok = await coro
                results[name] = "sent" if ok else "failed"
            except Exception as e:
                results[name] = f"error: {e}"

        # Always save locally
        results["local"] = str(filepath)
        logger.info(f"Delivery results: {results}")
        return results

    # ── Email ─────────────────────────────────────────────────────────────────

    async def _send_email(self, filepath: Path, label: str) -> bool:
        cfg = self.config.get("email", {})
        if not all(k in cfg for k in ("smtp_host", "smtp_port", "username", "password", "to")):
            logger.warning("Email config incomplete")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"]    = cfg["username"]
            msg["To"]      = cfg["to"]
            msg["Subject"] = f"Scraper Bot Results: {label or filepath.stem}"

            msg.attach(MIMEText(
                f"Your scrape results are attached.\n\nFile: {filepath.name}\nLabel: {label}",
                "plain"
            ))

            with open(filepath, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filepath.name}")
                msg.attach(part)

            # Run blocking SMTP in thread
            def _send():
                with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"]) as server:
                    server.login(cfg["username"], cfg["password"])
                    server.send_message(msg)

            await asyncio.get_event_loop().run_in_executor(None, _send)
            logger.success(f"Email sent to {cfg['to']}")
            return True

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    # ── Google Drive ──────────────────────────────────────────────────────────

    async def _upload_drive(self, filepath: Path, label: str) -> bool:
        """Upload file to Google Drive."""
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds_file = self.config["google_drive"].get("credentials_file")
            folder_id  = self.config["google_drive"].get("folder_id")

            if not creds_file:
                logger.warning("Google Drive credentials file not set")
                return False

            def _upload():
                creds   = Credentials.from_service_account_file(
                    creds_file,
                    scopes=["https://www.googleapis.com/auth/drive.file"],
                )
                service = build("drive", "v3", credentials=creds)
                meta    = {"name": filepath.name}
                if folder_id:
                    meta["parents"] = [folder_id]

                media = MediaFileUpload(
                    str(filepath),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                file  = service.files().create(body=meta, media_body=media, fields="id").execute()
                return file.get("id")

            file_id = await asyncio.get_event_loop().run_in_executor(None, _upload)
            logger.success(f"Uploaded to Google Drive: {file_id}")
            return bool(file_id)

        except ImportError:
            logger.warning("google-api-python-client not installed. pip install google-api-python-client")
            return False
        except Exception as e:
            logger.error(f"Google Drive upload error: {e}")
            return False
