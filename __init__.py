"""
intelligence/ — Jobs, leads, market research, conversation mining
Coordinates multiple scrapers to build intelligence reports
"""

import asyncio
from dataclasses import dataclass, field
from loguru import logger

from scrapers.google import GoogleScraper
from scrapers.reddit import RedditScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.generic import GenericScraper
from core.extractor import Extractor


# ── Job Hunter ────────────────────────────────────────────────────────────────

JOB_SITES = [
    "https://www.indeed.com/jobs?q={query}&l={location}",
    "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}",
    "https://remoteok.com/?q={query}",
    "https://weworkremotely.com/remote-jobs/search?term={query}",
    "https://ng.jobberman.com/listings?q={query}",          # Africa
    "https://ke.linkedin.com/jobs/search?keywords={query}", # Kenya
    "https://brightermonday.co.ke/listings?q={query}",      # Kenya
    "https://myjobmag.co.ke/?s={query}",                    # Kenya
]


class JobHunter:
    def __init__(self, google: GoogleScraper, linkedin: LinkedInScraper, generic: GenericScraper):
        self.google   = google
        self.linkedin = linkedin
        self.generic  = generic

    async def hunt(self, query: str, location: str = "", limit: int = 100) -> list[dict]:
        """Hunt for jobs across all platforms simultaneously."""
        logger.info(f"Job hunt: '{query}' in '{location or 'anywhere'}'")
        tasks = [
            self.google.search_jobs(query, location),
            self.linkedin.search_jobs(query, location, limit=50),
            self._scrape_job_sites(query, location),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        jobs    = []
        for r in results:
            if isinstance(r, list):
                jobs.extend(r)

        # Deduplicate by title + company
        seen  = set()
        dedup = []
        for j in jobs:
            key = (j.get("title","") + j.get("company","")).lower()[:60]
            if key and key not in seen:
                seen.add(key)
                dedup.append(j)

        logger.success(f"Job hunt complete: {len(dedup)} unique jobs found")
        return dedup[:limit]

    async def _scrape_job_sites(self, query: str, location: str) -> list[dict]:
        from urllib.parse import quote_plus
        jobs = []
        for site_tpl in JOB_SITES[:4]:
            url  = site_tpl.format(query=quote_plus(query), location=quote_plus(location))
            data = await self.generic.scrape(url, keywords=[query])
            if data:
                for link in data.links[:10]:
                    if any(kw in link.lower() for kw in ["job","career","listing","vacancy"]):
                        jobs.append({"url": link, "source": "job_site"})
            await asyncio.sleep(2)
        return jobs


# ── Lead Generator ────────────────────────────────────────────────────────────

class LeadGenerator:
    def __init__(self, google: GoogleScraper, generic: GenericScraper):
        self.google  = google
        self.generic = generic
        self.ext     = Extractor()

    async def find_leads(self, industry: str, location: str = "", limit: int = 100) -> list[dict]:
        """Find company leads in an industry — emails, phones, websites."""
        logger.info(f"Lead gen: {industry} in {location or 'any location'}")
        query   = f"{industry} companies {location} contact email".strip()
        results = await self.google.search(query, pages=5)
        leads   = []

        for r in results[:30]:
            url  = r.get("url", "")
            if not url:
                continue
            data = await self.generic.scrape(url, keywords=[industry])
            if data:
                if data.emails or data.phones:
                    leads.append({
                        "company":     data.title or r.get("title",""),
                        "website":     url,
                        "emails":      ", ".join(data.emails[:3]),
                        "phones":      ", ".join(data.phones[:3]),
                        "description": (data.description or "")[:200],
                        "source":      "lead_gen",
                    })
            await asyncio.sleep(1.5)

        logger.success(f"Lead gen: {len(leads)} leads found")
        return leads[:limit]

    async def find_emails_for_domain(self, domain: str) -> list[str]:
        """Hunt for all emails associated with a domain."""
        emails = set()
        pages  = [
            f"https://{domain}",
            f"https://{domain}/contact",
            f"https://{domain}/about",
            f"https://{domain}/team",
            f"https://{domain}/contact-us",
        ]
        for url in pages:
            data = await self.generic.scrape(url)
            if data:
                emails.update(data.emails)
            await asyncio.sleep(1)

        # Also search Google for emails on this domain
        google_results = await self.generic.scrape(
            f"https://www.google.com/search?q=email+site:{domain}",
            keywords=["@" + domain],
        )
        if google_results:
            emails.update(google_results.emails)

        return list(emails)


# ── Market Researcher ─────────────────────────────────────────────────────────

class MarketResearcher:
    def __init__(self, google: GoogleScraper, reddit: RedditScraper, generic: GenericScraper):
        self.google  = google
        self.reddit  = reddit
        self.generic = generic

    async def research(self, topic: str, depth: str = "medium") -> dict:
        """Full market research on a topic."""
        logger.info(f"Market research: {topic}")
        pages = {"light": 2, "medium": 4, "deep": 8}.get(depth, 4)
        tasks = [
            self.google.search(f"{topic} market analysis", pages=pages),
            self.google.search_news(topic, pages=2),
            self.reddit.search(topic, limit=30),
            self._scrape_competitor_prices(topic),
        ]
        web_results, news, reddit_posts, prices = await asyncio.gather(*tasks)

        return {
            "topic":       topic,
            "web_results": web_results,
            "news":        news,
            "reddit":      reddit_posts,
            "prices":      prices,
            "summary": {
                "total_sources": len(web_results) + len(news),
                "reddit_posts":  len(reddit_posts),
                "price_points":  len(prices),
            },
        }

    async def _scrape_competitor_prices(self, topic: str) -> list[dict]:
        results = await self.google.search(f"{topic} price cost buy", pages=2)
        prices  = []
        for r in results[:10]:
            data = await self.generic.scrape(r["url"], keywords=[topic])
            if data and data.prices:
                prices.append({
                    "site":   r.get("title",""),
                    "url":    r.get("url",""),
                    "prices": data.prices[:5],
                })
            await asyncio.sleep(1)
        return prices


# ── Conversation Miner ────────────────────────────────────────────────────────

class ConversationMiner:
    """Find what people are saying about a topic across platforms."""

    def __init__(self, google: GoogleScraper, reddit: RedditScraper, generic: GenericScraper):
        self.google  = google
        self.reddit  = reddit
        self.generic = generic

    async def mine(self, topic: str, platforms: list[str] = None) -> list[dict]:
        platforms = platforms or ["reddit", "google", "news"]
        results   = []
        tasks     = []

        if "reddit" in platforms:
            tasks.append(self.reddit.search(topic, limit=50))
        if "news" in platforms:
            tasks.append(self.google.search_news(topic, pages=3))
        if "google" in platforms:
            tasks.append(self.google.search(f'"{topic}" discussion forum', pages=3))
        if "facebook" in platforms:
            tasks.append(self._search_facebook(topic))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for group in gathered:
            if isinstance(group, list):
                results.extend(group)

        logger.success(f"Conversation mining: {len(results)} results for '{topic}'")
        return results

    async def _search_facebook(self, topic: str) -> list[dict]:
        # Search Google for Facebook discussions (no login needed)
        return await self.google.search(f"site:facebook.com {topic}", pages=2)
