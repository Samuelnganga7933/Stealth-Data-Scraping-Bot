"""
scrapers/tiktok.py — TikTok public scraper
Scrapes public profiles, search results, hashtags
Uses Playwright (heavy JS site)
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.browser import StealthBrowser


class TikTokScraper:

    def __init__(self, browser: StealthBrowser):
        self.browser = browser

    async def search(self, query: str, limit: int = 30) -> list[dict]:
        """Search TikTok for videos matching a keyword."""
        from urllib.parse import quote_plus
        url   = f"https://www.tiktok.com/search?q={quote_plus(query)}"
        page  = await self.browser.new_page()
        posts = []

        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(4)

            seen    = set()
            scrolls = 0
            while len(posts) < limit and scrolls < 10:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_videos(soup)
                for v in new:
                    key = v.get("url", "")
                    if key and key not in seen:
                        seen.add(key)
                        posts.append(v)
                await self.browser.human_scroll(page, "down", times=3)
                await asyncio.sleep(random.uniform(2, 4))
                scrolls += 1

        except Exception as e:
            logger.error(f"TikTok search error: {e}")
        finally:
            await page.close()

        logger.success(f"TikTok: {len(posts)} videos for '{query}'")
        return posts[:limit]

    async def scrape_profile(self, username: str, max_videos: int = 20) -> dict:
        """Scrape a public TikTok profile."""
        url  = f"https://www.tiktok.com/@{username}"
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(4)
            await self.browser.random_scroll_read(page)
            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")

            name     = soup.find("h1", {"data-e2e": "user-title"})
            bio      = soup.find("h2", {"data-e2e": "user-bio"})
            followers= soup.find("strong", {"data-e2e": "followers-count"})
            likes    = soup.find("strong", {"data-e2e": "likes-count"})
            videos   = self._parse_videos(soup)[:max_videos]

            return {
                "username":  username,
                "name":      name.get_text(strip=True) if name else "",
                "bio":       bio.get_text(strip=True) if bio else "",
                "followers": followers.get_text(strip=True) if followers else "",
                "likes":     likes.get_text(strip=True) if likes else "",
                "videos":    videos,
                "source":    "tiktok",
            }
        except Exception as e:
            logger.error(f"TikTok profile error: {e}")
            return {"username": username, "source": "tiktok"}
        finally:
            await page.close()

    async def scrape_hashtag(self, hashtag: str, limit: int = 30) -> list[dict]:
        """Scrape TikTok hashtag page."""
        url  = f"https://www.tiktok.com/tag/{hashtag}"
        page = await self.browser.new_page()
        posts = []
        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(4)
            seen    = set()
            scrolls = 0
            while len(posts) < limit and scrolls < 8:
                content = await page.content()
                new     = self._parse_videos(BeautifulSoup(content, "html.parser"))
                for v in new:
                    key = v.get("url", "")
                    if key and key not in seen:
                        seen.add(key)
                        posts.append(v)
                await self.browser.human_scroll(page, "down", times=3)
                await asyncio.sleep(random.uniform(2, 3))
                scrolls += 1
        except Exception as e:
            logger.error(f"TikTok hashtag error: {e}")
        finally:
            await page.close()
        return posts[:limit]

    def _parse_videos(self, soup: BeautifulSoup) -> list[dict]:
        videos = []
        for item in soup.find_all("div", {"data-e2e": "recommend-list-item-container"}):
            try:
                a       = item.find("a", href=True)
                desc    = item.find("div", {"data-e2e": "video-desc"})
                likes   = item.find("strong", {"data-e2e": "video-like-count"})
                if not a:
                    continue
                videos.append({
                    "url":    f"https://www.tiktok.com{a['href']}" if a["href"].startswith("/") else a["href"],
                    "desc":   desc.get_text(strip=True)[:200] if desc else "",
                    "likes":  likes.get_text(strip=True) if likes else "",
                    "source": "tiktok",
                })
            except Exception:
                continue
        return videos
