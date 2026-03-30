"""
core/proxy.py — Proxy rotation manager
Rotates through proxy list, tracks failures, auto-retires bad proxies
Supports free proxy lists + paid proxy services
"""

import random
import asyncio
from dataclasses import dataclass, field
from typing import Optional
import httpx
from loguru import logger


@dataclass
class Proxy:
    url:      str
    failures: int  = 0
    working:  bool = True


class ProxyRotator:
    """
    Manages a pool of proxies.
    Auto-removes proxies that fail too many times.
    Falls back to direct connection if pool is empty.
    """

    def __init__(self, proxies: list[str] = None, max_failures: int = 3):
        self._pool        = [Proxy(url=p) for p in (proxies or [])]
        self.max_failures = max_failures

    def add(self, proxy_url: str):
        self._pool.append(Proxy(url=proxy_url))

    def get(self) -> Optional[str]:
        """Return a random working proxy URL, or None for direct."""
        working = [p for p in self._pool if p.working]
        if not working:
            return None
        return random.choice(working).url

    def mark_failed(self, proxy_url: str):
        for p in self._pool:
            if p.url == proxy_url:
                p.failures += 1
                if p.failures >= self.max_failures:
                    p.working = False
                    logger.warning(f"Proxy retired: {proxy_url}")
                break

    def mark_success(self, proxy_url: str):
        for p in self._pool:
            if p.url == proxy_url:
                p.failures = 0
                break

    @property
    def count(self) -> int:
        return len([p for p in self._pool if p.working])

    async def fetch_free_proxies(self):
        """Fetch free proxies from public list (use as fallback only — unreliable)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all")
                for line in r.text.strip().splitlines():
                    line = line.strip()
                    if ":" in line:
                        self.add(f"http://{line}")
            logger.info(f"Loaded {self.count} free proxies")
        except Exception as e:
            logger.warning(f"Free proxy fetch failed: {e}")
