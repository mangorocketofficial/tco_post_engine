"""Coupang Partners affiliate link scraper using Playwright.

Automates affiliate link generation from the Coupang Partners dashboard
when API access is not available.

Uses persistent Chrome profile (channel="chrome") to avoid bot detection
by Coupang's Akamai CDN. First run requires manual login; subsequent runs
reuse the saved browser profile.

Flow:
    1. Launch real Chrome with persistent profile
    2. Login to partners.coupang.com (manual on first run, auto after)
    3. Navigate to link generation page
    4. For each product: search → select first result → generate link → copy URL

Usage:
    python -m src.part_b.cta_manager.link_scraper \
        --a0-data data/processed/a0_selected_전기면도기.json \
        --output data/processed/cta_links_전기면도기.json
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, BrowserContext

from src.common.logging import setup_logging

logger = setup_logging(module_name="link_scraper")

# --- Constants ---
# Persistent Chrome profile directory (survives between runs)
PROFILE_DIR = Path("data/.browser_profile/coupang_partners")
SCREENSHOT_DIR = Path("data/debug_screenshots")

COUPANG_BASE = "https://partners.coupang.com"
COUPANG_LOGIN_URL = f"{COUPANG_BASE}/#affiliate/ws"
COUPANG_LINK_URL = f"{COUPANG_BASE}/#affiliate/ws/link"

# Timeouts (ms)
NAV_TIMEOUT = 60_000
ACTION_TIMEOUT = 15_000
SETTLE_DELAY = 2_000


class CoupangLinkScraper:
    """Scrapes affiliate links from Coupang Partners dashboard via Playwright.

    Uses a persistent Chrome browser profile to:
    - Avoid Akamai bot detection (real Chrome fingerprint)
    - Preserve login session between runs (cookies/localStorage)
    """

    def __init__(self, headless: bool = False):
        load_dotenv()
        self.coupang_id = os.getenv("COUPANG_ID", "")
        self.coupang_pw = os.getenv("COUPANG_PASSWORD", "")

        if not self.coupang_id or not self.coupang_pw:
            raise ValueError(
                "COUPANG_ID and COUPANG_PASSWORD must be set in .env"
            )

        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # --- Lifecycle ---

    async def start(self):
        """Launch Chrome with a persistent user profile.

        Uses channel="chrome" to run the real system Chrome browser
        (not Playwright's bundled Chromium), which has a genuine browser
        fingerprint that passes Akamai bot detection.
        """
        self._playwright = await async_playwright().start()

        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        user_data_dir = str(PROFILE_DIR.resolve())

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=self.headless,
            slow_mo=300,
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--hide-crash-restore-bubble",
            ],
        )

        # Use existing page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Dismiss any "Restore pages?" infobar by pressing Escape
        try:
            await self._page.keyboard.press("Escape")
            await self._page.wait_for_timeout(500)
        except Exception:
            pass

        logger.info(
            "Chrome launched with persistent profile at %s (headless=%s)",
            user_data_dir, self.headless,
        )

    async def stop(self):
        """Close browser (profile is auto-saved by persistent context)."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed (profile preserved)")

    # --- Login ---

    async def login(self):
        """Login to Coupang Partners.

        With persistent profile, cookies are preserved between runs.
        Strategy: always go to the link generation page directly.
        If we end up on a login page, handle login (auto or manual).
        """
        page = self._page

        # Go directly to the target page — if logged in, it loads;
        # if not, Coupang redirects to login
        logger.info("Navigating to Coupang Partners link page...")
        await page.goto(COUPANG_LINK_URL, wait_until="domcontentloaded",
                        timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(5000)

        current_url = page.url
        logger.info("Current URL: %s", current_url)
        await self._save_screenshot("initial_page")

        # If we're on the link page, we're logged in
        if await self._is_logged_in():
            logger.info("Already logged in")
            return

        # We're on a login page — try auto-fill first
        logger.info("Login required. Attempting auto-login as %s ...", self.coupang_id)

        try:
            email_input = page.locator(
                'input[type="email"], input[name="email"], '
                'input[placeholder*="이메일"], input[placeholder*="아이디"], '
                'input[type="text"][name*="id"], input[type="text"][name*="login"]'
            ).first
            await email_input.fill(self.coupang_id, timeout=ACTION_TIMEOUT)

            pw_input = page.locator(
                'input[type="password"], input[name="password"]'
            ).first
            await pw_input.fill(self.coupang_pw, timeout=ACTION_TIMEOUT)

            login_btn = page.locator(
                'button[type="submit"], button:has-text("로그인"), '
                'input[type="submit"], a:has-text("로그인")'
            ).first
            await login_btn.click(timeout=ACTION_TIMEOUT)

            await page.wait_for_timeout(5000)

            if await self._is_logged_in():
                logger.info("Auto-login successful")
                return
        except Exception as e:
            logger.warning("Auto-fill failed: %s", e)

        # Auto-login failed — wait for manual login (120 seconds)
        if not self.headless:
            logger.info(
                "\n============================================"
                "\n  브라우저 창에서 직접 로그인해주세요!"
                "\n  로그인 완료되면 자동으로 진행됩니다."
                "\n  대기 시간: 최대 120초"
                "\n============================================"
            )

            for attempt in range(40):  # 40 * 3s = 120s
                await page.wait_for_timeout(3000)
                if await self._is_logged_in():
                    logger.info("Login confirmed (manual)")
                    return
                if (attempt + 1) % 5 == 0:
                    logger.info(
                        "Waiting for login... %d/120s", (attempt + 1) * 3
                    )

        await self._save_screenshot("login_final_state")
        raise RuntimeError(
            "Login failed after 120s. Run without --headless and login manually."
        )

    async def _is_logged_in(self) -> bool:
        """Strict check: must find dashboard-only UI AND not be on login/error page."""
        page = self._page
        url = page.url.lower()

        # Definitely NOT logged in if on login or error page
        if "login" in url or "access denied" in (await page.title()).lower():
            return False
        if "errors.edgesuite.net" in url:
            return False

        # Must find at least one dashboard-specific text element
        dashboard_texts = ["링크 생성", "내 실적", "로그아웃"]
        try:
            for text in dashboard_texts:
                loc = page.locator(f':text-is("{text}")')
                if await loc.count() > 0:
                    return True
        except Exception:
            pass

        # Check for the hash-based SPA route (only loads when authenticated)
        if "#affiliate" in page.url:
            try:
                # Look for any interactive element unique to the dashboard
                for sel in ['[class*="affiliate"]', '[class*="dashboard"]',
                            '[class*="gnb"]', '[class*="lnb"]']:
                    if await page.locator(sel).count() > 0:
                        return True
            except Exception:
                pass

        return False

    # --- Link Generation ---

    async def navigate_to_link_page(self):
        """Navigate to the affiliate link generation page."""
        page = self._page
        await page.goto(COUPANG_LINK_URL, wait_until="domcontentloaded",
                        timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(SETTLE_DELAY)
        logger.info("Navigated to link generation page")

    async def _scroll_down_by(self, pixels: int = 400, steps: int = 1):
        """Scroll down by a fixed amount (NOT to bottom).

        Args:
            pixels: Pixels to scroll per step.
            steps: Number of scroll steps.
        """
        page = self._page
        for _ in range(steps):
            await page.evaluate(f"window.scrollBy(0, {pixels})")
            await page.wait_for_timeout(600)

    async def _scroll_into_view(self, locator):
        """Scroll an element into view."""
        try:
            await locator.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass

    async def _execute_search(self, product_name: str) -> bool:
        """Execute product search using multiple strategies.

        Returns True if search results loaded (검색결과 text found).
        """
        page = self._page

        # --- Strategy 1: Fill input + click the adjacent blue search button ---
        # Dismiss any auth modal that might be blocking the page
        modal = page.locator('.ant-modal-wrap, [class*="modal"]')
        try:
            if await modal.count() > 0:
                logger.info("Modal detected before search, dismissing...")
                # Try clicking cancel/close button or pressing Escape
                close_btn = page.locator(
                    '.ant-modal button:has-text("취소"), '
                    '.ant-modal .ant-modal-close, '
                    '[class*="modal"] button:has-text("취소")'
                ).first
                try:
                    await close_btn.click(timeout=3000)
                except Exception:
                    await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        search_input = page.locator('input[type="text"], input[type="search"]').first
        try:
            await self._scroll_into_view(search_input)
            await search_input.click(timeout=ACTION_TIMEOUT)
            await search_input.fill("")
            await search_input.fill(product_name)
            logger.info("Filled search term: %s", product_name[:40])
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.error("Search input not found: %s", e)
            return False

        # Try clicking the blue search button next to the input via JS
        # (the button is adjacent to the input, has a magnifying glass icon)
        clicked = await page.evaluate("""() => {
            const input = document.querySelector('input[type="text"], input[type="search"]');
            if (!input) return false;
            // Look for button in the same parent container
            const parent = input.closest('div') || input.parentElement;
            if (!parent) return false;
            // Find any button/clickable in the parent or siblings
            let btn = parent.querySelector('button');
            if (!btn) {
                // Try sibling elements
                let sibling = input.nextElementSibling;
                while (sibling) {
                    if (sibling.tagName === 'BUTTON' || sibling.querySelector('button')) {
                        btn = sibling.tagName === 'BUTTON' ? sibling : sibling.querySelector('button');
                        break;
                    }
                    sibling = sibling.nextElementSibling;
                }
            }
            if (btn) { btn.click(); return true; }
            return false;
        }""")

        if clicked:
            logger.info("Clicked search button via JS (adjacent to input)")
            await page.wait_for_timeout(3000)
            if await self._has_search_results():
                return True

        # --- Strategy 2: Press Enter via keyboard (native) ---
        logger.info("Trying keyboard Enter...")
        await search_input.focus()
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)
        if await self._has_search_results():
            return True

        # --- Strategy 3: Dispatch Enter keydown event via JS ---
        logger.info("Trying JS Enter event dispatch...")
        await page.evaluate("""() => {
            const input = document.querySelector('input[type="text"], input[type="search"]');
            if (!input) return;
            input.focus();
            ['keydown', 'keypress', 'keyup'].forEach(type => {
                input.dispatchEvent(new KeyboardEvent(type, {
                    key: 'Enter', code: 'Enter', keyCode: 13,
                    which: 13, bubbles: true, cancelable: true
                }));
            });
            // Also try form submit
            const form = input.closest('form');
            if (form) form.submit();
        }""")
        await page.wait_for_timeout(3000)
        if await self._has_search_results():
            return True

        # --- Strategy 4: Click any visible search/submit button on the page ---
        logger.info("Trying all visible buttons...")
        btn_selectors = [
            'button:has(svg)', 'button:has(i)', 'button:has(img)',
            '[role="button"]', 'button[class*="search"]',
            'button[class*="submit"]', 'button[class*="icon"]',
        ]
        for sel in btn_selectors:
            try:
                # Find buttons near the search input area (y < 600px from top)
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=1000):
                    box = await btn.bounding_box()
                    if box and box["y"] > 300:  # Below the nav but in search area
                        await btn.click(timeout=3000)
                        logger.info("Clicked button: %s (y=%d)", sel, int(box["y"]))
                        await page.wait_for_timeout(3000)
                        if await self._has_search_results():
                            return True
            except Exception:
                continue

        logger.error("All search strategies failed")
        return False

    async def _has_search_results(self) -> bool:
        """Check if search results are visible (not default 골드박스 content)."""
        page = self._page
        try:
            # Look for "N 번의 검색결과" text that appears after searching
            result_text = page.locator(':text("검색결과")')
            if await result_text.count() > 0:
                logger.info("Search results confirmed (검색결과 text found)")
                return True
        except Exception:
            pass
        return False

    async def generate_link(self, product_name: str, target_price: int | None = None) -> str | None:
        """Search for a product and generate its affiliate link.

        Args:
            product_name: Full product name from A0 selection.
            target_price: Expected price (원) from A0 data for result matching.

        Returns:
            Affiliate URL string, or None on failure.
        """
        page = self._page
        await self.navigate_to_link_page()

        # --- Step 1: Scroll to search area and execute search ---
        await self._scroll_down_by(pixels=300, steps=2)
        await page.wait_for_timeout(1000)

        search_ok = await self._execute_search(product_name)
        await self._save_screenshot("after_search")

        if not search_ok:
            logger.error("Search failed for: %s", product_name)
            await self._save_screenshot("search_fail")
            return None

        # --- Step 2: Scroll down to reveal product grid ---
        await self._scroll_down_by(pixels=400, steps=2)
        await page.wait_for_timeout(1000)
        await self._save_screenshot("search_results")

        # --- Step 3+4: Select product and generate link ---
        affiliate_url = await self._select_product_and_generate(target_price=target_price)

        if affiliate_url:
            logger.info("Generated link: %s", affiliate_url[:80])
        else:
            logger.error("Failed to extract URL for: %s", product_name[:40])
            await self._save_screenshot("extract_fail")

        return affiliate_url

    async def _dump_product_dom(self):
        """Dump DOM structure of the search result area for debugging."""
        page = self._page
        dom_info = await page.evaluate("""() => {
            const info = { product_cards: [], buttons: [], links: [] };

            // Find all elements with "product" in class name
            document.querySelectorAll('[class*="product"]').forEach((el, i) => {
                if (i < 5) {
                    info.product_cards.push({
                        tag: el.tagName,
                        classes: el.className.substring(0, 120),
                        children_tags: Array.from(el.children).map(c =>
                            c.tagName + (c.className ? '.' + c.className.substring(0, 40) : '')
                        ).join(', '),
                        text: el.textContent.substring(0, 80),
                        has_input: !!el.querySelector('input'),
                        has_button: !!el.querySelector('button'),
                        has_link_btn: !!el.querySelector('button, a, [role="button"]'),
                    });
                }
            });

            // Find all buttons on the page
            document.querySelectorAll('button, [role="button"]').forEach((btn, i) => {
                if (i < 15) {
                    const rect = btn.getBoundingClientRect();
                    info.buttons.push({
                        tag: btn.tagName,
                        text: btn.textContent.trim().substring(0, 60),
                        classes: btn.className.substring(0, 80),
                        visible: rect.height > 0,
                        y: Math.round(rect.top),
                    });
                }
            });

            // Find all "링크" related text
            const allText = document.body.innerText;
            const linkMatches = allText.match(/링크[^\\n]{0,30}/g);
            if (linkMatches) {
                info.links = linkMatches.slice(0, 10);
            }

            return info;
        }""")

        logger.info("=== DOM DUMP ===")
        for i, card in enumerate(dom_info.get("product_cards", [])):
            logger.info(
                "  Card[%d]: <%s> class=%s | has_button=%s has_input=%s | text=%s",
                i, card["tag"], card["classes"][:60],
                card["has_button"], card["has_input"],
                card["text"][:50]
            )
            logger.info("    children: %s", card["children_tags"][:100])

        for btn in dom_info.get("buttons", []):
            if btn["visible"]:
                logger.info(
                    "  Button: '%s' class=%s y=%d",
                    btn["text"][:40], btn["classes"][:50], btn["y"]
                )

        for link_text in dom_info.get("links", []):
            logger.info("  Link text: %s", link_text)

        logger.info("=== END DOM DUMP ===")
        return dom_info

    async def _find_best_price_match(self, item_count: int, target_price: int) -> int:
        """Find the product-item whose price is closest to target_price.

        Extracts price text from each product-item, parses Korean won format
        (e.g. "399,000원"), and returns the index of the best match.
        Only considers items within 30% of the target price.
        """
        import re as _re
        page = self._page
        best_idx = 0
        best_diff = float("inf")
        MAX_ITEMS_TO_CHECK = min(item_count, 12)  # Don't check too many

        for idx in range(MAX_ITEMS_TO_CHECK):
            try:
                item = page.locator('.product-item').nth(idx)
                text = await item.text_content(timeout=2000)
                if not text:
                    continue
                # Extract price: "399,000원" or "1,190,000원"
                prices = _re.findall(r'[\d,]+원', text)
                for price_str in prices:
                    price_val = int(price_str.replace(',', '').replace('원', ''))
                    if price_val < 1000:  # Skip percentages parsed as prices
                        continue
                    diff = abs(price_val - target_price)
                    # Within 30% tolerance
                    if diff < best_diff and diff / target_price < 0.3:
                        best_diff = diff
                        best_idx = idx
                        logger.info(
                            "  item[%d] price %s원 (diff: %s원)",
                            idx, f"{price_val:,}", f"{diff:,}",
                        )
            except Exception:
                continue

        return best_idx

    async def _select_product_and_generate(self, target_price: int | None = None) -> str | None:
        """Click the '링크 생성' button inside the best-matching product-item.

        When target_price is provided, iterates through product-items to find
        the one whose displayed price is closest to the expected A0 price.
        Falls back to the first item if no price match is found.

        DOM structure (from dump):
          DIV.product-list
            DIV.product-row
              DIV.product-item  (has 2 buttons: "상품보기" + "링크 생성")

        Each product-item has 2 hidden buttons (shown on hover):
          - Button 0: "상품보기" (opens Coupang product page — DO NOT click)
          - Button 1: "링크 생성" (generates affiliate link — THIS ONE)
        """
        page = self._page

        item_count = await page.locator('.product-item').count()
        logger.info("Found %d product-item elements", item_count)

        # --- Price matching: find the best product-item ---
        best_idx = 0
        if target_price and item_count > 1:
            best_idx = await self._find_best_price_match(item_count, target_price)
            if best_idx != 0:
                logger.info("Price match: selected item[%d] (target: %s원)", best_idx, f"{target_price:,}")

        first_item = page.locator('.product-item').nth(best_idx)

        if item_count == 0:
            logger.error("No .product-item elements found")
            await self._save_screenshot("no_product_items")
            return None

        # Scroll into view and hover to reveal hidden buttons
        await self._scroll_into_view(first_item)
        await page.wait_for_timeout(500)
        await first_item.hover()
        await page.wait_for_timeout(1000)
        await self._save_screenshot("after_hover")

        btn_count = await first_item.locator('button').count()
        logger.info("Buttons inside first product-item: %d", btn_count)

        # Log all button texts for debugging
        for i in range(btn_count):
            try:
                text = await first_item.locator('button').nth(i).text_content()
                logger.info("  Button[%d]: '%s'", i, (text or "").strip()[:30])
            except Exception:
                pass

        # --- Click the SECOND button (링크 생성), not the first (상품보기) ---
        linkgen_btn = None

        # Strategy 1: Find button by text content "링크"
        linkgen_in_item = first_item.locator('button:has-text("링크")')
        try:
            if await linkgen_in_item.count() > 0:
                linkgen_btn = linkgen_in_item.first
                logger.info("Found '링크' button inside product-item by text")
        except Exception:
            pass

        # Strategy 2: Use the last button (index 1) — "링크 생성" is second
        if not linkgen_btn and btn_count >= 2:
            linkgen_btn = first_item.locator('button').nth(1)
            logger.info("Using second button (index 1) as linkgen")

        # Strategy 3: Any button that is NOT "상품보기"
        if not linkgen_btn:
            for i in range(btn_count):
                btn = first_item.locator('button').nth(i)
                try:
                    text = (await btn.text_content() or "").strip()
                    if "상품" not in text and "보기" not in text:
                        linkgen_btn = btn
                        logger.info("Using button[%d] '%s' (not 상품보기)", i, text[:20])
                        break
                except Exception:
                    continue

        if not linkgen_btn:
            logger.error("Could not find 링크생성 button in product-item")
            await self._save_screenshot("no_linkgen_btn")
            return None

        # Close any extra tabs that might have opened from previous attempts
        while len(self._context.pages) > 1:
            extra = self._context.pages[-1]
            await extra.close()

        # Click the 링크 생성 button
        try:
            await linkgen_btn.click(force=True, timeout=ACTION_TIMEOUT)
            logger.info("Clicked '링크 생성' button in product-item")
        except Exception as e:
            # Fallback: JS click on the correct button
            logger.warning("Playwright click failed, trying JS: %s", e)
            await page.evaluate("""() => {
                const item = document.querySelector('.product-item');
                if (!item) return;
                const buttons = item.querySelectorAll('button');
                // Click the last button (링크 생성), not the first (상품보기)
                const btn = buttons[buttons.length - 1];
                if (btn) {
                    btn.style.display = 'inline-block';
                    btn.style.visibility = 'visible';
                    btn.style.opacity = '1';
                    btn.click();
                }
            }""")
            logger.info("JS-clicked last button in product-item")

        await page.wait_for_timeout(3000)
        await self._save_screenshot("after_linkgen_click")

        return await self._try_extract_after_linkgen()

    async def _handle_auth_modal(self) -> bool:
        """Handle the '인증 실패' password re-auth modal if it appears.

        The modal asks for password re-entry when generating a link.
        Returns True if modal was handled (or wasn't present).
        """
        page = self._page

        # Check if the auth modal is present
        modal = page.locator('.ant-modal-wrap.auth-modal, [class*="auth-modal"]')
        try:
            if await modal.count() == 0:
                return True  # No modal — nothing to handle

            logger.info("Auth modal detected - entering password...")

            # Fill in the password field
            pw_input = page.locator(
                '.ant-modal input[type="password"], '
                '.auth-modal input[type="password"]'
            ).first

            await pw_input.fill(self.coupang_pw, timeout=ACTION_TIMEOUT)
            await page.wait_for_timeout(500)

            # Click "확인" (confirm) button
            confirm_btn = page.locator(
                '.ant-modal button:has-text("확인"), '
                '.auth-modal button:has-text("확인")'
            ).first
            await confirm_btn.click(timeout=ACTION_TIMEOUT)
            logger.info("Submitted auth modal password")

            # Wait for modal to close
            await page.wait_for_timeout(3000)
            await self._save_screenshot("after_auth_modal")

            # Verify modal is gone (check visibility, not just DOM presence)
            try:
                visible = await modal.first.is_visible(timeout=2000)
                if not visible:
                    logger.info("Auth modal closed successfully")
                    return True
            except Exception:
                # Element removed from DOM — also means closed
                logger.info("Auth modal closed (removed from DOM)")
                return True

            # Check if step 3 is now showing (modal might still be in DOM but hidden)
            step3 = page.locator(':text("URL"), :text("link.coupang")')
            try:
                if await step3.count() > 0:
                    logger.info("Auth succeeded - step 3 visible behind modal remnant")
                    return True
            except Exception:
                pass

            logger.error("Auth modal still blocking after password entry")
            await self._save_screenshot("auth_modal_still_open")
            return False

        except Exception as e:
            logger.warning("Auth modal handling failed: %s", e)
            return False

    async def _try_extract_after_linkgen(self) -> str | None:
        """After clicking 링크생성, try to extract the affiliate URL."""
        page = self._page

        # Close any Coupang product page tabs (opened by "상품보기" mistake)
        for p in self._context.pages[1:]:
            if "coupang.com/vp/products" in p.url:
                logger.info("Closing stray product tab: %s", p.url[:60])
                await p.close()

        # Handle auth modal if present (password re-entry)
        await self._handle_auth_modal()
        await self._save_screenshot("after_linkgen_check")

        # The page should now show Step 3 with the generated URL.
        # Behind the modal, we saw: "단축 URL" section + "URL 복사" button.
        # Wait a moment for the URL to be populated.
        await page.wait_for_timeout(2000)

        # Strategy 1: Click "URL 복사" button and read clipboard
        copy_btn = page.locator(
            'button:has-text("URL 복사"), button:has-text("URL복사")'
        ).first
        try:
            if await copy_btn.count() > 0:
                await self._scroll_into_view(copy_btn)
                await copy_btn.click(timeout=ACTION_TIMEOUT)
                await page.wait_for_timeout(1000)
                url = await page.evaluate("navigator.clipboard.readText()")
                if url and url.startswith("http"):
                    logger.info("URL copied via clipboard: %s", url[:60])
                    return url.strip()
        except Exception as e:
            logger.warning("Clipboard copy failed: %s", e)

        # Strategy 2: Read from input/textarea fields
        url = await self._extract_url_from_page(page)
        if url:
            return url

        # Strategy 3: Check for "HTML 복사" button area
        try:
            html_btn = page.locator('button:has-text("HTML 복사")').first
            if await html_btn.count() > 0:
                # The HTML contains the affiliate link — extract from page
                html_content = await page.content()
                matches = re.findall(
                    r'https://link\.coupang\.com/[^\s"\'<>]+', html_content
                )
                if matches:
                    logger.info("URL found via regex near HTML복사: %s", matches[0][:60])
                    return matches[0].strip()
        except Exception:
            pass

        return None

    async def _extract_url_from_page(self, page: Page) -> str | None:
        """Try multiple strategies to extract affiliate URL from a page."""

        # Strategy 1: Regex scan the page HTML for link.coupang.com URLs
        # (fastest and most reliable — the URL is embedded in the page)
        try:
            html = await page.content()
            matches = re.findall(
                r'https://link\.coupang\.com/[^\s"\'<>]+', html
            )
            if matches:
                logger.info("URL found via regex: %s", matches[0][:60])
                return matches[0].strip()
        except Exception:
            pass

        # Strategy 2: Read from input fields (readonly or value-based)
        for sel in ['input[readonly]', 'textarea[readonly]',
                    'input[value*="link.coupang"]',
                    'input[value*="coupang.com"]',
                    '[class*="link"] input', '[class*="url"] input',
                    'input.ant-input']:
            try:
                field = page.locator(sel).first
                if await field.count() > 0:
                    val = await field.input_value(timeout=5000)
                    if val and val.startswith("http"):
                        logger.info("URL found in input field (%s): %s", sel, val[:60])
                        return val.strip()
            except Exception:
                continue

        # Strategy 3: Click "URL 복사" and read clipboard
        copy_btn = page.locator(
            'button:has-text("URL 복사"), button:has-text("URL복사")'
        ).first
        try:
            await copy_btn.scroll_into_view_if_needed(timeout=5000)
            await copy_btn.click(timeout=ACTION_TIMEOUT)
            await page.wait_for_timeout(1000)
            url = await page.evaluate("navigator.clipboard.readText()")
            if url and url.startswith("http"):
                logger.info("URL copied via clipboard: %s", url[:60])
                return url.strip()
        except Exception:
            pass

        return None

    # --- Batch Processing ---

    async def process_products(self, products: list[dict]) -> list[dict]:
        """Generate affiliate links for A0-selected products.

        Args:
            products: A0 JSON `final_products` list.

        Returns:
            List of result dicts with product_id, name, url, success flag.
        """
        results = []

        for i, product in enumerate(products):
            name = product["name"]
            brand = product.get("brand", "")
            price = product.get("price")
            logger.info(
                "--- Product %d/%d: %s ---", i + 1, len(products), name[:50]
            )

            url = await self.generate_link(name, target_price=price)
            product_id = _make_product_id(name, brand)

            results.append({
                "product_id": product_id,
                "product_name": name,
                "brand": brand,
                "base_url": url or "",
                "platform": "coupang",
                "success": url is not None,
            })

            if i < len(products) - 1:
                await self._page.wait_for_timeout(SETTLE_DELAY)

        return results

    # --- Debug Helpers ---

    async def _save_screenshot(self, label: str):
        """Save a screenshot for debugging."""
        if not self._page:
            return
        await self._save_screenshot_page(self._page, label)

    async def _save_screenshot_page(self, page: Page, label: str):
        """Save a screenshot of any page for debugging."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"{label}_{ts}.png"
        try:
            await page.screenshot(path=str(path), full_page=False)
            logger.info("Screenshot saved: %s", path)
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)


# --- Helpers ---

def _make_product_id(name: str, brand: str) -> str:
    """Create a slug-style product ID from brand + name."""
    brand_slug = brand.strip().lower().replace(" ", "-") if brand else ""
    # Take first 3 meaningful words from product name
    words = [w for w in name.split() if len(w) > 1][:3]
    name_slug = "-".join(words).lower()
    if brand_slug:
        return f"{brand_slug}_{name_slug}"
    return name_slug


def load_a0_products(a0_path: Path) -> tuple[str, list[dict]]:
    """Load category and products from A0 output JSON.

    Returns:
        (category, final_products list)
    """
    with open(a0_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    category = data.get("category", "unknown")
    products = data.get("final_products", [])
    return category, products


def save_results(results: list[dict], output_path: Path, category: str):
    """Save scraper results in CTAManager-compatible JSON.

    Output includes:
        - `cta_manager_links`: Format for CTAManager.load_links()
        - `products`: Full result details per product
    """
    cta_links = {
        "links": [
            {
                "product_id": r["product_id"],
                "base_url": r["base_url"],
                "platform": r["platform"],
                "affiliate_tag": "",
            }
            for r in results
            if r["success"]
        ]
    }

    output = {
        "category": category,
        "generated_at": datetime.now().isoformat(),
        "source": "coupang_partners_scraper",
        "products": results,
        "cta_manager_links": cta_links,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    success_count = len(cta_links["links"])
    logger.info("Saved %d/%d links to %s", success_count, len(results), output_path)


# --- CLI Entry Point ---

async def run(a0_path: Path, output_path: Path, headless: bool = False):
    """Main execution flow."""
    category, products = load_a0_products(a0_path)
    if not products:
        logger.error("No products found in A0 data: %s", a0_path)
        return

    logger.info("Category: %s | Products: %d", category, len(products))

    scraper = CoupangLinkScraper(headless=headless)
    try:
        await scraper.start()
        await scraper.login()
        results = await scraper.process_products(products)
        save_results(results, output_path, category)

        success = sum(1 for r in results if r["success"])
        logger.info("Complete: %d/%d links generated", success, len(results))
    finally:
        await scraper.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Coupang Partners affiliate link scraper"
    )
    parser.add_argument(
        "--a0-data", required=True,
        help="Path to A0 selected products JSON",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for affiliate links JSON",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (default: headful for debugging)",
    )
    args = parser.parse_args()

    a0_path = Path(args.a0_data)
    output_path = Path(args.output)

    if not a0_path.exists():
        logger.error("A0 file not found: %s", a0_path)
        return

    asyncio.run(run(a0_path, output_path, headless=args.headless))


if __name__ == "__main__":
    main()
