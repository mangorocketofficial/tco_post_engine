"""Image processing pipeline for Coupang product images.

Downloads product images and re-processes them to avoid duplicate-image
detection by blog platforms:
    1. Strip EXIF metadata
    2. Resize (max 800×800, aspect ratio preserved, no upscaling)
    3. Brightness adjustment (+3%)
    4. Convert to WebP (quality 85)

Usage:
    from src.part_b.cta_manager.image_processor import ImageProcessor

    processor = ImageProcessor()
    result = processor.process_url(
        "https://thumbnail6.coupangcdn.com/thumbnails/remote/...",
        product_slug="roborock-s9-maxv",
        image_index=0,
    )
    # result.data → bytes (WebP), result.filename → "roborock-s9-maxv_0.webp"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import requests
from PIL import Image, ImageEnhance

# --- Configuration ---


@dataclass
class ProcessingConfig:
    """Image processing parameters."""

    max_width: int = 800
    max_height: int = 800
    quality: int = 85
    brightness_factor: float = 1.03
    output_format: str = "WEBP"


@dataclass
class ProcessedImage:
    """Result of processing a single image."""

    data: bytes
    filename: str  # e.g. "roborock-s9-maxv_0.webp"
    content_type: str  # "image/webp"
    width: int
    height: int
    original_url: str


# --- Slug helpers ---

_STRIP_RE = re.compile(r"[^\w가-힣\s-]", re.UNICODE)
_MULTI_DASH_RE = re.compile(r"[-\s]+")


def slugify(text: str) -> str:
    """Convert Korean/English text to a URL-friendly slug.

    Examples:
        "로보락 S9 MaxV Ultra" → "로보락-s9-maxv-ultra"
        "삼성 비스포크 제트 AI" → "삼성-비스포크-제트-ai"
    """
    text = unicodedata.normalize("NFC", text.strip().lower())
    text = _STRIP_RE.sub("", text)
    text = _MULTI_DASH_RE.sub("-", text)
    return text.strip("-")


# --- Core processor ---


class ImageProcessor:
    """Downloads and re-processes product images."""

    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://www.coupang.com/",
            }
        )

    # --- Public API ---

    def process_url(
        self,
        image_url: str,
        product_slug: str,
        image_index: int,
    ) -> ProcessedImage:
        """Download an image URL and process it through the pipeline."""
        raw_bytes = self._download(image_url)
        return self.process_bytes(raw_bytes, product_slug, image_index, image_url)

    def process_bytes(
        self,
        raw_bytes: bytes,
        product_slug: str,
        image_index: int,
        original_url: str = "",
    ) -> ProcessedImage:
        """Process raw image bytes through the full pipeline."""
        img = Image.open(BytesIO(raw_bytes))

        # Validate: reject tiny placeholder images (e.g. 1x1 white pixel)
        if img.width < 10 or img.height < 10:
            raise ValueError(
                f"Image too small ({img.width}x{img.height}), likely a placeholder"
            )

        # 1. Strip EXIF by re-creating without metadata
        img = self._strip_exif(img)

        # 2. Resize (preserve aspect ratio, no upscaling)
        img = self._resize(img)

        # 3. Brightness adjustment
        img = self._adjust_brightness(img)

        # 4. Convert to WebP
        output_bytes = self._to_webp(img)

        filename = f"{product_slug}_{image_index}.webp"

        return ProcessedImage(
            data=output_bytes,
            filename=filename,
            content_type="image/webp",
            width=img.width,
            height=img.height,
            original_url=original_url,
        )

    # --- Pipeline stages ---

    def _strip_exif(self, img: Image.Image) -> Image.Image:
        """Remove EXIF metadata by copying pixel data to a new image."""
        if hasattr(img, "get_flattened_data"):
            data = list(img.get_flattened_data())
        else:
            data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)
        return clean

    def _resize(self, img: Image.Image) -> Image.Image:
        """Resize to fit within max dimensions, preserving aspect ratio.

        Does NOT upscale images smaller than the max dimensions.
        """
        max_w = self.config.max_width
        max_h = self.config.max_height

        if img.width <= max_w and img.height <= max_h:
            return img

        ratio = min(max_w / img.width, max_h / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)

        return img.resize((new_w, new_h), Image.LANCZOS)

    def _adjust_brightness(self, img: Image.Image) -> Image.Image:
        """Apply slight brightness adjustment to differentiate from original."""
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        enhancer = ImageEnhance.Brightness(img)
        return enhancer.enhance(self.config.brightness_factor)

    def _to_webp(self, img: Image.Image) -> bytes:
        """Convert to WebP format."""
        buf = BytesIO()
        if img.mode == "RGBA":
            img.save(buf, format=self.config.output_format, quality=self.config.quality)
        else:
            img = img.convert("RGB")
            img.save(buf, format=self.config.output_format, quality=self.config.quality)
        return buf.getvalue()

    # --- Downloading ---

    def _download(self, url: str, timeout: int = 10, retries: int = 2) -> bytes:
        """Download an image with retry logic."""
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as e:
                last_err = e
                if attempt < retries:
                    continue
        raise RuntimeError(f"Failed to download {url} after {retries + 1} attempts: {last_err}")
