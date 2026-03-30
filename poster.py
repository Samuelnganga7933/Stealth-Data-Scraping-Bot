"""
automation/poster.py — Social media automation
Post, comment, DM using YOUR accounts
Supports: Twitter/X, LinkedIn, Facebook, Instagram, YouTube
"""

import asyncio
import random
from typing import Optional
from loguru import logger

from core.browser import StealthBrowser


class SocialPoster:
    """
    Automates posting/commenting on social platforms
    using credentials you supply.
    """

    def __init__(self, browser: StealthBrowser):
        self.browser  = browser
        self._sessions: dict[str, bool] = {}

    # ── Twitter/X ────────────────────────────────────────────────────────────

    async def twitter_post(self, text: str, credentials: dict) -> bool:
        await self._twitter_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://x.com/home")
            await asyncio.sleep(2)
            await self.browser.human_click(page, '[data-testid="tweetTextarea_0"]')
            await asyncio.sleep(0.5)
            await self.browser.human_type(page, '[data-testid="tweetTextarea_0"]', text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, '[data-testid="tweetButtonInline"]')
            await asyncio.sleep(3)
            logger.success("Twitter: post published")
            return True
        except Exception as e:
            logger.error(f"Twitter post error: {e}")
            return False
        finally:
            await page.close()

    async def twitter_reply(self, tweet_url: str, text: str, credentials: dict) -> bool:
        await self._twitter_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, tweet_url)
            await asyncio.sleep(2)
            await self.browser.human_click(page, '[data-testid="reply"]')
            await asyncio.sleep(1)
            await self.browser.human_type(page, '[data-testid="tweetTextarea_0"]', text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, '[data-testid="tweetButton"]')
            await asyncio.sleep(2)
            logger.success("Twitter: reply posted")
            return True
        except Exception as e:
            logger.error(f"Twitter reply error: {e}")
            return False
        finally:
            await page.close()

    async def _twitter_login(self, credentials: dict):
        if self._sessions.get("twitter"):
            return
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://x.com/i/flow/login")
            await asyncio.sleep(3)
            await self.browser.human_type(page, 'input[autocomplete="username"]', credentials["username"])
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            await self.browser.human_type(page, 'input[name="password"]', credentials["password"])
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            self._sessions["twitter"] = True
            logger.info("Twitter session active")
        except Exception as e:
            logger.error(f"Twitter login: {e}")
        finally:
            await page.close()

    # ── Facebook ─────────────────────────────────────────────────────────────

    async def facebook_post(self, text: str, credentials: dict) -> bool:
        await self._facebook_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://www.facebook.com")
            await asyncio.sleep(2)
            await self.browser.human_click(page, '[aria-label="What\'s on your mind"]')
            await asyncio.sleep(1)
            await self.browser.human_type(page, '[aria-label="What\'s on your mind"]', text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, '[aria-label="Post"]')
            await asyncio.sleep(3)
            logger.success("Facebook: post published")
            return True
        except Exception as e:
            logger.error(f"Facebook post error: {e}")
            return False
        finally:
            await page.close()

    async def facebook_comment(self, post_url: str, text: str, credentials: dict) -> bool:
        await self._facebook_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, post_url)
            await asyncio.sleep(2)
            comment_box = await page.query_selector('[aria-label="Write a comment"]')
            if not comment_box:
                return False
            await comment_box.click()
            await asyncio.sleep(0.5)
            await self.browser.human_type(page, '[aria-label="Write a comment"]', text)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            logger.success("Facebook: comment posted")
            return True
        except Exception as e:
            logger.error(f"Facebook comment error: {e}")
            return False
        finally:
            await page.close()

    async def _facebook_login(self, credentials: dict):
        if self._sessions.get("facebook"):
            return
        page = await self.browser.new_page()
        try:
            await self.browser.login(
                page,
                url="https://www.facebook.com/login",
                username_selector="#email",
                password_selector="#pass",
                submit_selector='[name="login"]',
                username=credentials["username"],
                password=credentials["password"],
                success_url_contains="facebook.com/",
            )
            self._sessions["facebook"] = True
            logger.info("Facebook session active")
        except Exception as e:
            logger.error(f"Facebook login: {e}")
        finally:
            await page.close()

    # ── Instagram ────────────────────────────────────────────────────────────

    async def instagram_post_caption(self, image_path: str, caption: str, credentials: dict) -> bool:
        """Post an image to Instagram (requires image file path)."""
        await self._instagram_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://www.instagram.com")
            await asyncio.sleep(2)
            # Click new post button
            new_post = await page.query_selector('svg[aria-label="New post"]')
            if new_post:
                await new_post.click()
                await asyncio.sleep(1)
            # Upload image
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(image_path)
                await asyncio.sleep(2)
            # Next buttons
            for _ in range(2):
                next_btn = await page.query_selector('div[role="button"]:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(1.5)
            # Caption
            caption_box = await page.query_selector('div[aria-label="Write a caption"]')
            if caption_box:
                await caption_box.click()
                await self.browser.human_type(page, 'div[aria-label="Write a caption"]', caption)
            # Share
            share_btn = await page.query_selector('div[role="button"]:has-text("Share")')
            if share_btn:
                await share_btn.click()
                await asyncio.sleep(4)
            logger.success("Instagram: post published")
            return True
        except Exception as e:
            logger.error(f"Instagram post error: {e}")
            return False
        finally:
            await page.close()

    async def _instagram_login(self, credentials: dict):
        if self._sessions.get("instagram"):
            return
        page = await self.browser.new_page()
        try:
            await self.browser.login(
                page,
                url="https://www.instagram.com/accounts/login",
                username_selector='input[name="username"]',
                password_selector='input[name="password"]',
                submit_selector='button[type="submit"]',
                username=credentials["username"],
                password=credentials["password"],
            )
            self._sessions["instagram"] = True
            logger.info("Instagram session active")
        except Exception as e:
            logger.error(f"Instagram login: {e}")
        finally:
            await page.close()

    # ── LinkedIn ─────────────────────────────────────────────────────────────

    async def linkedin_post(self, text: str, credentials: dict) -> bool:
        await self._linkedin_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://www.linkedin.com/feed/")
            await asyncio.sleep(2)
            await self.browser.human_click(page, ".share-box-feed-entry__trigger")
            await asyncio.sleep(1)
            editor = await page.query_selector(".ql-editor")
            if editor:
                await editor.click()
                await self.browser.human_type(page, ".ql-editor", text)
            await asyncio.sleep(1)
            await self.browser.human_click(page, "button.share-actions__primary-action")
            await asyncio.sleep(3)
            logger.success("LinkedIn: post published")
            return True
        except Exception as e:
            logger.error(f"LinkedIn post error: {e}")
            return False
        finally:
            await page.close()

    async def _linkedin_login(self, credentials: dict):
        if self._sessions.get("linkedin"):
            return
        page = await self.browser.new_page()
        try:
            await self.browser.login(
                page,
                url="https://www.linkedin.com/login",
                username_selector="#username",
                password_selector="#password",
                submit_selector='[type="submit"]',
                username=credentials["username"],
                password=credentials["password"],
            )
            self._sessions["linkedin"] = True
            logger.info("LinkedIn session active")
        except Exception as e:
            logger.error(f"LinkedIn login: {e}")
        finally:
            await page.close()

    # ── YouTube ──────────────────────────────────────────────────────────────

    async def youtube_comment(self, video_url: str, text: str, credentials: dict) -> bool:
        """Post a comment on a YouTube video (uses Google login)."""
        await self._youtube_login(credentials)
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, video_url)
            await asyncio.sleep(4)
            await self.browser.human_scroll(page, "down", times=2)
            await asyncio.sleep(1)
            comment_box = await page.query_selector("#simplebox-placeholder")
            if comment_box:
                await comment_box.click()
                await asyncio.sleep(1)
                await self.browser.human_type(page, "#contenteditable-root", text)
                await asyncio.sleep(1)
                submit = await page.query_selector("#submit-button")
                if submit:
                    await submit.click()
                    await asyncio.sleep(2)
            logger.success("YouTube: comment posted")
            return True
        except Exception as e:
            logger.error(f"YouTube comment error: {e}")
            return False
        finally:
            await page.close()

    async def _youtube_login(self, credentials: dict):
        if self._sessions.get("youtube"):
            return
        page = await self.browser.new_page()
        try:
            await self.browser.goto(page, "https://accounts.google.com/signin")
            await asyncio.sleep(2)
            await self.browser.human_type(page, 'input[type="email"]', credentials["username"])
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            await self.browser.human_type(page, 'input[type="password"]', credentials["password"])
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            self._sessions["youtube"] = True
            logger.info("YouTube/Google session active")
        except Exception as e:
            logger.error(f"YouTube login: {e}")
        finally:
            await page.close()
