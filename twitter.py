"""
scrapers/twitter.py — Twitter/X scraper
Scrapes public tweets, profiles, search results
Uses Playwright to bypass JS rendering
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import Page

from core.browser import StealthBrowser


class TwitterScraper:

    SEARCH_URL  = "https://twitter.com/search?q={query}&src=typed_query&f=live"
    PROFILE_URL = "https://twitter.com/{username}"

    def __init__(self, browser: StealthBrowser, credentials: Optional[dict] = None):
        self.browser     = browser
        self.credentials = credentials  # {"username": "...", "password": "..."}
        self._logged_in  = False

    async def login(self) -> bool:
        if not self.credentials:
            logger.warning("No Twitter credentials provided")
            return False
        try:
            page = await self.browser.new_page()
            await self.browser.goto(page, "https://twitter.com/i/flow/login")
            await asyncio.sleep(3)
            await self.browser.human_type(page, 'input[autocomplete="username"]', self.credentials["username"])
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            await self.browser.human_type(page, 'input[name="password"]', self.credentials["password"])
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            self._logged_in = "twitter.com/home" in page.url or "x.com/home" in page.url
            logger.info(f"Twitter login: {'success' if self._logged_in else 'failed'}")
            await page.close()
            return self._logged_in
        except Exception as e:
            logger.error(f"Twitter login error: {e}")
            return False

    async def search(self, query: str, max_tweets: int = 50) -> list[dict]:
        """Search Twitter/X for a keyword or phrase."""
        url   = self.SEARCH_URL.format(query=query.replace(" ", "%20"))
        page  = await self.browser.new_page()
        tweets = []

        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)

            seen = set()
            scrolls = 0
            max_scrolls = max_tweets // 5

            while len(tweets) < max_tweets and scrolls < max_scrolls:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_tweets(soup)

                for t in new:
                    key = t.get("text", "")[:50]
                    if key not in seen:
                        seen.add(key)
                        tweets.append(t)

                await self.browser.human_scroll(page, "down", times=3)
                await asyncio.sleep(random.uniform(1.5, 3))
                scrolls += 1

        except Exception as e:
            logger.error(f"Twitter search error: {e}")
        finally:
            await page.close()

        logger.success(f"Twitter: scraped {len(tweets)} tweets for '{query}'")
        return tweets[:max_tweets]

    async def scrape_profile(self, username: str, max_tweets: int = 30) -> dict:
        """Scrape a public Twitter/X profile."""
        url  = self.PROFILE_URL.format(username=username)
        page = await self.browser.new_page()

        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)
            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")

            profile = self._parse_profile(soup, username)
            tweets  = []
            seen    = set()
            scrolls = 0

            while len(tweets) < max_tweets and scrolls < 10:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_tweets(soup)
                for t in new:
                    key = t.get("text", "")[:50]
                    if key not in seen:
                        seen.add(key)
                        tweets.append(t)
                await self.browser.human_scroll(page, "down", times=2)
                await asyncio.sleep(random.uniform(1, 2.5))
                scrolls += 1

            profile["tweets"] = tweets[:max_tweets]
            return profile

        except Exception as e:
            logger.error(f"Twitter profile scrape error: {e}")
            return {}
        finally:
            await page.close()

    async def post_tweet(self, text: str) -> bool:
        """Post a tweet using logged-in account."""
        if not self._logged_in:
            await self.login()
        if not self._logged_in:
            return False

        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://twitter.com/home")
            await asyncio.sleep(2)
            await self.browser.human_click(page, '[data-testid="tweetTextarea_0"]')
            await self.browser.human_type(page, '[data-testid="tweetTextarea_0"]', text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, '[data-testid="tweetButton"]')
            await asyncio.sleep(3)
            logger.success("Tweet posted")
            return True
        except Exception as e:
            logger.error(f"Tweet post error: {e}")
            return False
        finally:
            await page.close()

    def _parse_tweets(self, soup: BeautifulSoup) -> list[dict]:
        tweets = []
        for article in soup.find_all("article", {"data-testid": "tweet"}):
            try:
                text_div = article.find("div", {"data-testid": "tweetText"})
                time_tag = article.find("time")
                user_div = article.find("div", {"data-testid": "User-Name"})
                links    = [a["href"] for a in article.find_all("a", href=True) if "status" in a.get("href","")]

                tweets.append({
                    "text":      text_div.get_text(separator=" ", strip=True) if text_div else "",
                    "datetime":  time_tag.get("datetime", "") if time_tag else "",
                    "user":      user_div.get_text(strip=True) if user_div else "",
                    "tweet_url": f"https://twitter.com{links[0]}" if links else "",
                    "source":    "twitter",
                })
            except Exception:
                continue
        return tweets

    def _parse_profile(self, soup: BeautifulSoup, username: str) -> dict:
        try:
            name    = soup.find("div", {"data-testid": "UserName"})
            bio     = soup.find("div", {"data-testid": "UserDescription"})
            stats   = soup.find_all("a", {"href": lambda h: h and "followers" in h})
            return {
                "username":  username,
                "name":      name.get_text(strip=True) if name else "",
                "bio":       bio.get_text(strip=True) if bio else "",
                "followers": stats[0].get_text(strip=True) if stats else "",
                "source":    "twitter",
            }
        except Exception:
            return {"username": username, "source": "twitter"}
