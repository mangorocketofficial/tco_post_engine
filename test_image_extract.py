"""Quick local test: extract images from Coupang and save to disk.

Tests the full flow: navigate → extract URLs → download via browser → save locally.

Usage:
    python test_image_extract.py
"""

import asyncio
from pathlib import Path

from src.part_b.cta_manager.image_scraper import CoupangImageScraper, load_cta_products


OUTPUT_DIR = Path("data/test_images")
CTA_PATH = Path("data/processed/cta_links_공기청정기.json")


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    category, products = load_cta_products(CTA_PATH)
    print(f"Category: {category}, Products: {len(products)}")

    scraper = CoupangImageScraper(headless=False)
    try:
        await scraper.start()

        for pi, product in enumerate(products):
            name = product.get("product_name", "unknown")
            base_url = product.get("base_url", "")
            print(f"\n{'='*60}")
            print(f"Product {pi+1}/{len(products)}: {name}")
            print(f"Affiliate URL: {base_url}")

            # Navigate
            product_url = None
            if base_url:
                product_url = await scraper._navigate_via_affiliate_url(base_url)
            if not product_url:
                product_url = await scraper._navigate_via_search(name)

            if not product_url:
                print("  FAIL: Could not reach product page")
                continue

            print(f"  Page: {product_url[:80]}")

            # Extract URLs (uses updated selectors)
            image_urls = await scraper._extract_thumbnail_urls()
            print(f"  Extracted {len(image_urls)} image URLs")
            for i, url in enumerate(image_urls):
                print(f"    [{i}] {url[:100]}")

            if not image_urls:
                print("  FAIL: No URLs extracted")
                continue

            # Download each image via browser context and save locally
            for i, url in enumerate(image_urls):
                raw_bytes = await scraper._download_image_bytes(url)
                if not raw_bytes:
                    print(f"    [{i}] DOWNLOAD FAIL (empty/placeholder)")
                    continue

                # Save raw
                raw_path = OUTPUT_DIR / f"product{pi+1}_img{i}_raw.jpg"
                raw_path.write_bytes(raw_bytes)

                # Process through pipeline
                from src.part_b.cta_manager.image_processor import ImageProcessor
                processor = ImageProcessor()
                try:
                    processed = processor.process_bytes(raw_bytes, f"product{pi+1}", i, url)
                    webp_path = OUTPUT_DIR / f"product{pi+1}_img{i}.webp"
                    webp_path.write_bytes(processed.data)
                    print(
                        f"    [{i}] OK: {len(raw_bytes):,}B → "
                        f"{processed.width}x{processed.height} WebP "
                        f"({len(processed.data):,}B)"
                    )
                except ValueError as e:
                    print(f"    [{i}] REJECTED: {e}")

            # Brief pause between products
            if pi < len(products) - 1:
                await scraper._page.wait_for_timeout(2000)

        print(f"\nDone! Check images in: {OUTPUT_DIR.resolve()}")

    finally:
        await scraper.stop()


if __name__ == "__main__":
    asyncio.run(main())
