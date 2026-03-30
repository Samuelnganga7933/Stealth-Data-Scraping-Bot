"""
scrapers/linkedin.py — LinkedIn scraper
Scrapes public profiles, job listings, company pages
Uses Playwright (JS-heavy site)
"""

import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.browser import StealthBrowser


class LinkedInScraper:

    def __init__(self, browser: StealthBrowser, credentials: Optional[dict] = None):
        self.browser     = browser
        self.credentials = credentials
        self._logged_in  = False

    async def login(self) -> bool:
        if not self.credentials:
            return False
        try:
            page = await self.browser.new_page()
            await self.browser.goto(page, "https://www.linkedin.com/login")
            await asyncio.sleep(2)
            await self.browser.human_type(page, '#username', self.credentials["username"])
            await self.browser.human_type(page, '#password', self.credentials["password"])
            await self.browser.human_click(page, '[type="submit"]')
            await asyncio.sleep(4)
            self._logged_in = "feed" in page.url or "mynetwork" in page.url
            logger.info(f"LinkedIn login: {'success' if self._logged_in else 'failed'}")
            await page.close()
            return self._logged_in
        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False

    async def search_jobs(self, query: str, location: str = "", limit: int = 50) -> list[dict]:
        """Search LinkedIn Jobs."""
        from urllib.parse import quote_plus
        loc_param = f"&location={quote_plus(location)}" if location else ""
        url  = f"https://www.linkedin.com/jobs/search?keywords={quote_plus(query)}{loc_param}"
        page = await self.browser.new_page()
        jobs = []

        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)

            seen = set()
            scrolls = 0

            while len(jobs) < limit and scrolls < 15:
                content = await page.content()
                soup    = BeautifulSoup(content, "html.parser")
                new     = self._parse_jobs(soup)

                for j in new:
                    key = j.get("title", "") + j.get("company", "")
                    if key and key not in seen:
                        seen.add(key)
                        jobs.append(j)

                # Click "Show more jobs" if present
                try:
                    btn = await page.query_selector("button.infinite-scroller__show-more-button")
                    if btn:
                        await self.browser.human_click(page, "button.infinite-scroller__show-more-button")
                        await asyncio.sleep(2)
                except Exception:
                    pass

                await self.browser.human_scroll(page, "down", times=4)
                await asyncio.sleep(random.uniform(2, 4))
                scrolls += 1

        except Exception as e:
            logger.error(f"LinkedIn jobs error: {e}")
        finally:
            await page.close()

        logger.success(f"LinkedIn: found {len(jobs)} jobs for '{query}'")
        return jobs[:limit]

    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape a public LinkedIn profile."""
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, profile_url)
            await asyncio.sleep(3)
            await self.browser.random_scroll_read(page)
            content = await page.content()
            return self._parse_profile(BeautifulSoup(content, "html.parser"), profile_url)
        except Exception as e:
            logger.error(f"LinkedIn profile error: {e}")
            return {}
        finally:
            await page.close()

    async def search_people(self, query: str, limit: int = 20) -> list[dict]:
        """Search for people on LinkedIn."""
        from urllib.parse import quote_plus
        url  = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
        page = await self.browser.new_page()
        people = []

        try:
            await self.browser.goto(page, url)
            await asyncio.sleep(3)
            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")

            for card in soup.select(".entity-result__item, .search-result__info"):
                try:
                    name  = card.find("span", {"aria-hidden": "true"})
                    title = card.find("div", class_="entity-result__primary-subtitle")
                    loc   = card.find("div", class_="entity-result__secondary-subtitle")
                    link  = card.find("a", class_="app-aware-link")
                    people.append({
                        "name":     name.get_text(strip=True) if name else "",
                        "title":    title.get_text(strip=True) if title else "",
                        "location": loc.get_text(strip=True) if loc else "",
                        "url":      link.get("href", "") if link else "",
                        "source":   "linkedin",
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"LinkedIn people search error: {e}")
        finally:
            await page.close()

        return people[:limit]

    async def post_linkedin(self, text: str) -> bool:
        """Post to LinkedIn using logged-in account."""
        if not self._logged_in:
            await self.login()
        if not self._logged_in:
            return False

        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://www.linkedin.com/feed/")
            await asyncio.sleep(2)
            await self.browser.human_click(page, ".share-box-feed-entry__trigger")
            await asyncio.sleep(1)
            await self.browser.human_type(page, ".ql-editor", text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, "button.share-actions__primary-action")
            await asyncio.sleep(3)
            logger.success("LinkedIn post published")
            return True
        except Exception as e:
            logger.error(f"LinkedIn post error: {e}")
            return False
        finally:
            await page.close()

    def _parse_jobs(self, soup: BeautifulSoup) -> list[dict]:
        jobs = []
        for card in soup.select(".job-search-card, .base-card"):
            try:
                title   = card.find("h3", class_="base-search-card__title")
                company = card.find("h4", class_="base-search-card__subtitle")
                loc     = card.find("span", class_="job-search-card__location")
                date    = card.find("time")
                link    = card.find("a", class_="base-card__full-link")
                jobs.append({
                    "title":    title.get_text(strip=True) if title else "",
                    "company":  company.get_text(strip=True) if company else "",
                    "location": loc.get_text(strip=True) if loc else "",
                    "date":     date.get("datetime", "") if date else "",
                    "url":      link.get("href", "") if link else "",
                    "source":   "linkedin",
                })
            except Exception:
                continue
        return jobs

    def _parse_profile(self, soup: BeautifulSoup, url: str) -> dict:
        try:
            name  = soup.find("h1", class_="text-heading-xlarge")
            title = soup.find("div", class_="text-body-medium")
            loc   = soup.find("span", class_="text-body-small")
            about = soup.find("div", {"id": "about"})
            return {
                "name":     name.get_text(strip=True) if name else "",
                "title":    title.get_text(strip=True) if title else "",
                "location": loc.get_text(strip=True) if loc else "",
                "about":    about.get_text(strip=True)[:500] if about else "",
                "url":      url,
                "source":   "linkedin",
            }
        except Exception:
            return {"url": url, "source": "linkedin"}
