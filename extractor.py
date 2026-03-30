"""
core/extractor.py — Smart regex data extractor
Pulls emails, phones, prices, dates, links, social handles,
company names, job titles from any raw text or HTML
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class ExtractedData:
    url:           str             = ""
    title:         str             = ""
    description:   str             = ""
    emails:        list[str]       = field(default_factory=list)
    phones:        list[str]       = field(default_factory=list)
    prices:        list[str]       = field(default_factory=list)
    dates:         list[str]       = field(default_factory=list)
    links:         list[str]       = field(default_factory=list)
    social_links:  list[str]       = field(default_factory=list)
    images:        list[str]       = field(default_factory=list)
    headings:      list[str]       = field(default_factory=list)
    keywords_found:list[str]       = field(default_factory=list)
    raw_text:      str             = ""
    meta:          dict            = field(default_factory=dict)


class Extractor:
    """
    Extracts structured data from HTML or plain text.
    No AI — pure regex + BeautifulSoup.
    """

    # ── Patterns ──────────────────────────────────────────────────────────────
    EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)
    PHONE_RE   = re.compile(
        r"""(\+?[\d\s\-().]{7,20})""",
        re.X,
    )
    PRICE_RE   = re.compile(
        r"""(
            (?:USD|KES|KSH|EUR|GBP|NGN|ZAR|UGX|TZS|\$|£|€|Ksh|Kshs)
            \s?[\d,]+(?:\.\d{1,2})?
            |
            [\d,]+(?:\.\d{1,2})?\s?
            (?:USD|KES|KSH|EUR|GBP|NGN|ZAR|UGX|TZS|dollars?|shillings?)
        )""",
        re.X | re.I,
    )
    DATE_RE    = re.compile(
        r"""(
            \d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}
            |\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}
            |(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}
            |\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}
        )""",
        re.X | re.I,
    )
    SOCIAL_RE  = re.compile(
        r"https?://(?:www\.)?(?:twitter\.com|x\.com|facebook\.com|instagram\.com"
        r"|linkedin\.com|tiktok\.com|youtube\.com|reddit\.com|github\.com)"
        r"/[^\s\"'<>]{2,50}",
        re.I,
    )
    PHONE_CLEAN_RE = re.compile(r"[^\d+\s\-()]")
    WHATSAPP_GROUP_RE = re.compile(
        r"https?://(?:chat\.whatsapp\.com)/[A-Za-z0-9]{20,}",
        re.I,
    )
    DISCORD_RE = re.compile(
        r"https?://(?:discord\.gg|discord\.com/invite)/[A-Za-z0-9]{5,20}",
        re.I,
    )

    def extract_from_html(self, html: str, url: str = "", keywords: list[str] = None) -> ExtractedData:
        """Full extraction from raw HTML string."""
        soup = BeautifulSoup(html, "html.parser")
        return self._extract(soup, html, url, keywords or [])

    def extract_from_soup(self, soup: BeautifulSoup, url: str = "", keywords: list[str] = None) -> ExtractedData:
        html = str(soup)
        return self._extract(soup, html, url, keywords or [])

    def extract_from_text(self, text: str, url: str = "") -> ExtractedData:
        data          = ExtractedData(url=url)
        data.raw_text = text[:5000]
        data.emails   = self._emails(text)
        data.phones   = self._phones(text)
        data.prices   = self._prices(text)
        data.dates    = self._dates(text)
        return data

    # ── Internal ──────────────────────────────────────────────────────────────

    def _extract(self, soup: BeautifulSoup, html: str, url: str, keywords: list[str]) -> ExtractedData:
        data     = ExtractedData(url=url)
        text     = soup.get_text(separator=" ", strip=True)
        data.raw_text = text[:8000]

        # Title
        title_tag    = soup.find("title")
        data.title   = title_tag.get_text(strip=True) if title_tag else ""

        # Description
        desc = (
            soup.find("meta", attrs={"name": "description"}) or
            soup.find("meta", attrs={"property": "og:description"})
        )
        data.description = desc.get("content", "") if desc else ""

        # Meta tags
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property", "")
            val  = tag.get("content", "")
            if name and val:
                data.meta[name] = val

        # Headings
        data.headings = [
            h.get_text(strip=True)
            for h in soup.find_all(["h1", "h2", "h3"])
            if h.get_text(strip=True)
        ][:20]

        # All links
        data.links = list({
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].startswith("http")
        })[:100]

        # Social links
        data.social_links = list(set(self.SOCIAL_RE.findall(html)))

        # WhatsApp groups + Discord invites (treat as special links)
        wa_groups = self.WHATSAPP_GROUP_RE.findall(html)
        discord   = self.DISCORD_RE.findall(html)
        data.social_links.extend(wa_groups)
        data.social_links.extend(discord)
        data.social_links = list(set(data.social_links))

        # Images
        data.images = list({
            img["src"] for img in soup.find_all("img", src=True)
            if img["src"].startswith("http")
        })[:50]

        # Contacts
        data.emails = self._emails(html)
        data.phones = self._phones(text)

        # Prices
        data.prices = self._prices(text)

        # Dates
        data.dates = self._dates(text)

        # Keyword matching
        if keywords:
            lower = text.lower()
            data.keywords_found = [kw for kw in keywords if kw.lower() in lower]

        return data

    def _emails(self, text: str) -> list[str]:
        found = self.EMAIL_RE.findall(text)
        # Filter out common false positives
        skip = {"example.com", "email.com", "domain.com", "youremail.com", "test.com"}
        return list({e.lower() for e in found if e.split("@")[-1].lower() not in skip})

    def _phones(self, text: str) -> list[str]:
        raw     = self.PHONE_RE.findall(text)
        cleaned = []
        for p in raw:
            p = p.strip()
            digits = re.sub(r"\D", "", p)
            if 7 <= len(digits) <= 15:
                cleaned.append(p)
        return list(set(cleaned))[:20]

    def _prices(self, text: str) -> list[str]:
        return list(set(self.PRICE_RE.findall(text)))[:30]

    def _dates(self, text: str) -> list[str]:
        return list(set(self.DATE_RE.findall(text)))[:20]
