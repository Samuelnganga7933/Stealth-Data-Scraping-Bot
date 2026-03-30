"""
bot_engine.py — Central coordinator
Receives a Command, routes it to the right scraper,
returns a Path to the XLSX result
"""

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from core.command_parser import Command
from core.browser import StealthBrowser
from core.fetcher import Fetcher
from core.extractor import Extractor
from core.proxy import ProxyRotator
from scrapers.google import GoogleScraper
from scrapers.reddit import RedditScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.twitter import TwitterScraper
from scrapers.generic import GenericScraper
from intelligence import JobHunter, LeadGenerator, MarketResearcher, ConversationMiner
from automation.poster import SocialPoster
from output.xlsx_builder import XLSXBuilder


class BotEngine:
    """
    Central engine — everything flows through here.
    One execute() call per command.
    """

    def __init__(self, config: dict):
        self.config   = config
        self.proxies  = ProxyRotator(config.get("proxies", []))
        self.fetcher  = Fetcher(proxy=self.proxies.get())
        self.extractor= Extractor()
        self.xlsx     = XLSXBuilder()

        # Browser (shared instance)
        self.browser  = StealthBrowser(
            captcha_api_key=config.get("captcha_api_key"),
            headless=config.get("headless", True),
        )

        # Scrapers
        self.google   = GoogleScraper(self.fetcher, self.browser)
        self.reddit   = RedditScraper(self.fetcher, self.browser)
        self.linkedin = LinkedInScraper(self.browser, config.get("credentials", {}).get("linkedin"))
        self.twitter  = TwitterScraper(self.browser, config.get("credentials", {}).get("twitter"))
        self.generic  = GenericScraper(self.fetcher, self.browser)
        self.poster   = SocialPoster(self.browser)

        # Intelligence
        self.job_hunter   = JobHunter(self.google, self.linkedin, self.generic)
        self.lead_gen     = LeadGenerator(self.google, self.generic)
        self.market       = MarketResearcher(self.google, self.reddit, self.generic)
        self.conv_miner   = ConversationMiner(self.google, self.reddit, self.generic)

        self._started = False

    async def start(self):
        await self.browser.start()
        self._started = True
        logger.success("BotEngine ready")

    async def stop(self):
        await self.browser.stop()

    async def execute(self, cmd: Command) -> Optional[Path]:
        """Route a command to the right handler, return XLSX path."""
        if not self._started:
            await self.start()

        logger.info(f"Executing: intent={cmd.intent} query='{cmd.query}' platforms={cmd.platforms}")

        try:
            if cmd.intent == "jobs":
                return await self._handle_jobs(cmd)

            elif cmd.intent == "leads":
                return await self._handle_leads(cmd)

            elif cmd.intent == "market":
                return await self._handle_market(cmd)

            elif cmd.intent == "mine":
                return await self._handle_mine(cmd)

            elif cmd.intent in ("post", "comment"):
                return await self._handle_post(cmd)

            else:
                # Default: scrape / search
                return await self._handle_scrape(cmd)

        except Exception as e:
            logger.error(f"Execute error: {e}")
            raise

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _handle_scrape(self, cmd: Command) -> Optional[Path]:
        results = []

        # Scrape explicit URLs first
        if cmd.urls:
            scraped = await self.generic.scrape_many(cmd.urls, keywords=[cmd.query] if cmd.query else [])
            results.extend(scraped)

        # Search-based scraping per platform
        for platform in cmd.platforms:
            if platform in ("google", "web") and cmd.query:
                google_results = await self.google.search(cmd.query, pages=3)
                # Scrape top results
                for r in google_results[:10]:
                    data = await self.generic.scrape(r["url"], keywords=[cmd.query])
                    if data:
                        results.append(data)

            elif platform == "reddit" and cmd.query:
                posts = await self.reddit.search(cmd.query, limit=cmd.limit)
                extra = {"Reddit Posts": posts}
                return self.xlsx.build_from_scrape_results(results, cmd.query, extra_sheets=extra)

            elif platform in ("twitter", "x") and cmd.query:
                tweets = await self.twitter.search(cmd.query, max_tweets=cmd.limit)
                extra  = {"Tweets": tweets}
                return self.xlsx.build_from_scrape_results(results, cmd.query, extra_sheets=extra)

            elif platform == "linkedin" and cmd.query:
                people = await self.linkedin.search_people(cmd.query, limit=cmd.limit)
                extra  = {"LinkedIn People": people}
                return self.xlsx.build_from_scrape_results(results, cmd.query, extra_sheets=extra)

        if results:
            return self.xlsx.build_from_scrape_results(results, cmd.query)

        # Fallback: Google search results as rows
        if cmd.query:
            google_results = await self.google.search(cmd.query, pages=4)
            news           = await self.google.search_news(cmd.query, pages=2)
            return self.xlsx.build(
                {"Web Results": google_results, "News": news},
                filename=None,
            )

        return None

    async def _handle_jobs(self, cmd: Command) -> Optional[Path]:
        jobs = await self.job_hunter.hunt(
            query=cmd.query,
            location=cmd.location,
            limit=cmd.limit,
        )
        return self.xlsx.build_jobs_report(jobs, cmd.query)

    async def _handle_leads(self, cmd: Command) -> Optional[Path]:
        leads = await self.lead_gen.find_leads(
            industry=cmd.query,
            location=cmd.location,
            limit=cmd.limit,
        )
        return self.xlsx.build_leads_report(leads, cmd.query)

    async def _handle_market(self, cmd: Command) -> Optional[Path]:
        research = await self.market.research(cmd.query, depth=cmd.depth)
        return self.xlsx.build_market_report(research)

    async def _handle_mine(self, cmd: Command) -> Optional[Path]:
        results = await self.conv_miner.mine(cmd.query, platforms=cmd.platforms)
        return self.xlsx.build({"Conversations": results}, filename=None)

    async def _handle_post(self, cmd: Command) -> Optional[Path]:
        text  = cmd.post_text or cmd.query
        creds = self.config.get("credentials", {})
        log   = []

        for platform in cmd.platforms:
            pcreds = creds.get(platform, {})
            if not pcreds:
                log.append({"platform": platform, "status": "no credentials", "text": text})
                continue

            success = False
            if platform in ("twitter", "x"):
                success = await self.poster.twitter_post(text, pcreds)
            elif platform == "facebook":
                success = await self.poster.facebook_post(text, pcreds)
            elif platform == "linkedin":
                success = await self.poster.linkedin_post(text, pcreds)
            elif platform == "instagram":
                logger.info("Instagram posting requires an image file. Skipping text-only.")
                continue

            log.append({
                "platform": platform,
                "status":   "posted" if success else "failed",
                "text":     text[:100],
            })

        return self.xlsx.build({"Post Log": log}, filename=None) if log else None
