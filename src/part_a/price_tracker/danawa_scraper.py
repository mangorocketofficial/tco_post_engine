"""Danawa product price scraper.

Danawa (다나와) is Korea's largest price comparison site.
This scraper collects:
- Product search results for a given keyword
- Current/lowest/average pricing for individual products
- Price history chart data when available

All raw HTML is cached for audit via HTTPClient.
"""

from __future__ import annotations

import hashlib
import logging
import re
import json
import statistics
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
        kw_hash = hashlib.md5(keyword.encode()).hexdigest()[:12]
        cache_key = f"danawa_search_{kw_hash}"

        resp = self._client.get(self.SEARCH_URL, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")

        products: list[dict] = []
        # Current Danawa: li.goods-list__item with id="productItem-{code}"
        # Legacy fallback: .product_list .prod_item
        product_items = (
            soup.select("li.goods-list__item[id^='productItem']")
            or soup.select(".product_list .prod_item")
        )

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
        # Current: id="productItem-98919797" (with hyphen)
        # Legacy:  id="productItem98919797" (no hyphen)
        raw_id = item.get("id", "")
        product_code = raw_id.replace("productItem-", "").replace("productItem", "").strip()
        if not product_code:
            product_code_match = re.search(r"pcode=(\d+)", str(item))
            if product_code_match:
                product_code = product_code_match.group(1)

        if not product_code:
            return None

        # Current: span.goods-list__title  |  Legacy: .prod_name a
        name_el = (
            item.select_one("span.goods-list__title")
            or item.select_one(".prod_name a, .prod_name p")
        )
        name = clean_product_name(name_el.get_text(strip=True)) if name_el else ""

        brand_el = item.select_one(".maker, .brand")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # Current: div.goods-list__price  |  Legacy: .price_sect .price_wrap .price
        price_el = (
            item.select_one("div.goods-list__price")
            or item.select_one(".box__price-wrap .text__price em")
            or item.select_one(".price_sect .price_wrap .price")
        )
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

        # Parse product name (BEM: .text__title or legacy: .prod_tit)
        title_el = (
            soup.select_one(".top-summary .text__title")
            or soup.select_one(".prod_tit, #blog_content .tit")
        )
        raw_name = title_el.get_text(strip=True) if title_el else f"product_{product_code}"
        product_name = clean_product_name(raw_name)

        # Strategy 1: Mall price list rows
        # Current: div.price_row_type1 with div.sell-price
        # Legacy:  .list__mall-price .list-item, .prod_pricelist tr
        price_rows = (
            soup.select("div.price_row_type1")
            or soup.select(".list__mall-price .list-item")
            or soup.select(".prod_pricelist .price_list_tbl tbody tr")
        )

        for row in price_rows:
            try:
                # Current: div.sell-price or span.mall_t3_price
                price_el = (
                    row.select_one("div.sell-price")
                    or row.select_one("span.mall_t3_price")
                    or row.select_one(".sell-price .text__num")
                    or row.select_one(".price, .prc_c")
                )
                if not price_el:
                    continue
                price = self._parse_price(price_el.get_text(strip=True))
                if price <= 0:
                    continue

                is_sale = bool(
                    row.select_one(".badge__lowest, .sale, .coupon, .event, .official_mall")
                )

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

        # Strategy 2: Main lowest price display
        if not records:
            main_price_el = (
                soup.select_one("strong.num_low01")  # current
                or soup.select_one("span.text__number")  # current alt
                or soup.select_one(".price-summary .sell-price .text__num")
                or soup.select_one("#lowPriceCash .lwst_prc, .lowest_price .prc")
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

        # Strategy 3: Any element with price-like number in price containers
        if not records:
            for el in soup.select("div.price_unit, div.sell-price"):
                price = self._parse_price(el.get_text(strip=True))
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
                    break  # just need one fallback price

        # Layer 2: IQR-based outlier removal
        before_count = len(records)
        records = filter_prices_iqr(records)
        removed = before_count - len(records)
        if removed:
            logger.info(
                "IQR filter removed %d/%d records for product %s",
                removed, before_count, product_code,
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

    # Minimum valid product price in KRW.  Values below this threshold are
    # always parsing artifacts (shipping fees, coupon %, badge counts, etc.).
    MIN_PRICE_FLOOR = 1_000

    @staticmethod
    def _parse_price(text: str) -> int:
        """Extract numeric price from Korean price text.

        Handles formats like '1,234,000원', '614,740원(657몰)', '369,000원~'.
        Truncates at '원' or '~' to avoid capturing trailing numbers like '(657몰)'.

        Returns 0 for values below MIN_PRICE_FLOOR (Layer 1 absolute floor filter).
        """
        # Cut at '원', '~', or '(' to isolate the price portion
        price_part = re.split(r"[원~(]", text)[0]
        digits = re.sub(r"[^\d]", "", price_part)
        value = int(digits) if digits else 0
        if value < DanawaScraper.MIN_PRICE_FLOOR:
            return 0
        return value

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


# ---------------------------------------------------------------------------
# Module-level utility functions
# ---------------------------------------------------------------------------

# Danawa UI text fragments that leak into product names via get_text().
_NAME_JUNK_PATTERNS = re.compile(
    r"VS검색하기|VS검색 도움말|추천상품과스펙비교하세요|"
    r"스펙비교하세요|"
    r"\(일반구매\)|\(공식판매\)|"
    r"닫기$|\.닫기$"
)


def clean_product_name(name: str) -> str:
    """Strip known Danawa UI artifacts from a product name."""
    cleaned = _NAME_JUNK_PATTERNS.sub("", name)
    # Collapse multiple spaces / trim dots at boundaries
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .")
    return cleaned


def filter_prices_iqr(records: list[PriceRecord]) -> list[PriceRecord]:
    """Layer 2: Remove statistical outliers using IQR on a single-product price list.

    If fewer than 4 records, IQR is unreliable — return all records unchanged.
    """
    if len(records) < 4:
        return records

    prices = sorted(r.price for r in records)
    n = len(prices)
    q1 = prices[n // 4]
    q3 = prices[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return [r for r in records if lower <= r.price <= upper]


def filter_prices_a0_reference(
    records: list[PriceRecord],
    reference_price: int,
) -> list[PriceRecord]:
    """Layer 3: Discard prices far from the A0 reference price.

    Keeps prices within [reference × 0.3, reference × 3.0].
    If reference_price is 0 or None, skip filtering (A0.1 blog-only product).
    """
    if not reference_price:
        return records
    low = reference_price * 0.3
    high = reference_price * 3.0
    return [r for r in records if low <= r.price <= high]


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Similarity between two product names.

    Uses two strategies and returns the higher score:
    1. Token-overlap (space-split) — works when both names have spaces.
    2. Bidirectional substring containment — handles Danawa names with no
       spaces (e.g. "필립스SkinIQ7000시리즈S7886/70").  Checks A-tokens in
       B-flat AND B-tokens in A-flat, returns the best result.

    Returns a float in [0, 1].
    """
    if not name_a or not name_b:
        return 0.0

    a_lower = name_a.lower()
    b_lower = name_b.lower()

    tokens_a = set(a_lower.split())
    tokens_b = set(b_lower.split())

    # Strategy 1: token overlap
    token_score = 0.0
    if tokens_a and tokens_b:
        overlap = len(tokens_a & tokens_b)
        token_score = overlap / min(len(tokens_a), len(tokens_b))

    # Strategy 2: bidirectional substring containment
    a_flat = a_lower.replace(" ", "").replace(",", "")
    b_flat = b_lower.replace(" ", "").replace(",", "")

    def _substr_ratio(tokens: set[str], target_flat: str) -> float:
        if not tokens:
            return 0.0
        found = sum(1 for t in tokens if t in target_flat)
        return found / len(tokens)

    substr_a_in_b = _substr_ratio(tokens_a, b_flat)  # A0 tokens → Danawa text
    substr_b_in_a = _substr_ratio(tokens_b, a_flat)  # Danawa tokens → A0 text

    return max(token_score, substr_a_in_b, substr_b_in_a)
