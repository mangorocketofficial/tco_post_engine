"""Danawa product price scraper.

Danawa (다나와) is Korea's largest price comparison site.
This scraper collects:
- Product search results for a given keyword
- Current/lowest/average pricing for individual products
- Price history chart data when available

All raw HTML is cached for audit via HTTPClient.
"""

from __future__ import annotations

import logging
import re
import json
from datetime import date, datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from ..database.connection import get_connection
from ..database.models import Product, Price
from .models import PriceRecord, ProductPriceSummary

logger = logging.getLogger(__name__)


class DanawaScraper:
    """Scraper for Danawa price comparison site.

    Usage:
        scraper = DanawaScraper()
        products = scraper.search_products("로봇청소기")
        for product in products:
            prices = scraper.get_product_prices(product["product_code"])
    """

    SEARCH_URL = "https://search.danawa.com/dsearch.php"
    PRODUCT_URL = "https://prod.danawa.com/info/"
    PRICE_API_URL = "https://prod.danawa.com/info/ajax/getProductPriceList.ajax.php"

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def search_products(
        self, keyword: str, max_results: int = 10
    ) -> list[dict]:
        """Search Danawa for products matching a keyword.

        Args:
            keyword: Search term (e.g., "로봇청소기").
            max_results: Maximum number of results to return.

        Returns:
            List of dicts with keys: product_code, name, brand, price, image_url.
        """
        params = {
            "keyword": keyword,
            "module": "goods",
            "act": "dispMain",
        }
        cache_key = f"danawa_search_{quote(keyword)}"

        resp = self._client.get(self.SEARCH_URL, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")

        products: list[dict] = []
        product_items = soup.select(".product_list .prod_item")

        for item in product_items[:max_results]:
            try:
                product = self._parse_search_item(item)
                if product:
                    products.append(product)
            except Exception:
                logger.debug("Failed to parse search item", exc_info=True)
                continue

        logger.info("Found %d products for keyword '%s'", len(products), keyword)
        return products

    def _parse_search_item(self, item: BeautifulSoup) -> dict | None:
        """Parse a single search result item."""
        product_code = item.get("id", "").replace("productItem", "").strip()
        if not product_code:
            product_code_match = re.search(r"pcode=(\d+)", str(item))
            if product_code_match:
                product_code = product_code_match.group(1)

        if not product_code:
            return None

        name_el = item.select_one(".prod_name a, .prod_name p")
        name = name_el.get_text(strip=True) if name_el else ""

        brand_el = item.select_one(".maker, .brand")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        price_el = item.select_one(".price_sect .price_wrap .price")
        price_text = price_el.get_text(strip=True) if price_el else "0"
        price = self._parse_price(price_text)

        return {
            "product_code": product_code,
            "name": name,
            "brand": brand,
            "price": price,
        }

    def get_product_prices(self, product_code: str) -> list[PriceRecord]:
        """Fetch current price listings for a product.

        Args:
            product_code: Danawa product code.

        Returns:
            List of PriceRecord from different vendors.
        """
        url = f"{self.PRODUCT_URL}?pcode={product_code}"
        cache_key = f"danawa_product_{product_code}"

        resp = self._client.get(url, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")

        records: list[PriceRecord] = []

        # Parse product name
        title_el = soup.select_one(".prod_tit, #blog_content .tit")
        product_name = title_el.get_text(strip=True) if title_el else f"product_{product_code}"

        # Parse price table from the product page
        price_rows = soup.select(
            ".prod_pricelist .price_list_tbl tbody tr, "
            "#lowPriceList .lwst_row"
        )

        for row in price_rows:
            try:
                price_el = row.select_one(".price, .prc_c")
                if not price_el:
                    continue
                price = self._parse_price(price_el.get_text(strip=True))
                if price <= 0:
                    continue

                # Check if this is a sale/special price
                is_sale = bool(row.select_one(".sale, .coupon, .event"))

                records.append(
                    PriceRecord(
                        product_name=product_name,
                        price=price,
                        source="danawa",
                        date=date.today(),
                        is_sale=is_sale,
                        product_id=product_code,
                    )
                )
            except Exception:
                logger.debug("Failed to parse price row", exc_info=True)
                continue

        # If no detailed rows found, try the main price display
        if not records:
            main_price_el = soup.select_one(
                "#lowPriceCash .lwst_prc, .lowest_price .prc"
            )
            if main_price_el:
                price = self._parse_price(main_price_el.get_text(strip=True))
                if price > 0:
                    records.append(
                        PriceRecord(
                            product_name=product_name,
                            price=price,
                            source="danawa",
                            date=date.today(),
                            is_sale=False,
                            product_id=product_code,
                        )
                    )

        logger.info(
            "Found %d price records for product %s", len(records), product_code
        )
        return records

    def get_price_history(self, product_code: str) -> list[PriceRecord]:
        """Fetch price history chart data for a product.

        Danawa provides price trend data via an AJAX endpoint used
        by their price history chart.

        Args:
            product_code: Danawa product code.

        Returns:
            List of PriceRecord over time.
        """
        headers = {
            "Referer": f"{self.PRODUCT_URL}?pcode={product_code}",
            "X-Requested-With": "XMLHttpRequest",
        }
        params = {
            "pcode": product_code,
            "cate1": "",
            "dealerType": "price",
        }
        cache_key = f"danawa_history_{product_code}"

        try:
            resp = self._client.get(
                self.PRICE_API_URL,
                params=params,
                headers=headers,
                cache_key=cache_key,
            )
        except Exception:
            logger.warning(
                "Failed to fetch price history for %s", product_code
            )
            return []

        return self._parse_price_history_response(resp.text, product_code)

    def _parse_price_history_response(
        self, response_text: str, product_code: str
    ) -> list[PriceRecord]:
        """Parse the AJAX price history response."""
        records: list[PriceRecord] = []

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Sometimes the response is JSONP or HTML; try to extract JSON
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not json_match:
                return records
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                return records

        # Danawa price history format varies; handle common structures
        price_data = data.get("priceList", data.get("data", []))
        if isinstance(price_data, list):
            for entry in price_data:
                try:
                    price_date = self._parse_date(
                        entry.get("date", entry.get("regDate", ""))
                    )
                    price = int(entry.get("price", entry.get("minPrice", 0)))
                    if price > 0 and price_date:
                        records.append(
                            PriceRecord(
                                product_name=f"product_{product_code}",
                                price=price,
                                source="danawa",
                                date=price_date,
                                is_sale=False,
                                product_id=product_code,
                            )
                        )
                except (ValueError, TypeError):
                    continue

        return records

    def save_prices_to_db(self, records: list[PriceRecord]) -> int:
        """Save price records to the database.

        Args:
            records: List of PriceRecord to save.

        Returns:
            Number of records inserted (duplicates are skipped).
        """
        conn = get_connection(self.config)
        inserted = 0
        try:
            for record in records:
                # Find or create the product
                product_id = self._ensure_product(conn, record)

                # Insert price (skip duplicates via UNIQUE index)
                try:
                    conn.execute(
                        """
                        INSERT INTO prices (product_id, date, price, source, is_sale)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            product_id,
                            record.date.isoformat(),
                            record.price,
                            record.source,
                            int(record.is_sale),
                        ),
                    )
                    inserted += 1
                except Exception:
                    # Duplicate — skip
                    pass

            conn.commit()
            logger.info("Inserted %d/%d price records", inserted, len(records))
        finally:
            conn.close()

        return inserted

    def _ensure_product(self, conn, record: PriceRecord) -> int:
        """Get or create a product row, return its ID."""
        row = conn.execute(
            "SELECT id FROM products WHERE name = ?",
            (record.product_name,),
        ).fetchone()

        if row:
            return row["id"]

        cursor = conn.execute(
            """
            INSERT INTO products (name, brand, category)
            VALUES (?, ?, ?)
            """,
            (record.product_name, "", ""),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    @staticmethod
    def _parse_price(text: str) -> int:
        """Extract numeric price from Korean price text (e.g., '1,234,000원')."""
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """Try common date formats."""
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"):
            try:
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DanawaScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
