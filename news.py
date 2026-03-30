"""
scrapers/news.py — Multi-source news scraper
Scrapes news articles from Google News, RSS feeds,
and major news sites by keyword
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.fetcher import Fetcher
from core.extractor import Extractor

# Popular RSS feeds by category
RSS_FEEDS = {
    "general": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.cnn.com/rss/edition.rss",
        "https://feeds.reuters.com/reuters/topNews",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ],
    "tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.wired.com/feed/rss",
        "https://www.theverge.com/rss/index.xml",
    ],
    "africa": [
        "https://www.nation.co.ke/rss",
        "https://www.standardmedia.co.ke/rss/news.php",
        "https://techcabal.com/feed/",
        "https://disrupt-africa.com/feed/",
        "https://www.businessdailyafrica.com/rss",
    ],
    "business": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.ft.com/rss/home",
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    ],
    "jobs": [
        "https://remoteok.com/remote-jobs.rss",
        "https://weworkremotely.com/remote-jobs.rss",
    ],
}


class NewsScraper:

    def __init__(self, fetcher: Fetcher):
        self.fetcher   = fetcher
        self.extractor = Extractor()

    async def search_news(self, query: str, limit: int = 50) -> list[dict]:
        """Search news across Google News + RSS feeds."""
        tasks = [
            self._google_news(query),
            self._rss_search(query),
            self._newsapi_search(query),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for r in results:
            if isinstance(r, list):
                articles.extend(r)

        # Deduplicate by title
        seen  = set()
        dedup = []
        for a in articles:
            key = a.get("title", "")[:50].lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(a)

        logger.success(f"News: {len(dedup)} articles for '{query}'")
        return dedup[:limit]

    async def scrape_rss(self, feed_url: str, keywords: list[str] = None) -> list[dict]:
        """Scrape a single RSS feed."""
        html = await self.fetcher.get(feed_url)
        if not html:
            return []
        return self._parse_rss(html, feed_url, keywords)

    async def scrape_category(self, category: str, limit: int = 50) -> list[dict]:
        """Scrape all feeds in a category (general, tech, africa, business)."""
        feeds   = RSS_FEEDS.get(category.lower(), RSS_FEEDS["general"])
        results = []
        for feed in feeds:
            articles = await self.scrape_rss(feed)
            results.extend(articles)
            await asyncio.sleep(random.uniform(0.5, 1.5))
        return results[:limit]

    async def scrape_article(self, url: str) -> dict:
        """Scrape full text of a news article."""
        soup = await self.fetcher.get_soup(url)
        if not soup:
            return {}

        # Remove nav, footer, ads
        for tag in soup.find_all(["nav", "footer", "aside", "script", "style", "header"]):
            tag.decompose()

        title   = soup.find("h1")
        date    = (
            soup.find("time") or
            soup.find("meta", {"property": "article:published_time"}) or
            soup.find("span", {"class": lambda c: c and "date" in str(c).lower()})
        )
        # Get article body
        body    = (
            soup.find("article") or
            soup.find("div", {"class": lambda c: c and any(x in str(c).lower() for x in ["article", "content", "story", "post-body"])}) or
            soup.find("main")
        )

        return {
            "title":   title.get_text(strip=True) if title else "",
            "url":     url,
            "date":    date.get_text(strip=True) if date else date.get("content", "") if date else "",
            "content": body.get_text(separator=" ", strip=True)[:3000] if body else "",
            "source":  "news",
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _google_news(self, query: str) -> list[dict]:
        """Search Google News RSS."""
        from urllib.parse import quote_plus
        url  = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en&gl=US&ceid=US:en"
        html = await self.fetcher.get(url)
        if not html:
            return []
        return self._parse_rss(html, url)

    async def _rss_search(self, query: str) -> list[dict]:
        """Search keyword across our RSS feed list."""
        feeds   = RSS_FEEDS["general"] + RSS_FEEDS["africa"]
        results = []
        kw      = query.lower().split()
        for feed in feeds[:6]:
            articles = await self.scrape_rss(feed)
            for a in articles:
                text = (a.get("title","") + " " + a.get("description","")).lower()
                if all(k in text for k in kw):
                    results.append(a)
            await asyncio.sleep(0.5)
        return results

    async def _newsapi_search(self, query: str) -> list[dict]:
        """Search via free NewsAPI (1000 req/day free tier)."""
        # Returns empty if no key — graceful fallback
        try:
            from urllib.parse import quote_plus
            url  = f"https://newsapi.org/v2/everything?q={quote_plus(query)}&sortBy=relevancy&language=en&pageSize=30"
            # Note: add &apiKey=YOUR_KEY to .env for this to work
            html = await self.fetcher.get(url)
            if not html:
                return []
            import json
            data = json.loads(html)
            return [
                {
                    "title":       a.get("title",""),
                    "url":         a.get("url",""),
                    "description": a.get("description",""),
                    "date":        a.get("publishedAt",""),
                    "outlet":      a.get("source",{}).get("name",""),
                    "source":      "newsapi",
                }
                for a in data.get("articles",[])
                if a.get("title") and a.get("url")
            ]
        except Exception:
            return []

    def _parse_rss(self, xml: str, feed_url: str, keywords: list[str] = None) -> list[dict]:
        soup     = BeautifulSoup(xml, "xml")
        articles = []
        for item in soup.find_all("item"):
            try:
                title = item.find("title")
                link  = item.find("link")
                desc  = item.find("description")
                pub   = item.find("pubDate") or item.find("published")

                t = title.get_text(strip=True) if title else ""
                d = desc.get_text(strip=True)[:300] if desc else ""

                # Filter by keywords if given
                if keywords:
                    combined = (t + " " + d).lower()
                    if not any(k.lower() in combined for k in keywords):
                        continue

                articles.append({
                    "title":       t,
                    "url":         link.get_text(strip=True) if link else "",
                    "description": d,
                    "date":        pub.get_text(strip=True) if pub else "",
                    "feed":        feed_url,
                    "source":      "rss",
                })
            except Exception:
                continue
        return articles
