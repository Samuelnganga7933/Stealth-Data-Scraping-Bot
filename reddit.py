"""
scrapers/reddit.py — Reddit scraper
Uses direct HTTP (no API key needed for public data)
Scrapes posts, comments, subreddits by keyword
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.fetcher import Fetcher
from core.browser import StealthBrowser


class RedditScraper:

    BASE     = "https://www.reddit.com"
    OLD_BASE = "https://old.reddit.com"  # easier to scrape

    def __init__(self, fetcher: Fetcher, browser: Optional[StealthBrowser] = None):
        self.fetcher = fetcher
        self.browser = browser

    async def search(self, query: str, subreddit: str = "", limit: int = 50) -> list[dict]:
        """Search Reddit for posts matching a keyword."""
        if subreddit:
            url = f"{self.OLD_BASE}/r/{subreddit}/search?q={query}&restrict_sr=1&sort=relevance"
        else:
            url = f"{self.OLD_BASE}/search?q={query}&sort=relevance"

        posts = []
        after = None

        while len(posts) < limit:
            fetch_url = f"{url}&after={after}" if after else url
            soup      = await self.fetcher.get_soup(fetch_url)
            if not soup:
                break

            new, after = self._parse_posts(soup)
            posts.extend(new)

            if not after or not new:
                break

            await asyncio.sleep(random.uniform(2, 4))

        logger.success(f"Reddit: found {len(posts)} posts for '{query}'")
        return posts[:limit]

    async def scrape_subreddit(self, subreddit: str, sort: str = "hot", limit: int = 50) -> list[dict]:
        """Scrape posts from a subreddit."""
        url   = f"{self.OLD_BASE}/r/{subreddit}/{sort}"
        posts = []
        after = None

        while len(posts) < limit:
            fetch_url = f"{url}?after={after}" if after else url
            soup      = await self.fetcher.get_soup(fetch_url)
            if not soup:
                break

            new, after = self._parse_posts(soup)
            posts.extend(new)
            if not after or not new:
                break

            await asyncio.sleep(random.uniform(1.5, 3))

        logger.success(f"Reddit r/{subreddit}: scraped {len(posts)} posts")
        return posts[:limit]

    async def get_post_comments(self, post_url: str, max_comments: int = 100) -> list[dict]:
        """Scrape comments from a Reddit post."""
        old_url = post_url.replace("www.reddit.com", "old.reddit.com")
        soup    = await self.fetcher.get_soup(old_url)
        if not soup:
            return []
        return self._parse_comments(soup)[:max_comments]

    async def scrape_user(self, username: str) -> dict:
        """Scrape a Reddit user's public profile and posts."""
        url  = f"{self.OLD_BASE}/user/{username}"
        soup = await self.fetcher.get_soup(url)
        if not soup:
            return {}

        posts, _ = self._parse_posts(soup)
        karma    = soup.find("span", class_="karma")
        return {
            "username": username,
            "karma":    karma.get_text(strip=True) if karma else "",
            "posts":    posts,
            "source":   "reddit",
        }

    def _parse_posts(self, soup: BeautifulSoup) -> tuple[list[dict], Optional[str]]:
        posts = []
        for thing in soup.find_all("div", class_="thing"):
            try:
                title    = thing.find("a", class_="title")
                score    = thing.find("div", class_="score")
                comments = thing.find("a", class_="comments")
                time_tag = thing.find("time")
                sub      = thing.get("data-subreddit", "")
                author   = thing.get("data-author", "")

                if not title:
                    continue

                posts.append({
                    "title":       title.get_text(strip=True),
                    "url":         title.get("href", ""),
                    "score":       score.get_text(strip=True) if score else "",
                    "comments":    comments.get_text(strip=True) if comments else "",
                    "datetime":    time_tag.get("datetime", "") if time_tag else "",
                    "subreddit":   sub,
                    "author":      author,
                    "source":      "reddit",
                })
            except Exception:
                continue

        # Pagination
        after_btn = soup.find("span", class_="next-button")
        after     = None
        if after_btn:
            a     = after_btn.find("a", href=True)
            if a:
                import re
                m = re.search(r"after=([^&]+)", a["href"])
                if m:
                    after = m.group(1)

        return posts, after

    def _parse_comments(self, soup: BeautifulSoup) -> list[dict]:
        comments = []
        for c in soup.find_all("div", class_="comment"):
            try:
                body   = c.find("div", class_="md")
                author = c.find("a", class_="author")
                score  = c.find("span", class_="score")
                t      = c.find("time")
                if not body:
                    continue
                comments.append({
                    "text":     body.get_text(separator=" ", strip=True)[:1000],
                    "author":   author.get_text(strip=True) if author else "",
                    "score":    score.get_text(strip=True) if score else "",
                    "datetime": t.get("datetime", "") if t else "",
                    "source":   "reddit",
                })
            except Exception:
                continue
        return comments
