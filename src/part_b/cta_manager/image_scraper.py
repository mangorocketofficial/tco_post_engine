"""Coupang product image scraper using Playwright.

Extracts product images from Coupang product pages for use in TCO blog posts.
Operates independently from the affiliate link scraper — can run with CTA link
data (follow affiliate redirect) or A0 data (search Coupang directly).

Two access strategies (in priority order):
    1. CTA link follow: affiliate URL → 302 redirect → product page (no login)
    2. Coupang search: product name → search results → first match click

Image source: left sidebar thumbnails on product page (top 5 images).

Usage:
    # With CTA links (recommended)
    python -m src.part_b.cta_manager.image_scraper \
        --cta-data data/processed/cta_links_로봇청소기.json \
        --output data/processed/product_images_로봇청소기.json \
        --upload

    # With A0 data (independent, no CTA needed)
    python -m src.part_b.cta_manager.image_scraper \
        --a0-data data/processed/a0_selected_로봇청소기.json \
        --output data/processed/product_images_로봇청소기.json \
        --upload
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext

from src.common.logging import setup_logging

logger = setup_logging(module_name="image_scraper")


# --- Constants ---

# Separate browser profile from link_scraper (avoids profile lock conflicts)
PROFILE_DIR = Path("data/.browser_profile/coupang_image")
SCREENSHOT_DIR = Path("data/debug_screenshots")

COUPANG_SEARCH_URL = "https://www.coupang.com/np/search"

# Timeouts (ms)
NAV_TIMEOUT = 60_000
ACTION_TIMEOUT = 15_000
SETTLE_DELAY = 2_000

# Max images to extract per product
MAX_IMAGES = 5

# DOM selectors for product page thumbnails (tried in order)
# Coupang migrated from BEM (.prod-image__*) to Tailwind (.product-image) ~2025
THUMBNAIL_SELECTORS = [
    ".product-image img",           # Current Coupang (2025+, Tailwind-based)
    ".prod-image__thumbnails img",  # Legacy: standard product page
    ".prod-image__item img",        # Legacy: variant layout
    "#productImage img",            # Legacy: alternative ID-based
    ".subType-IMAGE img",           # Legacy: some categories
    ".gallery-image img",           # Gallery layout
    ".swiper-slide img",            # Swiper carousel
]

# Fallback: main product hero image (single image, when thumbnails fail)
MAIN_IMAGE_SELECTORS = [
    "img[alt='Product image']",     # Current Coupang (exact alt text)
    ".prod-image__detail img",      # Legacy: main detail image
    "img.prod-image__detail",       # Legacy: direct img class
    ".prod-image__big-img img",     # Legacy: big image variant
    ".prod-image img",              # Legacy: generic prod-image container
]

# Image element attributes to check (priority order, skip data: URI placeholders)
IMG_ATTRS = ["data-origin", "data-src", "data-lazy-src", "src"]

# Thumbnail URL → high-res URL pattern replacement
THUMB_SIZE_RE = re.compile(r"/\d+x\d+ex/")
HIGH_RES_REPLACEMENT = "/500x500ex/"


# --- Helper functions ---


def _upgrade_image_url(url: str) -> str:
    """Convert a thumbnail URL to higher resolution if possible.

    Coupang CDN uses patterns like /230x230ex/ for thumbnails.
    Replace with /500x500ex/ for better quality.
    """
    if THUMB_SIZE_RE.search(url):
        return THUMB_SIZE_RE.sub(HIGH_RES_REPLACEMENT, url)
    return url


def load_cta_products(cta_path: Path) -> tuple[str, list[dict]]:
    """Load products from CTA links JSON output.

    Returns:
        (category, products list with product_id, product_name, base_url)
    """
    with open(cta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    category = data.get("category", "unknown")
    products = data.get("products", [])
    return category, products


def load_a0_products(a0_path: Path) -> tuple[str, list[dict]]:
    """Load products from A0 selected products JSON.

    Returns:
        (category, products list with name, brand)
    """
    with open(a0_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    category = data.get("category", "unknown")
    products = data.get("final_products", [])
    return category, products


def save_image_results(
    results: list[dict], output_path: Path, category: str
):
    """Save image extraction results to JSON.

    Output format is documented in the plan:
    product_images_{CAT}.json with per-product image arrays.
    """
    output = {
        "category": category,
        "generated_at": datetime.now().isoformat(),
        "source": "coupang_image_scraper",
        "products": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    success_count = sum(1 for r in results if r.get("success"))
    logger.info(
        "Saved image data: %d/%d products to %s",
        success_count, len(results), output_path,
    )


# --- Scraper class ---


class CoupangImageScraper:
    """Extracts product images from Coupang product pages via Playwright.

    Uses a separate persistent Chrome profile from link_scraper.
    No Coupang Partners login required — accesses public product pages directly.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # --- Lifecycle ---

    async def start(self):
        """Launch Chrome with a persistent profile (separate from link_scraper)."""
        self._playwright = await async_playwright().start()

        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        user_data_dir = str(PROFILE_DIR.resolve())

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=self.headless,
            slow_mo=200,
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--hide-crash-restore-bubble",
            ],
        )

        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Dismiss "Restore pages?" infobar
        try:
            await self._page.keyboard.press("Escape")
            await self._page.wait_for_timeout(500)
        except Exception:
            pass

        logger.info(
            "Chrome launched for image scraping (profile: %s, headless=%s)",
            user_data_dir, self.headless,
        )

    async def stop(self):
        """Close browser (profile is auto-saved)."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Image scraper browser closed")

    # --- Navigation strategies ---

    async def _navigate_via_affiliate_url(self, affiliate_url: str) -> Optional[str]:
        """Follow affiliate link redirect to reach the product page.

        affiliate URL (link.coupang.com/a/xxx) → 302 redirect →
        coupang.com/vp/products/{id}

        Returns:
            Product page URL on success, None on failure.
        """
        page = self._page
        try:
            await page.goto(affiliate_url, wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await page.wait_for_timeout(SETTLE_DELAY)

            current_url = page.url
            if "coupang.com" in current_url and "/products/" in current_url:
                logger.info("Reached product page via affiliate link: %s", current_url[:80])
                return current_url
            logger.warning("Affiliate redirect did not reach product page: %s", current_url[:80])
            return None
        except Exception as e:
            logger.error("Failed to follow affiliate URL %s: %s", affiliate_url[:50], e)
            return None

    async def _navigate_via_search(self, product_name: str) -> Optional[str]:
        """Search Coupang directly and click the first result.

        Returns:
            Product page URL on success, None on failure.
        """
        page = self._page
        try:
            search_url = f"{COUPANG_SEARCH_URL}?q={product_name}"
            await page.goto(search_url, wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await page.wait_for_timeout(SETTLE_DELAY)

            # Click first product in search results
            product_link = page.locator(
                "a.search-product-link, "
                "li.search-product a, "
                ".baby-product-link"
            ).first

            await product_link.click(timeout=ACTION_TIMEOUT)
            await page.wait_for_timeout(SETTLE_DELAY)

            current_url = page.url
            if "coupang.com" in current_url:
                logger.info("Reached product page via search: %s", current_url[:80])
                return current_url
            return None
        except Exception as e:
            logger.error("Search navigation failed for '%s': %s", product_name[:30], e)
            return None

    # --- Image extraction ---

    async def _extract_thumbnail_urls(self) -> list[str]:
        """Extract image URLs from the left sidebar thumbnails.

        Tries multiple DOM selectors in order. Checks data-origin,
        data-src, data-lazy-src, and src attributes (in priority order).
        Skips data: URIs (lazy-load placeholders).
        Falls back to main product hero image if thumbnails not found.
        """
        page = self._page
        urls = []

        # Phase 1: Try thumbnail selectors (multiple images)
        for selector in THUMBNAIL_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                if not elements:
                    continue

                for el in elements[:MAX_IMAGES]:
                    url = None
                    for attr in IMG_ATTRS:
                        val = await el.get_attribute(attr)
                        if val and not val.startswith("data:"):
                            url = val
                            break
                    if url:
                        if url.startswith("//"):
                            url = "https:" + url
                        url = _upgrade_image_url(url)
                        urls.append(url)

                if urls:
                    logger.info(
                        "Extracted %d image URLs using selector: %s",
                        len(urls), selector,
                    )
                    break
            except Exception as e:
                logger.debug("Selector %s failed: %s", selector, e)
                continue

        # Phase 2: Fallback to main product hero image
        if not urls:
            logger.info("No thumbnails found, trying main product image selectors")
            for selector in MAIN_IMAGE_SELECTORS:
                try:
                    el = await page.query_selector(selector)
                    if not el:
                        continue
                    url = None
                    for attr in IMG_ATTRS:
                        val = await el.get_attribute(attr)
                        if val and not val.startswith("data:"):
                            url = val
                            break
                    if url:
                        if url.startswith("//"):
                            url = "https:" + url
                        url = _upgrade_image_url(url)
                        urls.append(url)
                        logger.info(
                            "Extracted main image using selector: %s", selector,
                        )
                        break
                except Exception as e:
                    logger.debug("Main image selector %s failed: %s", selector, e)
                    continue

        if not urls:
            logger.warning("No images found on product page (thumbnails + main)")
            await self._save_screenshot("no_images_found")

        # Deduplicate while preserving order (thumbnail + main can share same URL)
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        if len(unique_urls) < len(urls):
            logger.info(
                "Deduplicated images: %d → %d unique",
                len(urls), len(unique_urls),
            )

        return unique_urls[:MAX_IMAGES]

    # --- Image download ---

    async def _download_image_bytes(self, url: str) -> Optional[bytes]:
        """Download image bytes using the browser context's API request.

        Uses the BrowserContext's APIRequestContext which shares cookies
        with the browser session. Adds proper Referer header to avoid
        Coupang CDN anti-hotlinking blocks that return blank/white images
        for requests without proper headers.

        Returns:
            Image bytes on success, None on failure or placeholder detection.
        """
        try:
            response = await self._context.request.get(
                url,
                headers={
                    "Referer": "https://www.coupang.com/",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )

            if not response.ok:
                logger.warning(
                    "Image download failed (status %d): %s",
                    response.status, url[:80],
                )
                return None

            image_bytes = await response.body()

            # Reject tiny images (likely 1x1 placeholders)
            if len(image_bytes) < 1024:
                logger.warning(
                    "Downloaded image too small (%d bytes), likely placeholder: %s",
                    len(image_bytes), url[:80],
                )
                return None

            return image_bytes
        except Exception as e:
            logger.error("Failed to download image: %s — %s", url[:80], e)
            return None

    # --- Batch processing ---

    async def process_products_from_cta(
        self,
        products: list[dict],
        upload: bool = False,
        category: str = "",
        domain: str = "tech",
    ) -> list[dict]:
        """Extract images for products using CTA link data.

        Strategy: follow affiliate URL → product page → extract thumbnails.
        Falls back to search if affiliate redirect fails.

        Args:
            products: CTA JSON products list (product_id, product_name, base_url).
            upload: If True, process images and upload to Supabase Storage.
            category: Category name (needed for upload path).
            domain: Blog domain ("tech" or "pet") for Supabase routing.

        Returns:
            List of result dicts per product.
        """
        results = []
        processor = None
        storage = None

        if upload:
            from src.part_b.cta_manager.image_processor import ImageProcessor, slugify
            from src.part_b.publisher.storage import SupabaseStorage
            processor = ImageProcessor()
            storage = SupabaseStorage(domain=domain)

        for i, product in enumerate(products):
            name = product.get("product_name", product.get("name", "unknown"))
            product_id = product.get("product_id", "")
            base_url = product.get("base_url", "")

            logger.info(
                "--- Image extraction %d/%d: %s ---",
                i + 1, len(products), name[:50],
            )

            # Strategy 1: follow affiliate URL
            product_url = None
            if base_url:
                product_url = await self._navigate_via_affiliate_url(base_url)

            # Strategy 2: search by product name
            if not product_url:
                product_url = await self._navigate_via_search(name)

            if not product_url:
                logger.error("Could not reach product page for: %s", name[:50])
                results.append({
                    "product_id": product_id,
                    "product_name": name,
                    "product_url": "",
                    "images": [],
                    "image_count": 0,
                    "success": False,
                })
                continue

            # Extract thumbnail URLs
            image_urls = await self._extract_thumbnail_urls()

            # Build image entries
            images = []
            if upload and processor and storage and image_urls:
                from src.part_b.cta_manager.image_processor import slugify
                slug = slugify(product_id or name)
                for idx, img_url in enumerate(image_urls):
                    try:
                        # Download via browser context (shares cookies + Referer)
                        raw_bytes = await self._download_image_bytes(img_url)
                        if not raw_bytes:
                            logger.warning(
                                "Skipping blank/failed image: %s[%d]",
                                name[:30], idx,
                            )
                            images.append({
                                "index": idx,
                                "original_url": img_url,
                                "public_url": "",
                                "width": 0,
                                "height": 0,
                            })
                            continue

                        processed = processor.process_bytes(
                            raw_bytes, slug, idx, img_url,
                        )
                        upload_results = storage.upload_product_images(
                            [processed], category, slug,
                        )
                        if upload_results and upload_results[0].success:
                            images.append({
                                "index": idx,
                                "original_url": img_url,
                                "public_url": upload_results[0].public_url,
                                "width": processed.width,
                                "height": processed.height,
                            })
                        else:
                            images.append({
                                "index": idx,
                                "original_url": img_url,
                                "public_url": "",
                                "width": 0,
                                "height": 0,
                            })
                    except Exception as e:
                        logger.error(
                            "Image processing failed for %s[%d]: %s",
                            name[:30], idx, e,
                        )
                        images.append({
                            "index": idx,
                            "original_url": img_url,
                            "public_url": "",
                            "width": 0,
                            "height": 0,
                        })
            else:
                # No upload — just save URLs for later processing
                for idx, img_url in enumerate(image_urls):
                    images.append({
                        "index": idx,
                        "original_url": img_url,
                        "public_url": "",
                        "width": 0,
                        "height": 0,
                    })

            results.append({
                "product_id": product_id,
                "product_name": name,
                "product_url": product_url,
                "images": images,
                "image_count": len(images),
                "success": len(images) > 0,
            })

            if i < len(products) - 1:
                await self._page.wait_for_timeout(SETTLE_DELAY)

        return results

    async def process_products_from_a0(
        self,
        products: list[dict],
        upload: bool = False,
        category: str = "",
        domain: str = "tech",
    ) -> list[dict]:
        """Extract images for products using A0 data (search-based).

        Strategy: search Coupang by product name → extract thumbnails.

        Args:
            products: A0 JSON final_products list (name, brand).
            upload: If True, process images and upload to Supabase Storage.
            category: Category name.
            domain: Blog domain ("tech" or "pet") for Supabase routing.

        Returns:
            List of result dicts per product.
        """
        # Convert A0 format to CTA-compatible format for reuse
        cta_style = []
        for p in products:
            from src.part_b.cta_manager.link_scraper import _make_product_id
            name = p.get("name", "")
            brand = p.get("brand", "")
            cta_style.append({
                "product_id": _make_product_id(name, brand),
                "product_name": name,
                "base_url": "",  # No affiliate link — will use search strategy
            })

        return await self.process_products_from_cta(cta_style, upload, category, domain=domain)

    # --- Debug ---

    async def _save_screenshot(self, label: str):
        """Save a screenshot for debugging."""
        if not self._page:
            return
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"img_{label}_{ts}.png"
        try:
            await self._page.screenshot(path=str(path), full_page=False)
            logger.info("Screenshot saved: %s", path)
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)


# --- CLI Entry Point ---


async def run(
    cta_path: Optional[Path] = None,
    a0_path: Optional[Path] = None,
    output_path: Path = Path("data/processed/product_images.json"),
    headless: bool = False,
    upload: bool = False,
    domain: str = "tech",
):
    """Main execution flow."""
    if cta_path:
        category, products = load_cta_products(cta_path)
        mode = "cta"
    elif a0_path:
        category, products = load_a0_products(a0_path)
        mode = "a0"
    else:
        logger.error("Must provide either --cta-data or --a0-data")
        return

    if not products:
        logger.error("No products found in input data")
        return

    logger.info(
        "Category: %s | Products: %d | Mode: %s | Upload: %s | Domain: %s",
        category, len(products), mode, upload, domain,
    )

    scraper = CoupangImageScraper(headless=headless)
    try:
        await scraper.start()

        if mode == "cta":
            results = await scraper.process_products_from_cta(
                products, upload=upload, category=category, domain=domain,
            )
        else:
            results = await scraper.process_products_from_a0(
                products, upload=upload, category=category, domain=domain,
            )

        save_image_results(results, output_path, category)

        success = sum(1 for r in results if r.get("success"))
        total_images = sum(r.get("image_count", 0) for r in results)
        logger.info(
            "Complete: %d/%d products, %d total images",
            success, len(results), total_images,
        )
    finally:
        await scraper.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Coupang product image scraper"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--cta-data",
        help="Path to CTA links JSON (cta_links_{CAT}.json)",
    )
    input_group.add_argument(
        "--a0-data",
        help="Path to A0 selected products JSON (a0_selected_{CAT}.json)",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for product images JSON",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (default: headful)",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="Process images and upload to Supabase Storage",
    )
    parser.add_argument(
        "--domain", type=str, choices=["tech", "pet"], default="tech",
        help="Blog domain for Supabase routing (default: tech)",
    )
    args = parser.parse_args()

    cta_path = Path(args.cta_data) if args.cta_data else None
    a0_path = Path(args.a0_data) if args.a0_data else None
    output_path = Path(args.output)

    if cta_path and not cta_path.exists():
        logger.error("CTA file not found: %s", cta_path)
        return
    if a0_path and not a0_path.exists():
        logger.error("A0 file not found: %s", a0_path)
        return

    asyncio.run(run(
        cta_path=cta_path,
        a0_path=a0_path,
        output_path=output_path,
        headless=args.headless,
        upload=args.upload,
        domain=args.domain,
    ))


if __name__ == "__main__":
    main()
