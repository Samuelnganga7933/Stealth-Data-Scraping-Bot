"""
core/browser.py — Stealth Playwright browser engine
Human mimicry: realistic mouse, typing, scrolling, random delays
Fingerprint spoofing, proxy rotation, CAPTCHA solving
"""

import asyncio
import random
import string
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger


# ── Human behaviour constants ──────────────────────────────────────────────
HUMAN_TYPING_DELAY = (80, 220)      # ms between keystrokes
HUMAN_MOUSE_STEPS  = (10, 30)       # steps for mouse movement
PAGE_LOAD_WAIT     = (1500, 4000)   # ms after navigation
ACTION_PAUSE       = (500, 2000)    # ms between actions
SCROLL_PAUSE       = (300, 900)     # ms between scroll steps


# ── Realistic browser fingerprints ────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

LOCALES   = ["en-US", "en-GB", "en-KE", "en-ZA"]
TIMEZONES = ["Africa/Nairobi", "America/New_York", "Europe/London", "Asia/Singapore"]


class StealthBrowser:
    """
    Fully stealth async Playwright browser.
    Patches automation fingerprints, mimics human behaviour.
    """

    def __init__(
        self,
        proxy: Optional[dict] = None,
        captcha_api_key: Optional[str] = None,
        headless: bool = True,
    ):
        self.proxy           = proxy            # {"server": "http://ip:port", "username": "...", "password": "..."}
        self.captcha_key     = captcha_api_key  # 2captcha API key
        self.headless        = headless
        self._playwright     = None
        self._browser: Optional[Browser]        = None
        self._context: Optional[BrowserContext] = None
        self.user_agent      = random.choice(USER_AGENTS)
        self.viewport        = random.choice(VIEWPORTS)
        self.locale          = random.choice(LOCALES)
        self.timezone        = random.choice(TIMEZONES)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        self._playwright = await async_playwright().start()

        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--no-first-run",
            "--ignore-certificate-errors",
            "--disable-web-security",
            f"--window-size={self.viewport['width']},{self.viewport['height']}",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
            proxy=self.proxy,
        )

        self._context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport=self.viewport,
            locale=self.locale,
            timezone_id=self.timezone,
            java_script_enabled=True,
            accept_downloads=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        await self._patch_fingerprints()
        logger.info(f"Browser started | UA: {self.user_agent[:60]}...")
        return self

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *_):
        await self.stop()

    # ── Fingerprint patching ─────────────────────────────────────────────────

    async def _patch_fingerprints(self):
        """Inject JS to mask all automation signals."""
        await self._context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Fake plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client',      filename: 'internal-nacl-plugin' },
                ]
            });

            // Fake languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

            // Fake chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function(){},
                csi: function(){},
                app: {},
            };

            // Permissions API
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(params);

            // WebGL vendor spoofing
            const getParam = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Intel Inc.';
                if (param === 37446) return 'Intel Iris OpenGL Engine';
                return getParam.call(this, param);
            };

            // Canvas fingerprint noise
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i]     += Math.floor(Math.random() * 2);
                        imageData.data[i + 1] += Math.floor(Math.random() * 2);
                        imageData.data[i + 2] += Math.floor(Math.random() * 2);
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
                return origToDataURL.apply(this, arguments);
            };
        """)

    # ── Page management ──────────────────────────────────────────────────────

    async def new_page(self) -> Page:
        page = await self._context.new_page()
        await page.set_extra_http_headers({
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        })
        return page

    async def goto(self, page: Page, url: str, wait: str = "domcontentloaded"):
        await page.goto(url, wait_until=wait, timeout=30000)
        await self._human_pause(*PAGE_LOAD_WAIT)

    # ── Human mimicry ────────────────────────────────────────────────────────

    async def _human_pause(self, min_ms: int, max_ms: int):
        await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)

    async def human_type(self, page: Page, selector: str, text: str):
        """Type text with realistic per-keystroke delays and occasional typos."""
        await page.click(selector)
        await self._human_pause(300, 700)

        for char in text:
            # Occasional typo + correction (3% chance)
            if random.random() < 0.03:
                wrong = random.choice(string.ascii_lowercase)
                await page.keyboard.type(wrong, delay=random.randint(*HUMAN_TYPING_DELAY))
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await page.keyboard.type(char, delay=random.randint(*HUMAN_TYPING_DELAY))

            # Occasional pause mid-sentence (2% chance)
            if random.random() < 0.02:
                await asyncio.sleep(random.uniform(0.3, 1.2))

    async def human_click(self, page: Page, selector: str):
        """Move mouse naturally to element then click."""
        element = await page.query_selector(selector)
        if not element:
            raise Exception(f"Element not found: {selector}")

        box = await element.bounding_box()
        if not box:
            raise Exception(f"Element not visible: {selector}")

        # Target a random point inside the element (not dead center)
        target_x = box["x"] + box["width"]  * random.uniform(0.2, 0.8)
        target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

        current = await page.evaluate("() => ({ x: window.mouseX || 100, y: window.mouseY || 100 })")

        # Move in small steps (Bezier-like)
        steps = random.randint(*HUMAN_MOUSE_STEPS)
        for i in range(steps):
            t = (i + 1) / steps
            # Ease in-out
            t = t * t * (3 - 2 * t)
            mx = current["x"] + (target_x - current["x"]) * t + random.uniform(-2, 2)
            my = current["y"] + (target_y - current["y"]) * t + random.uniform(-2, 2)
            await page.mouse.move(mx, my)
            await asyncio.sleep(random.uniform(0.005, 0.015))

        await self._human_pause(50, 200)
        await page.mouse.click(target_x, target_y)
        await self._human_pause(*ACTION_PAUSE)

    async def human_scroll(self, page: Page, direction: str = "down", times: int = 3):
        """Scroll page in human-like increments."""
        for _ in range(times):
            amount = random.randint(300, 800) * (1 if direction == "down" else -1)
            await page.evaluate(f"window.scrollBy(0, {amount})")
            await self._human_pause(*SCROLL_PAUSE)

    async def random_scroll_read(self, page: Page):
        """Simulate reading — scroll slowly, pause, continue."""
        total_height = await page.evaluate("document.body.scrollHeight")
        current      = 0
        while current < total_height * 0.8:
            step     = random.randint(150, 400)
            current += step
            await page.evaluate(f"window.scrollBy(0, {step})")
            await asyncio.sleep(random.uniform(0.4, 2.5))

    # ── CAPTCHA solving ──────────────────────────────────────────────────────

    async def solve_recaptcha_v2(self, page: Page, site_key: str, url: str) -> Optional[str]:
        """Solve reCAPTCHA v2 via 2captcha service."""
        if not self.captcha_key:
            logger.warning("No 2captcha API key — skipping CAPTCHA solve")
            return None

        import httpx
        try:
            async with httpx.AsyncClient() as client:
                # Submit CAPTCHA
                r = await client.post("http://2captcha.com/in.php", data={
                    "key":       self.captcha_key,
                    "method":    "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl":   url,
                    "json":      1,
                })
                task_id = r.json().get("request")
                if not task_id:
                    return None

                logger.info(f"CAPTCHA submitted, task_id={task_id}")

                # Poll for result
                for _ in range(24):  # max 2 minutes
                    await asyncio.sleep(5)
                    r = await client.get(f"http://2captcha.com/res.php?key={self.captcha_key}&action=get&id={task_id}&json=1")
                    data = r.json()
                    if data.get("status") == 1:
                        token = data["request"]
                        logger.info("CAPTCHA solved")
                        # Inject token into page
                        await page.evaluate(f"""
                            document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                        """)
                        return token
                    elif data.get("request") != "CAPCHA_NOT_READY":
                        logger.error(f"CAPTCHA error: {data}")
                        return None

        except Exception as e:
            logger.error(f"CAPTCHA solve failed: {e}")
            return None

    # ── Login helper ─────────────────────────────────────────────────────────

    async def login(
        self,
        page: Page,
        url: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        username: str,
        password: str,
        success_url_contains: Optional[str] = None,
    ) -> bool:
        """Generic login — types credentials humanly, submits, verifies."""
        try:
            await self.goto(page, url)
            await self.human_type(page, username_selector, username)
            await self._human_pause(400, 1000)
            await self.human_type(page, password_selector, password)
            await self._human_pause(300, 800)
            await self.human_click(page, submit_selector)
            await self._human_pause(2000, 4000)

            if success_url_contains:
                return success_url_contains in page.url
            return True

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
