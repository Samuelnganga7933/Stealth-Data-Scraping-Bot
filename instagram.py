"""
scrapers/instagram.py — Instagram public scraper
Scrapes public profiles, posts, hashtags
Uses instaloader for public data + Playwright fallback
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.browser import StealthBrowser
from core.fetcher import Fetcher


class InstagramScraper:

    def __init__(self, browser: StealthBrowser, fetcher: Fetcher):
        self.browser = browser
        self.fetcher = fetcher

    async def scrape_public_profile(self, username: str) -> dict:
        """Scrape a public Instagram profile."""
        # Try instaloader first (fast, no browser)
        profile = await self._instaloader_profile(username)
        if profile:
            return profile
        # Fallback to Playwright
        return await self._playwright_profile(username)

    async def search_hashtag(self, hashtag: str, limit: int = 30) -> list[dict]:
        """Scrape posts from a public hashtag."""
        url  = f"https://www.instagram.com/explore/tags/{hashtag}/"
        page = await self.browser.new_page()
        posts = []
        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)
            seen    = set()
            scrolls = 0
            while len(posts) < limit and scrolls < 10:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_posts(soup)
                for p in new:
                    key = p.get("url", "")
                    if key and key not in seen:
                        seen.add(key)
                        posts.append(p)
                await self.browser.human_scroll(page, "down", times=2)
                await asyncio.sleep(random.uniform(2, 4))
                scrolls += 1
        except Exception as e:
            logger.error(f"Instagram hashtag error: {e}")
        finally:
            await page.close()

        logger.success(f"Instagram #{hashtag}: {len(posts)} posts")
        return posts[:limit]

    async def _instaloader_profile(self, username: str) -> Optional[dict]:
        """Use instaloader library for clean public data."""
        try:
            import instaloader
            L        = instaloader.Instaloader(download_pictures=False, download_videos=False)
            profile  = instaloader.Profile.from_username(L.context, username)
            posts    = []
            count    = 0
            for post in profile.get_posts():
                if count >= 20:
                    break
                posts.append({
                    "caption":  post.caption[:300] if post.caption else "",
                    "likes":    post.likes,
                    "comments": post.comments,
                    "date":     str(post.date_utc),
                    "url":      f"https://www.instagram.com/p/{post.shortcode}/",
                    "source":   "instagram",
                })
                count += 1

            return {
                "username":  username,
                "full_name": profile.full_name,
                "bio":       profile.biography,
                "followers": profile.followers,
                "following": profile.followees,
                "posts":     posts,
                "source":    "instagram",
            }
        except Exception as e:
            logger.warning(f"instaloader failed for {username}: {e}")
            return None

    async def _playwright_profile(self, username: str) -> dict:
        """Playwright fallback for Instagram profile."""
        url  = f"https://www.instagram.com/{username}/"
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)
            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")

            name_tag  = soup.find("h2")
            meta_desc = soup.find("meta", {"name": "description"})
            posts     = self._parse_posts(soup)

            return {
                "username": username,
                "name":     name_tag.get_text(strip=True) if name_tag else "",
                "bio":      meta_desc.get("content", "") if meta_desc else "",
                "posts":    posts,
                "source":   "instagram",
            }
        except Exception as e:
            logger.error(f"Instagram Playwright error: {e}")
            return {"username": username, "source": "instagram"}
        finally:
            await page.close()

    def _parse_posts(self, soup: BeautifulSoup) -> list[dict]:
        posts = []
        for a in soup.find_all("a", href=lambda h: h and "/p/" in str(h)):
            try:
                img = a.find("img")
                posts.append({
                    "url":     f"https://www.instagram.com{a['href']}",
                    "caption": img.get("alt", "") if img else "",
                    "source":  "instagram",
                })
            except Exception:
                continue
        return posts
