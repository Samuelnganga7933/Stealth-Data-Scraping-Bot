"""
core/command_parser.py — Natural language command parser
Pure Python — no AI. Regex + keyword matching.
Understands commands like:
  "scrape linkedin for python developer jobs in Nairobi"
  "find leads in fintech industry kenya"
  "search twitter for posts about Safaricom"
  "post on facebook: Hello world"
"""

import re
from dataclasses import dataclass, field
from typing import Optional


PLATFORMS = [
    "google", "twitter", "x", "facebook", "instagram", "linkedin",
    "tiktok", "reddit", "youtube", "news", "web", "whatsapp", "discord",
]

INTENTS = {
    "scrape":   ["scrape", "extract", "get data", "pull data", "fetch", "crawl", "grab"],
    "jobs":     ["jobs", "job listings", "vacancies", "openings", "hiring", "work", "employment", "career"],
    "leads":    ["leads", "companies", "contacts", "emails", "phones", "prospects", "businesses"],
    "market":   ["market research", "research", "trends", "competitors", "industry", "analysis", "pricing"],
    "mine":     ["conversations", "discussions", "posts about", "talking about", "mentions", "sentiment"],
    "post":     ["post", "tweet", "publish", "share", "upload", "send", "write"],
    "comment":  ["comment", "reply", "respond"],
    "search":   ["search", "find", "look for", "look up", "show me", "get me"],
}


@dataclass
class Command:
    intent:    str            = "scrape"      # scrape | jobs | leads | market | mine | post | comment | search
    query:     str            = ""            # main search term / keyword
    platforms: list[str]      = field(default_factory=list)
    urls:      list[str]      = field(default_factory=list)
    location:  str            = ""
    depth:     str            = "medium"      # light | medium | deep
    limit:     int            = 50
    post_text: str            = ""            # for post/comment intents
    platform_creds: dict      = field(default_factory=dict)
    raw:       str            = ""


class CommandParser:

    URL_RE      = re.compile(r"https?://[^\s]+")
    LIMIT_RE    = re.compile(r"\b(\d+)\s*(?:results?|items?|posts?|jobs?|leads?)\b", re.I)
    LOCATION_RE = re.compile(
        r"\b(?:in|at|from|near|location|city|country)\s+([A-Za-z][A-Za-z\s,]{2,30}?)(?:\s+(?:for|about|on|from)|$)",
        re.I,
    )
    DEPTH_RE    = re.compile(r"\b(deep|thorough|full|quick|light|fast|detailed)\b", re.I)

    DEPTH_MAP = {
        "deep": "deep", "thorough": "deep", "full": "deep", "detailed": "deep",
        "quick": "light", "light": "light", "fast": "light",
    }

    def parse(self, text: str) -> Command:
        cmd       = Command(raw=text)
        lower     = text.lower().strip()

        # Extract URLs
        cmd.urls  = self.URL_RE.findall(text)
        clean     = self.URL_RE.sub("", lower)

        # Detect intent
        cmd.intent = self._detect_intent(clean)

        # Detect platforms
        cmd.platforms = self._detect_platforms(clean)

        # Detect location
        loc_match = self.LOCATION_RE.search(clean)
        if loc_match:
            cmd.location = loc_match.group(1).strip()

        # Detect depth
        depth_match = self.DEPTH_RE.search(clean)
        if depth_match:
            cmd.depth = self.DEPTH_MAP.get(depth_match.group(1).lower(), "medium")

        # Detect limit
        limit_match = self.LIMIT_RE.search(clean)
        if limit_match:
            cmd.limit = min(int(limit_match.group(1)), 500)

        # Post text (everything after colon or "post:")
        if cmd.intent in ("post", "comment"):
            post_match = re.search(r"(?:post|tweet|say|write|publish|comment)[:\s]+[\"']?(.+)[\"']?$", text, re.I)
            if post_match:
                cmd.post_text = post_match.group(1).strip().strip('"\'')

        # Extract main query (remove platform names, intent words, location)
        cmd.query = self._extract_query(clean, cmd)

        return cmd

    def _detect_intent(self, text: str) -> str:
        for intent, keywords in INTENTS.items():
            if any(kw in text for kw in keywords):
                return intent
        return "scrape"

    def _detect_platforms(self, text: str) -> list[str]:
        found = []
        for p in PLATFORMS:
            if p in text:
                found.append(p)
        # Normalise x → twitter
        if "x" in found and "twitter" not in found:
            found.append("twitter")
            found.remove("x")
        return list(set(found)) or ["google", "web"]

    def _extract_query(self, text: str, cmd: Command) -> str:
        # Remove intent words
        for keywords in INTENTS.values():
            for kw in keywords:
                text = text.replace(kw, "")

        # Remove platform names
        for p in PLATFORMS:
            text = re.sub(rf"\b{p}\b", "", text)

        # Remove stop words
        stops = ["for", "on", "from", "about", "in", "at", "the", "a", "an",
                 "and", "or", "to", "me", "please", "can", "you", "i", "want",
                 "need", "with", "using", "show", "give", "find", "search", "get"]
        words = [w for w in text.split() if w.lower() not in stops and len(w) > 1]

        # Remove location from query
        if cmd.location:
            loc_words = cmd.location.lower().split()
            words     = [w for w in words if w.lower() not in loc_words]

        return " ".join(words).strip()


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser   = CommandParser()
    examples = [
        "scrape linkedin for python developer jobs in Nairobi",
        "find leads in fintech industry Kenya",
        "deep search twitter for posts about Safaricom",
        "post on facebook: Hello everyone, check out my new project!",
        "find 100 job openings for data analyst in Nairobi",
        "market research on solar energy in East Africa",
        "scrape https://example.com for emails and phones",
        "search google for python freelance gigs remote",
    ]
    for ex in examples:
        c = parser.parse(ex)
        print(f"\nInput:     {ex}")
        print(f"Intent:    {c.intent}")
        print(f"Query:     {c.query}")
        print(f"Platforms: {c.platforms}")
        print(f"Location:  {c.location}")
        print(f"Depth:     {c.depth}")
        print(f"Limit:     {c.limit}")
