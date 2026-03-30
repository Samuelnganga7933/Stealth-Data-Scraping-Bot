"""
interfaces/cli.py — Terminal command interface
Run the bot from your terminal directly
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger

from core.command_parser import CommandParser
from core.queue import JobQueue


class CLIInterface:

    def __init__(self, queue: JobQueue, bot_engine):
        self.queue  = queue
        self.engine = bot_engine
        self.parser = CommandParser()

    async def run(self):
        print("\n" + "="*50)
        print("  SCRAPER BOT — Terminal Mode")
        print("="*50)
        print("Type a command or 'help' or 'quit'\n")

        while True:
            try:
                text = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not text:
                continue

            if text.lower() in ("quit", "exit", "q"):
                print("Bye!")
                break

            if text.lower() == "help":
                self._print_help()
                continue

            if text.lower() == "status":
                self._print_status()
                continue

            cmd = self.parser.parse(text)
            print(f"  Intent:    {cmd.intent}")
            print(f"  Query:     {cmd.query}")
            print(f"  Platforms: {', '.join(cmd.platforms)}")
            print(f"  Location:  {cmd.location or 'any'}")
            print(f"  Depth:     {cmd.depth}")
            print(f"  Limit:     {cmd.limit}")
            print("  Running...\n")

            try:
                result = await self.engine.execute(cmd)
                if isinstance(result, Path):
                    print(f"  ✅ Saved: {result}\n")
                else:
                    print(f"  ✅ Done\n")
            except Exception as e:
                print(f"  ❌ Error: {e}\n")

    def _print_help(self):
        print("""
  EXAMPLES:
  scrape https://example.com
  scrape linkedin for python jobs in Nairobi
  deep scrape twitter for posts about KCB Bank
  find 100 fintech leads in Kenya
  jobs data analyst Nairobi
  market research on mobile money East Africa
  search reddit for remote work opportunities
  post on twitter: Hello world
  post on linkedin: Excited to announce...
  post on facebook: Check this out!
""")

    def _print_status(self):
        jobs = self.queue.all_jobs()
        if not jobs:
            print("  No jobs.\n")
            return
        for j in jobs[-10:]:
            icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(j.status, "•")
            print(f"  {icon} [{j.id}] {j.name} — {j.status}")
        print()
