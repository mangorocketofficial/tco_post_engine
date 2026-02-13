"""Supabase Publisher — Upload TCO blog posts to Supabase-backed Next.js blog (Step D).

Reads the TCO pipeline output (tco JSON + blog/review HTML files) and inserts
them as posts into the Supabase `posts` table. Supports dry-run mode, upsert,
and internal link placeholder resolution.

Usage:
    python -m src.part_b.publisher.supabase_publisher \
        --tco-data data/exports/tco_가습기.json \
        --blog-html data/exports/blog_가습기.html \
        --review-dir data/exports/ \
        --cta-data data/processed/cta_links_가습기.json \
        --publish
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class FAQItem(BaseModel):
    """A single FAQ question/answer pair for the faq JSONB field."""
    question: str
    answer: str


class SupabasePostRow(BaseModel):
    """Maps to the Supabase `posts` table schema."""
    slug: str
    title: str
    content: str
    category: str

    description: Optional[str] = None
    featured_image: Optional[str] = None
    coupang_url: Optional[str] = None
    coupang_product_id: Optional[str] = None
    product_name: Optional[str] = None
    product_price: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    seo_keywords: list[str] = Field(default_factory=list)
    faq: list[FAQItem] = Field(default_factory=list)
    is_published: bool = False
    word_count: int = 0
    published_at: Optional[str] = None

    def to_supabase_dict(self) -> dict:
        """Serialize for Supabase insert, omitting None values."""
        data = {}
        for field_name, value in self:
            if value is None:
                continue
            if field_name == "faq":
                data["faq"] = [item.model_dump() for item in self.faq]
            else:
                data[field_name] = value
        return data


class PublishSummary(BaseModel):
    """Summary returned after a publish run."""
    total_posts: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    posts: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# HTML Parsing Utilities
# ---------------------------------------------------------------------------

def extract_body_content(html_doc: str) -> str:
    """Extract content for the Supabase `content` field.

    Strategy:
    - If a <style> block exists in <head>, include it (preserves class-based
      CSS for tables, CTA buttons, FAQ styling).
    - Extract <body> inner HTML (all children).
    - Combine: <style> + body inner HTML.
    """
    soup = BeautifulSoup(html_doc, "lxml")

    # Extract <style> blocks from <head>
    style_parts = []
    head = soup.find("head")
    if head:
        for style_tag in head.find_all("style"):
            style_parts.append(str(style_tag))

    # Extract <body> inner HTML
    body = soup.find("body")
    if body is None:
        return html_doc  # Treat as fragment

    # Strip first <h1> — blog platform displays title from DB separately,
    # keeping <h1> in content causes the title to appear twice.
    first_h1 = body.find("h1")
    if first_h1:
        first_h1.decompose()

    body_inner = "".join(str(child) for child in body.children)

    if style_parts:
        return "\n".join(style_parts) + "\n" + body_inner
    return body_inner


def extract_title(html_doc: str) -> str:
    """Extract title from <title> tag, falling back to first <h1>."""
    soup = BeautifulSoup(html_doc, "lxml")
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def extract_description(html_doc: str) -> str:
    """Extract content from <meta name="description">."""
    soup = BeautifulSoup(html_doc, "lxml")
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"]
    return ""


def extract_faq_items(html_doc: str) -> list[FAQItem]:
    """Parse <details><summary> FAQ items into structured JSON."""
    soup = BeautifulSoup(html_doc, "lxml")
    items = []
    for details in soup.find_all("details"):
        summary = details.find("summary")
        if summary is None:
            continue
        question = summary.get_text(strip=True)
        # Answer is everything after <summary>
        answer_parts = []
        for sibling in summary.next_siblings:
            text = (
                sibling.get_text(strip=True)
                if hasattr(sibling, "get_text")
                else str(sibling).strip()
            )
            if text:
                answer_parts.append(text)
        answer = " ".join(answer_parts)
        if question and answer:
            items.append(FAQItem(question=question, answer=answer))
    return items


def strip_faq_from_content(content: str) -> str:
    """Remove FAQ section from HTML content to avoid duplication.

    The blog site renders FAQ from the `faq` JSONB field separately,
    so including FAQ in HTML content causes double rendering.
    """
    soup = BeautifulSoup(content, "lxml")
    body = soup.find("body") or soup

    for section in body.find_all("section"):
        h2 = section.find("h2")
        if h2 and "자주 묻는 질문" in h2.get_text():
            # Remove preceding <hr> divider if present
            prev_sibling = section.find_previous_sibling()
            if prev_sibling and prev_sibling.name == "hr":
                prev_sibling.decompose()
            section.decompose()
            break

    # Reconstruct: style tags + body inner HTML
    style_parts = []
    head = soup.find("head")
    if head:
        for style_tag in head.find_all("style"):
            style_parts.append(str(style_tag))

    body = soup.find("body")
    if body:
        body_inner = "".join(str(child) for child in body.children)
    else:
        body_inner = str(soup)

    if style_parts:
        return "\n".join(style_parts) + "\n" + body_inner
    return body_inner


def count_words(html_content: str) -> int:
    """Count words in HTML content (strip tags, split on whitespace)."""
    soup = BeautifulSoup(html_content, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    return len(text.split())


def _extract_first_coupang_link(html_doc: str) -> Optional[str]:
    """Extract the first Coupang affiliate link from HTML content."""
    soup = BeautifulSoup(html_doc, "lxml")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "link.coupang.com" in href or "coupang.com" in href:
            return href
    return None


def _match_product_to_tco(
    title: str, products: list[dict]
) -> Optional[dict]:
    """Match a review HTML title to a TCO JSON product via substring matching.

    Priority: exact name > model number match > brand-only (single brand).
    Brand-only match is skipped when multiple products share the same brand.
    """
    title_lower = title.lower()
    # Build reverse brand map (korean -> ascii and ascii -> korean)
    brand_aliases: dict[str, list[str]] = {}
    for kr, en in BRAND_MAP.items():
        brand_aliases.setdefault(kr.lower(), []).append(en.lower())
        brand_aliases.setdefault(en.lower(), []).append(kr.lower())

    # Pass 1: exact product name in title
    for product in products:
        name = product.get("name", "")
        if name and name.lower() in title_lower:
            return product

    # Pass 2: keyword matching (model numbers are high-specificity)
    best_product = None
    best_count = 0
    for product in products:
        name = product.get("name", "")
        name_words = [w.strip(".,;:!?()[]") for w in name.split() if len(w) >= 3]
        matched_words = [w for w in name_words if w and w.lower() in title_lower]
        matches = len(matched_words)
        has_model = any(any(c.isdigit() for c in w) for w in matched_words)
        # A single model number match is sufficient (high specificity)
        threshold = 1 if has_model else 2
        if matches >= threshold and matches > best_count:
            best_count = matches
            best_product = product
    if best_product:
        return best_product

    # Pass 3: brand-only match (only if brand is unique among products)
    brand_counts: dict[str, int] = {}
    for product in products:
        brand = product.get("brand", "").lower()
        if brand:
            all_brands = [brand] + brand_aliases.get(brand, [])
            for b in all_brands:
                brand_counts[b] = brand_counts.get(b, 0) + 1

    for product in products:
        brand = product.get("brand", "")
        if brand:
            brand_lower = brand.lower()
            brands_to_check = [brand_lower] + brand_aliases.get(brand_lower, [])
            for b in brands_to_check:
                if b in title_lower and brand_counts.get(b, 0) <= 1:
                    return product

    return None


# ---------------------------------------------------------------------------
# ASCII Slug Helpers
# ---------------------------------------------------------------------------

# Korean brand → ASCII mapping (international brand names)
BRAND_MAP: dict[str, str] = {
    "로보락": "roborock",
    "다이슨": "dyson",
    "드리미": "dreame",
    "삼성": "samsung",
    "샤오미": "xiaomi",
    "에코백스": "ecovacs",
    "나르왈": "narwal",
    "코웨이": "coway",
    "위닉스": "winix",
    "쿠쿠": "cuckoo",
    "쿠쿠전자": "cuckoo",
    "청호나이스": "chungho",
    "필립스": "philips",
    "브라운": "braun",
    "파나소닉": "panasonic",
    "아이로봇": "irobot",
    "조지루시": "zojirushi",
    "보쉬": "bosch",
    "테팔": "tefal",
    "닌자": "ninja",
    "SK매직": "sk-magic",
    "LG": "lg",
    "LG전자": "lg",
    "펫킷": "petkit",
    "퍼릿": "purrit",
    "애구애구": "petkit",
    "캐리어": "carrier",
    "신일": "shinil",
    "신일전자": "shinil",
    "위니아": "winia",
    "대웅": "daewung",
    "쿠쿠홈시스": "cuckoo",
    "딩동펫": "dingdongpet",
    "도그아이": "dogeye",
    "요기펫": "yogipet",
    # Handy vacuum brands
    "클래파": "clapa",
    "자일렉": "zailex",
    "바우아토": "bauato",
    # Humidifier brands
    "듀플렉스": "duplex",
    "다룸": "daroom",
    # Food waste processor brands
    "미닉스": "minix",
    "한일전기": "hanil",
    "한일": "hanil",
    # Auto feeder brands
    "디클": "dicle",
    "디클펫": "dicle",
    # Cat water fountain / shared pet brands
    "페키움": "petkium",
    "펫케어": "petcare",
    "닉센": "nixen",
}


def _brand_to_ascii(brand: str) -> str:
    """Map Korean brand name to ASCII slug component."""
    mapped = BRAND_MAP.get(brand)
    if mapped:
        return mapped
    # Fallback: strip Korean, keep ASCII
    ascii_only = re.sub(r"[가-힣]", "", brand).strip().lower()
    if ascii_only:
        return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return f"brand-{abs(hash(brand)) % 10000}"


_MODEL_WORD_MAP: dict[str, str] = {
    # Compound model words (MUST come before their sub-words, e.g. 퓨라맥스 before 맥스)
    "퓨라맥스": "puramax", "퓨라엑스": "purax",
    # Common product model words (Korean → ASCII)
    "디지털": "digital", "슬림": "slim", "옵틱": "optic",
    "비스포크": "bespoke", "제트": "jet", "싸이클론": "cyclone",
    "플러스": "plus", "프로": "pro", "맥스": "max", "울트라": "ultra",
    "미니": "mini", "라이트": "lite", "에어": "air", "퓨어": "pure",
    "클린": "clean", "스팀": "steam", "터보": "turbo", "파워": "power",
    "스마트": "smart", "컴팩트": "compact", "올인원": "all-in-one",
    "네오": "neo", "제로": "zero", "아이": "i", "엣지": "edge",
    "스큐빅": "scubic",
    # Model series identifiers (noise for slug — model number is sufficient)
    "앱솔루트": "", "오리진": "",
    # Noise words to strip (colors, suffixes, generic descriptors)
    "퍼플": "", "화이트": "", "블랙": "", "그레이": "", "실버": "",
    "핑크": "", "베이지": "", "네이비": "", "레드": "", "블루": "",
    "새틴그레이지": "", "단품": "", "세트": "",
    "고온세척물걸레": "", "무선청소기": "", "청소기": "",
    "로봇청소기": "", "공기청정기": "", "정수기": "",
    "제습기": "", "가습기": "", "전기면도기": "",
    # Pet product noise words
    "고양이": "", "화장실": "", "자동화장실": "", "자동": "",
    "배변통": "", "대형": "", "초대형": "", "프리미엄": "",
    "강아지": "", "배변판": "", "배변매트": "", "논슬립": "", "애견": "",
    "연장형": "", "토일렛": "toilet",
}


def _extract_model_ascii(product_name: str, brand: str) -> str:
    """Extract ASCII model identifier from product name."""
    name = product_name
    if brand:
        name = name.replace(brand, "").strip()
    # Also strip the ASCII brand name (e.g. "CUCKOO" when brand is "쿠쿠전자")
    brand_ascii = _brand_to_ascii(brand) if brand else ""
    if brand_ascii:
        name = re.sub(re.escape(brand_ascii), "", name, flags=re.IGNORECASE).strip()
    # Remove parenthetical content (internal model codes)
    name = re.sub(r"\([^)]*\)", "", name)
    # Remove bracket content [단품] etc
    name = re.sub(r"\[[^\]]*\]", "", name)
    # Strip Korean year prefix patterns: "25년", "24년" etc.
    name = re.sub(r"\d{2,4}년\s*", "", name)
    # Transliterate known Korean model words → ASCII before stripping Korean
    # Sort by key length (longest first) to prevent partial matches
    for kr, en in sorted(_MODEL_WORD_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        name = name.replace(kr, f" {en} " if en else " ")
    # Remove remaining Korean characters
    name = re.sub(r"[가-힣]+", "", name)
    # Clean up
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-")
    # Deduplicate segments: "scubic-scubic" → "scubic", "puramax-2-puramax2" → "puramax2"
    parts = name.split("-")
    if not parts:
        return name
    # Remove segments that are substrings of other segments
    filtered = [
        p for i, p in enumerate(parts)
        if not any(p in other and p != other for j, other in enumerate(parts) if i != j)
    ]
    # Remove exact duplicates preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for part in filtered:
        if part not in seen:
            deduped.append(part)
            seen.add(part)
    return "-".join(deduped)


def _resolve_category_slug(category: str) -> str:
    """Look up ASCII category slug from config YAML filename.

    Searches config/ directory for a YAML file whose content contains
    the Korean category name, then derives the English slug from the filename.
    Example: category_robot_vacuum.yaml → 'robot-vacuum'
    """
    config_dir = Path(__file__).resolve().parents[3] / "config"
    if config_dir.exists():
        for cf in sorted(config_dir.glob("category_*.yaml")):
            try:
                content = cf.read_text(encoding="utf-8")
                if category in content:
                    return cf.stem.replace("category_", "").replace("_", "-")
            except Exception:
                continue
    return category


# ---------------------------------------------------------------------------
# SupabasePublisher
# ---------------------------------------------------------------------------

class SupabasePublisher:
    """Publishes TCO pipeline output to Supabase-backed blog.

    Supports two Supabase projects (tech/pet) via domain-based routing:
    - tech: SUPABASE_URL + SUPABASE_SERVICE_KEY
    - pet:  SUPABASE_PET_URL + SUPABASE_PET_SERVICE_KEY
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        domain: str = "tech",
    ):
        if domain == "pet":
            self._supabase_url = supabase_url or os.getenv("SUPABASE_PET_URL", "")
            self._supabase_key = supabase_key or os.getenv("SUPABASE_PET_SERVICE_KEY", "")
        else:
            self._supabase_url = supabase_url or os.getenv("SUPABASE_URL", "") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
            self._supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
        self._domain = domain
        self._client = None  # Lazy init

    def _get_client(self):
        """Lazy-initialize Supabase client (only when actually publishing)."""
        if self._client is not None:
            return self._client
        if not self._supabase_url or not self._supabase_key:
            domain_label = "PET" if self._domain == "pet" else "TECH"
            env_hint = (
                "SUPABASE_PET_URL / SUPABASE_PET_SERVICE_KEY"
                if self._domain == "pet"
                else "SUPABASE_URL / SUPABASE_SERVICE_KEY"
            )
            raise ValueError(
                f"{domain_label} blog: {env_hint} must be set in .env. "
                f"See config/.env.example."
            )
        from supabase import create_client

        self._client = create_client(self._supabase_url, self._supabase_key)
        logger.info("Connected to %s blog: %s", self._domain.upper(), self._supabase_url)
        return self._client

    # --- Slug generation (ASCII-safe) ---

    @staticmethod
    def generate_comparison_slug(category_slug: str) -> str:
        """Generate an ASCII-safe slug for comparison posts.

        Rule: {category_slug}-best
        Example: robot-vacuum-best
        """
        return f"{category_slug}-best"

    @staticmethod
    def generate_review_slug(
        product_name: str,
        brand: str,
        category_slug: str,
    ) -> str:
        """Generate an ASCII-safe slug for review posts.

        Rule: {category_slug}-{brand_ascii}-{model_ascii}-review
        Example: robot-vacuum-roborock-s9-maxv-ultra-review
        """
        brand_ascii = _brand_to_ascii(brand)
        model_ascii = _extract_model_ascii(product_name, brand)
        if model_ascii:
            return f"{category_slug}-{brand_ascii}-{model_ascii}-review"
        return f"{category_slug}-{brand_ascii}-review"

    # --- Main pipeline ---

    def publish_category(
        self,
        tco_data_path: str,
        blog_html_path: str,
        review_dir: Optional[str] = None,
        cta_data_path: Optional[str] = None,
        image_data_path: Optional[str] = None,
        publish: bool = False,
        update_existing: bool = True,
        category_slug: Optional[str] = None,
    ) -> PublishSummary:
        """Build and optionally publish all posts for a category.

        Args:
            tco_data_path: Path to tco_{CATEGORY}.json
            blog_html_path: Path to blog_{CATEGORY}.html
            review_dir: Directory containing review_*.html files
            cta_data_path: Path to cta_links_{CATEGORY}.json (optional)
            image_data_path: Path to product_images_{CATEGORY}.json (optional)
            publish: Actually insert into Supabase (False = dry-run)
            update_existing: Upsert posts with matching slugs (default True to prevent duplicates)
            category_slug: ASCII category slug (e.g. 'robot-vacuum'). Auto-detected if omitted.
        """
        summary = PublishSummary()

        # Validate input files
        if not Path(tco_data_path).exists():
            summary.errors.append(f"TCO data not found: {tco_data_path}")
            return summary
        if not Path(blog_html_path).exists():
            summary.errors.append(f"Blog HTML not found: {blog_html_path}")
            return summary

        # Load data
        tco_data = json.loads(Path(tco_data_path).read_text(encoding="utf-8"))
        blog_html = Path(blog_html_path).read_text(encoding="utf-8")
        cta_data = None
        if cta_data_path and Path(cta_data_path).exists():
            cta_data = json.loads(Path(cta_data_path).read_text(encoding="utf-8"))

        image_data = None
        if image_data_path and Path(image_data_path).exists():
            image_data = json.loads(Path(image_data_path).read_text(encoding="utf-8"))

        posts: list[SupabasePostRow] = []

        # Build comparison post
        try:
            comparison_post = self.build_comparison_post(tco_data, blog_html, cta_data)
            posts.append(comparison_post)
        except Exception as e:
            summary.errors.append(f"Failed to build comparison post: {e}")
            logger.exception("Error building comparison post")

        # Build review posts
        if review_dir:
            category = tco_data.get("category", "")
            review_pattern = f"review_{category}_*.html"
            review_files = sorted(Path(review_dir).glob(review_pattern))

            for review_path in review_files:
                try:
                    review_html = review_path.read_text(encoding="utf-8")
                    title = extract_title(review_html)
                    product_data = _match_product_to_tco(
                        title, tco_data.get("products", [])
                    )
                    if product_data is None:
                        logger.warning(
                            "Could not match review '%s' to TCO product, skipping",
                            review_path.name,
                        )
                        summary.skipped += 1
                        continue
                    review_post = self.build_review_post(
                        tco_data, review_html, product_data, cta_data
                    )
                    posts.append(review_post)
                except Exception as e:
                    summary.errors.append(
                        f"Failed to build review from {review_path.name}: {e}"
                    )
                    logger.exception("Error building review post: %s", review_path.name)

        # Resolve ASCII category slug
        category = tco_data.get("category", "")
        cat_slug = category_slug or _resolve_category_slug(category)
        logger.info("Category slug: %s → %s", category, cat_slug)

        # Build brand lookup from TCO data
        brand_lookup: dict[str, str] = {}
        for p in tco_data.get("products", []):
            brand_lookup[p.get("name", "")] = p.get("brand", "")

        # Assign ASCII-safe slugs
        for post in posts:
            if post.product_name is None:
                post.slug = self.generate_comparison_slug(cat_slug)
            else:
                brand = brand_lookup.get(post.product_name, "")
                post.slug = self.generate_review_slug(
                    post.product_name, brand, cat_slug
                )

        # Deduplicate slugs (safety)
        seen_slugs: set[str] = set()
        for post in posts:
            base = post.slug
            i = 2
            while post.slug in seen_slugs:
                post.slug = f"{base}-{i}"
                i += 1
            seen_slugs.add(post.slug)

        # Assign featured_image from image data
        if image_data:
            self._assign_featured_images(posts, image_data, tco_data)

        # Resolve Korean internal links → ASCII-safe slugs
        posts = self._resolve_internal_links(posts, cat_slug, tco_data)

        # Clean up any stale placeholders (safety net)
        posts = self._cleanup_stale_placeholders(posts)

        # Set publish state when actually publishing
        if publish:
            now = datetime.now().isoformat()
            for post in posts:
                post.is_published = True
                post.published_at = now

        summary.total_posts = len(posts)

        if not publish:
            # Dry-run: populate summary without Supabase
            for post in posts:
                summary.posts.append({
                    "slug": post.slug,
                    "title": post.title,
                    "word_count": post.word_count,
                    "category": post.category,
                    "product_name": post.product_name,
                    "has_faq": len(post.faq) > 0,
                    "has_coupang_url": post.coupang_url is not None,
                })
            return summary

        # Actual publish
        for post in posts:
            result = self._upsert_post(post, update_existing)
            summary.posts.append({
                "slug": post.slug,
                "title": post.title,
                "word_count": post.word_count,
                "product_name": post.product_name,
                **result,
            })
            if result.get("action") == "inserted":
                summary.inserted += 1
            elif result.get("action") == "updated":
                summary.updated += 1
            elif result.get("action") == "skipped":
                summary.skipped += 1
            elif result.get("error"):
                summary.errors.append(f"{post.slug}: {result['error']}")

        return summary

    # --- Post builders ---

    def build_comparison_post(
        self,
        tco_data: dict,
        blog_html: str,
        cta_data: Optional[dict] = None,
    ) -> SupabasePostRow:
        """Build a SupabasePostRow for the comparison blog (Step B)."""
        category = tco_data.get("category", "")
        products = tco_data.get("products", [])
        tco_years = tco_data.get("tco_years", 3)
        domain = tco_data.get("domain", "")

        # Extract HTML parts
        content = extract_body_content(blog_html)
        title = extract_title(blog_html) or f"{category} TCO 비교"
        description = extract_description(blog_html)
        faq_items = extract_faq_items(blog_html)

        # Strip FAQ section from content (blog renders FAQ from JSONB separately)
        if faq_items:
            content = strip_faq_from_content(content)

        word_cnt = count_words(content)
        coupang_url = _extract_first_coupang_link(blog_html)

        # Generate metadata
        brands = list({p.get("brand", "") for p in products if p.get("brand")})
        tier_label_map = {"premium": "프리미엄", "mid": "중급", "budget": "가성비"}
        selected_tier = tco_data.get("selected_tier", "")
        tags = [category, f"{category} 비교"] + brands
        if selected_tier in tier_label_map:
            tags.append(f"{category} {tier_label_map[selected_tier]}")
        if domain == "pet":
            tags.append("반려동물")
        seo_keywords = [
            f"{category} 추천",
            f"{category} 비교",
            f"{tco_years}년 실비용",
        ] + [f"{b} {category}" for b in brands]

        return SupabasePostRow(
            slug="pending",
            title=title,
            content=content,
            category=category,
            description=description or None,
            coupang_url=coupang_url,
            product_name=None,
            product_price=None,
            tags=tags,
            seo_keywords=seo_keywords,
            faq=faq_items,
            word_count=word_cnt,
        )

    def build_review_post(
        self,
        tco_data: dict,
        review_html: str,
        product_data: dict,
        cta_data: Optional[dict] = None,
    ) -> SupabasePostRow:
        """Build a SupabasePostRow for an individual review (Step C)."""
        category = tco_data.get("category", "")
        domain = tco_data.get("domain", "")
        product_name = product_data.get("name", "")
        brand = product_data.get("brand", "")
        purchase_price = product_data.get("tco", {}).get("purchase_price")

        # Extract HTML parts
        content = extract_body_content(review_html)
        title = extract_title(review_html) or f"{product_name} 리뷰"
        description = extract_description(review_html)
        word_cnt = count_words(content)

        # CTA link from cta_data
        coupang_url = self._find_cta_link(product_name, cta_data)

        # Generate metadata
        all_brands = list({p.get("brand", "") for p in tco_data.get("products", []) if p.get("brand")})
        tier_label_map = {"premium": "프리미엄", "mid": "중급", "budget": "가성비"}
        selected_tier = tco_data.get("selected_tier", "")
        # Short model name: strip color suffix for concise tag
        short_name = product_name
        for color in ("화이트", "블랙", "그레이", "실버", "핑크", "베이지", "네이비", "레드", "블루"):
            if short_name.endswith(color):
                short_name = short_name[: -len(color)].strip()
                break
        tags = [category, f"{short_name} 리뷰"] + all_brands
        if selected_tier in tier_label_map:
            tags.append(f"{category} {tier_label_map[selected_tier]}")
        if domain == "pet":
            tags.append("반려동물")
        seo_keywords = [
            f"{product_name} 리뷰",
            f"{product_name} 단점",
        ]
        if brand:
            seo_keywords.append(f"{brand} {category}")

        return SupabasePostRow(
            slug="pending",
            title=title,
            content=content,
            category=category,
            description=description or None,
            coupang_url=coupang_url,
            product_name=product_name or None,
            product_price=purchase_price,
            tags=tags,
            seo_keywords=seo_keywords,
            faq=[],
            word_count=word_cnt,
        )

    # --- Internal helpers ---

    @staticmethod
    def _find_cta_link(
        product_name: str, cta_data: Optional[dict]
    ) -> Optional[str]:
        """Look up a product's CTA link from the cta_links JSON."""
        if not cta_data:
            return None
        products = cta_data.get("products", cta_data.get("results", []))
        name_lower = product_name.lower()
        for entry in products:
            entry_name = entry.get("product_name", entry.get("name", "")).lower()
            if entry_name and (entry_name in name_lower or name_lower in entry_name):
                return entry.get("base_url", entry.get("cta_url", entry.get("url")))
        return None

    @staticmethod
    def _assign_featured_images(
        posts: list[SupabasePostRow],
        image_data: dict,
        tco_data: dict,
    ) -> None:
        """Set featured_image from product_images JSON.

        Image data structure: { "products": [ { "product_name": ..., "images": [ { "public_url": ... } ] } ] }
        """
        img_products = image_data.get("products", [])
        tco_products = tco_data.get("products", [])

        for post in posts:
            if post.product_name:
                # Review post — match by product name
                for img_p in img_products:
                    img_name = img_p.get("product_name", "").lower()
                    if post.product_name.lower() in img_name or img_name in post.product_name.lower():
                        images = img_p.get("images", [])
                        if images:
                            post.featured_image = images[0].get("public_url")
                        break
            else:
                # Comparison post — use first product's image
                if img_products:
                    images = img_products[0].get("images", [])
                    if images:
                        post.featured_image = images[0].get("public_url")

    def _resolve_internal_links(
        self,
        posts: list[SupabasePostRow],
        cat_slug: str,
        tco_data: dict,
    ) -> list[SupabasePostRow]:
        """Replace Korean /posts/* internal links with ASCII-safe slugs.

        Step B/C HTML uses Korean slugs per RUNBOOK Step 0 rules
        (e.g. /posts/공기청정기-추천-비교, /posts/위닉스-at8e430-리뷰),
        but the publisher generates ASCII slugs (e.g. /posts/air-purifier-best).
        This method bridges the gap so internal links work on the live site.
        """
        category = tco_data.get("category", "")
        products = tco_data.get("products", [])

        comparison_ascii = self.generate_comparison_slug(cat_slug)

        # Build review slug info: model_ascii key → ascii slug
        product_slug_info: list[dict] = []
        for p in products:
            name = p.get("name", "")
            brand = p.get("brand", "")
            model_ascii = _extract_model_ascii(name, brand)
            ascii_slug = self.generate_review_slug(name, brand, cat_slug)
            product_slug_info.append({
                "name": name,
                "brand": brand,
                "model_ascii": model_ascii,
                "ascii_slug": ascii_slug,
            })

        # Build set of valid generated slugs for early-exit
        valid_slugs = {comparison_ascii} | {
            info["ascii_slug"] for info in product_slug_info
        }

        for post in posts:
            content = post.content

            def _replace_link(match: re.Match) -> str:
                slug_part = match.group(1)
                slug_lower = slug_part.lower()

                # Already a valid generated slug — no change needed
                if slug_part in valid_slugs:
                    return match.group(0)

                # --- Korean slug resolution (legacy) ---

                # Comparison link: contains 추천 or 비교 with category name
                if "추천" in slug_part and "비교" in slug_part:
                    return f"/posts/{comparison_ascii}"
                if category in slug_part and "비교" in slug_part:
                    return f"/posts/{comparison_ascii}"

                # Review link: ends with 리뷰
                if "리뷰" in slug_part:
                    for info in product_slug_info:
                        ma = info["model_ascii"]
                        if ma and ma in slug_lower:
                            return f"/posts/{info['ascii_slug']}"
                    # Fallback: match by model number substrings (e.g. "ac-24w20fwh")
                    for info in product_slug_info:
                        ma = info["model_ascii"]
                        if not ma:
                            continue
                        # Try each segment of the model ascii (split on brand prefix)
                        brand_ascii = _brand_to_ascii(info["brand"])
                        model_only = ma
                        if brand_ascii and ma.startswith(brand_ascii + "-"):
                            model_only = ma[len(brand_ascii) + 1:]
                        if model_only and len(model_only) >= 3 and model_only in slug_lower:
                            return f"/posts/{info['ascii_slug']}"
                    # Last resort: try brand ASCII match
                    for info in product_slug_info:
                        brand_ascii = _brand_to_ascii(info["brand"])
                        if brand_ascii and brand_ascii in slug_lower:
                            return f"/posts/{info['ascii_slug']}"

                # --- ASCII slug resolution ---
                # Handles cases where Step B/C HTML already has ASCII slugs
                # that don't match the generated slugs (e.g. LLM guessed
                # "clapa-mini-review" but generator produces "clapa-mini-review")

                # ASCII review link: {cat_slug}-...-review
                if (slug_lower.startswith(cat_slug + "-")
                        and slug_lower.endswith("-review")):
                    # Try brand + model keyword match
                    for info in product_slug_info:
                        brand_ascii = _brand_to_ascii(info["brand"]) if info["brand"] else ""
                        ma = info["model_ascii"]
                        if brand_ascii and brand_ascii in slug_lower:
                            if ma and ma in slug_lower:
                                return f"/posts/{info['ascii_slug']}"
                    # Try brand-only match (unique brand)
                    for info in product_slug_info:
                        brand_ascii = _brand_to_ascii(info["brand"]) if info["brand"] else ""
                        if brand_ascii and brand_ascii in slug_lower:
                            same_brand = [
                                i for i in product_slug_info
                                if i["brand"] and _brand_to_ascii(i["brand"]) == brand_ascii
                            ]
                            if len(same_brand) == 1:
                                return f"/posts/{same_brand[0]['ascii_slug']}"

                # ASCII comparison link
                if slug_lower.startswith(cat_slug) and "best" in slug_lower:
                    return f"/posts/{comparison_ascii}"

                return match.group(0)  # No match — keep original

            content = re.sub(r'/posts/([^"\'<>\s]+)', _replace_link, content)
            post.content = content

        return posts

    @staticmethod
    def _cleanup_stale_placeholders(
        posts: list[SupabasePostRow],
    ) -> list[SupabasePostRow]:
        """Remove any remaining {*_url} placeholders as a safety net.

        Internal links should already be resolved in Step B/C HTML using
        deterministic slugs. This method only cleans up any stale placeholders.
        """
        for post in posts:
            content = post.content
            if "{" in content and "_url}" in content:
                content = re.sub(r"\{[^}]*_url\}", "#", content)
                logger.warning(
                    "Cleaned stale URL placeholders in post '%s'", post.slug
                )
            post.content = content
        return posts

    def _upsert_post(
        self, row: SupabasePostRow, update_existing: bool = False
    ) -> dict:
        """Insert or update a post in Supabase."""
        client = self._get_client()
        data = row.to_supabase_dict()

        # Set publish timestamps
        if row.is_published and not row.published_at:
            data["published_at"] = datetime.now().isoformat()

        try:
            if update_existing:
                result = (
                    client.table("posts")
                    .upsert(data, on_conflict="slug")
                    .execute()
                )
                # Determine if it was insert or update based on response
                return {"action": "updated", "success": True}
            else:
                result = (
                    client.table("posts")
                    .insert(data)
                    .execute()
                )
                return {"action": "inserted", "success": True}
        except Exception as e:
            error_msg = str(e)
            # Handle missing column errors (e.g. 'faq' column not in pet DB)
            if "PGRST204" in error_msg or "could not find" in error_msg.lower():
                # Retry without the problematic field(s)
                for field in ("faq",):
                    if field in error_msg.lower() and field in data:
                        logger.warning(
                            "Column '%s' not found in DB for %s — retrying without it",
                            field, row.slug,
                        )
                        data.pop(field)
                try:
                    if update_existing:
                        client.table("posts").upsert(data, on_conflict="slug").execute()
                    else:
                        client.table("posts").insert(data).execute()
                    return {"action": "updated" if update_existing else "inserted", "success": True}
                except Exception as retry_e:
                    logger.error("Retry failed for %s: %s", row.slug, retry_e)
                    return {"action": "error", "error": str(retry_e)}
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                logger.warning("Slug already exists: %s (skipping)", row.slug)
                return {"action": "skipped", "error": "duplicate_slug"}
            logger.error("Supabase insert failed for %s: %s", row.slug, error_msg)
            return {"action": "error", "error": error_msg}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(summary: PublishSummary, dry_run: bool = True) -> None:
    """Print a human-readable summary of the publish run."""
    mode = "DRY RUN" if dry_run else "PUBLISHED"
    print(f"\n{'=' * 60}")
    print(f"  Supabase Publisher - {mode}")
    print(f"{'=' * 60}")
    print(f"  Total posts:  {summary.total_posts}")
    if not dry_run:
        print(f"  Inserted:     {summary.inserted}")
        print(f"  Updated:      {summary.updated}")
    print(f"  Skipped:      {summary.skipped}")
    print(f"  Errors:       {len(summary.errors)}")
    print()

    if summary.posts:
        print(f"  {'Slug':<50} {'Words':>6}  {'Type':<10}")
        print(f"  {'-' * 50} {'-' * 6}  {'-' * 10}")
        for post in summary.posts:
            post_type = "review" if post.get("product_name") else "comparison"
            slug = post["slug"]
            if len(slug) > 48:
                slug = slug[:45] + "..."
            print(f"  {slug:<50} {post.get('word_count', 0):>6}  {post_type:<10}")
        print()

    if summary.errors:
        print("  Errors:")
        for err in summary.errors:
            print(f"    - {err}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supabase Publisher — Upload TCO blog posts to Supabase (Step D)",
    )
    parser.add_argument(
        "--tco-data",
        type=str,
        required=True,
        help="Path to tco_{CATEGORY}.json (from Step A4)",
    )
    parser.add_argument(
        "--blog-html",
        type=str,
        required=True,
        help="Path to blog_{CATEGORY}.html (from Step B)",
    )
    parser.add_argument(
        "--review-dir",
        type=str,
        default=None,
        help="Directory containing review_*.html files (from Step C)",
    )
    parser.add_argument(
        "--cta-data",
        type=str,
        default=None,
        help="Path to cta_links_{CATEGORY}.json (from Step A-CTA)",
    )
    parser.add_argument(
        "--category-slug",
        type=str,
        default=None,
        help="ASCII category slug (e.g. 'robot-vacuum'). Auto-detected from config/ if omitted.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=False,
        help="Actually insert into Supabase (default: dry-run)",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        default=True,
        help="Upsert posts with matching slugs (default: True to prevent duplicates)",
    )
    parser.add_argument(
        "--image-data",
        type=str,
        default=None,
        help="Path to product_images_{CATEGORY}.json for featured_image",
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=["tech", "pet"],
        default=None,
        help="Blog domain: 'tech' or 'pet'. Auto-detected from TCO JSON if omitted.",
    )
    args = parser.parse_args()

    # Ensure UTF-8 output on Windows (cp949 can't display Korean)
    import sys
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Resolve domain: CLI arg > TCO JSON > default "tech"
    domain = args.domain
    if domain is None:
        try:
            tco_data = json.loads(Path(args.tco_data).read_text(encoding="utf-8"))
            domain = tco_data.get("domain", "tech")
        except Exception:
            domain = "tech"
    logger.info("Blog domain: %s", domain.upper())

    publisher = SupabasePublisher(domain=domain)
    summary = publisher.publish_category(
        tco_data_path=args.tco_data,
        blog_html_path=args.blog_html,
        review_dir=args.review_dir,
        cta_data_path=args.cta_data,
        image_data_path=args.image_data,
        publish=args.publish,
        update_existing=args.update_existing,
        category_slug=args.category_slug,
    )
    _print_summary(summary, dry_run=not args.publish)


if __name__ == "__main__":
    main()
