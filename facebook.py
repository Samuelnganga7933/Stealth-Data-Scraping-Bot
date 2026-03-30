"""
scrapers/facebook.py — Facebook public page & group scraper
Scrapes public posts, pages, group links
Uses Playwright (JS-heavy)
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.browser import StealthBrowser
from core.fetcher import Fetcher


class FacebookScraper:

    def __init__(self, browser: StealthBrowser, fetcher: Fetcher):
        self.browser = browser
        self.fetcher = fetcher

    async def search_public(self, query: str, limit: int = 30) -> list[dict]:
        """Search Facebook public posts (via Google site search — no login needed)."""
        from urllib.parse import quote_plus
        from scrapers.google import GoogleScraper
        google = GoogleScraper(self.fetcher, self.browser)
        results = await google.search(f"site:facebook.com {query}", pages=3)
        posts = []
        for r in results[:limit]:
            posts.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "snippet": r.get("description", ""),
                "source":  "facebook_public",
            })
        logger.success(f"Facebook public search: {len(posts)} results for '{query}'")
        return posts

    async def scrape_public_page(self, page_url: str, max_posts: int = 30) -> dict:
        """Scrape a public Facebook page."""
        page = await self.browser.new_page()
        posts = []
        try:
            await self.browser.goto(page, page_url)
            await asyncio.sleep(3)

            # Close cookie/login popup if present
            for selector in ['[aria-label="Close"]', '[data-testid="cookie-policy-manage-dialog-accept-button"]']:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    pass

            seen   = set()
            scrolls = 0
            while len(posts) < max_posts and scrolls < 15:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_posts(soup)
                for p in new:
                    key = p.get("text", "")[:60]
                    if key and key not in seen:
                        seen.add(key)
                        posts.append(p)
                await self.browser.human_scroll(page, "down", times=3)
                await asyncio.sleep(random.uniform(1.5, 3))
                scrolls += 1

            # Page info
            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")
            name    = soup.find("h1")
            about   = soup.find("div", {"data-key": "intro_card"})

            return {
                "page_url": page_url,
                "name":     name.get_text(strip=True) if name else "",
                "about":    about.get_text(strip=True)[:300] if about else "",
                "posts":    posts,
                "source":   "facebook",
            }
        except Exception as e:
            logger.error(f"Facebook page scrape error: {e}")
            return {"page_url": page_url, "posts": posts}
        finally:
            await page.close()

    async def find_group_links(self, keyword: str) -> list[str]:
        """Find public WhatsApp/Facebook group invite links mentioning a keyword."""
        from scrapers.google import GoogleScraper
        from core.extractor import Extractor
        google = GoogleScraper(self.fetcher, self.browser)
        ext    = Extractor()

        results  = await google.search(f"facebook group {keyword} join", pages=2)
        wa_links = []
        for r in results[:10]:
            html = await self.fetcher.get(r.get("url", ""))
            if html:
                data = ext.extract_from_html(html, r.get("url", ""))
                wa_links.extend(data.social_links)

        return list(set(wa_links))

    def _parse_posts(self, soup: BeautifulSoup) -> list[dict]:
        posts = []
        for div in soup.find_all("div", {"data-ad-preview": "message"}):
            try:
                text = div.get_text(separator=" ", strip=True)
                if text and len(text) > 10:
                    posts.append({"text": text[:500], "source": "facebook"})
            except Exception:
                continue

        # Also try generic post containers
        if not posts:
            for div in soup.find_all("div", class_=lambda c: c and "userContent" in str(c)):
                text = div.get_text(separator=" ", strip=True)
                if text and len(text) > 10:
                    posts.append({"text": text[:500], "source": "facebook"})

        return posts
