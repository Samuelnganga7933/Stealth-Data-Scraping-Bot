"""
core/fetcher.py — Fast static site fetcher
httpx + BeautifulSoup for sites that don't need JavaScript
10x faster than Playwright for simple pages
"""

import asyncio
import random
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


class Fetcher:
    """
    Async HTTP fetcher with rotating headers, proxy support,
    retry logic, and BeautifulSoup parsing.
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 20,
        max_retries: int = 3,
    ):
        self.proxy       = proxy
        self.timeout     = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict:
        return {
            "User-Agent":      random.choice(USER_AGENTS),
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection":      "keep-alive",
            "DNT":             "1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def get(self, url: str) -> Optional[str]:
        """Fetch a URL, return raw HTML string."""
        proxies = {"http://": self.proxy, "https://": self.proxy} if self.proxy else None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    headers=self._headers(),
                    proxies=proxies,
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=False,
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    logger.info(f"Fetched {url} [{resp.status_code}]")
                    return resp.text

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} on {url} (attempt {attempt})")
                if e.response.status_code in (403, 429):
                    await asyncio.sleep(random.uniform(5, 15))
            except Exception as e:
                logger.warning(f"Fetch error on {url} (attempt {attempt}): {e}")
                await asyncio.sleep(random.uniform(2, 6))

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None

    async def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch URL and return parsed BeautifulSoup object."""
        html = await self.get(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    async def get_many(self, urls: list[str], delay: float = 1.5) -> dict[str, Optional[str]]:
        """Fetch multiple URLs with a polite delay between each."""
        results = {}
        for url in urls:
            results[url] = await self.get(url)
            await asyncio.sleep(random.uniform(delay * 0.5, delay * 1.5))
        return results

    def parse(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")
