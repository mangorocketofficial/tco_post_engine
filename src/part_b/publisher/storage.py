"""Supabase Storage — Upload product images to Supabase Storage.

Uploads processed product images to a public Supabase Storage bucket
and returns public URLs for use in blog HTML.

Prerequisites:
    - Create a 'product-images' bucket in Supabase dashboard (set to public)
    - SUPABASE_URL and SUPABASE_SERVICE_KEY in .env

Usage:
    from src.part_b.publisher.storage import SupabaseStorage

    storage = SupabaseStorage()
    result = storage.upload(image_bytes, "로봇청소기/slug/slug_0.webp", "image/webp")
    print(result.public_url)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.part_b.cta_manager.image_processor import ProcessedImage

logger = logging.getLogger(__name__)

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DEFAULT_BUCKET = "product-images"


@dataclass
class UploadResult:
    """Result of a single image upload."""

    path: str  # Storage path: "{category}/{slug}/{filename}"
    public_url: str
    success: bool
    error: str = ""


# Domain → Supabase environment variable mapping
STORAGE_DOMAIN_ENV_MAP: dict[str, dict[str, str]] = {
    "tech": {"url_env": "SUPABASE_URL", "key_env": "SUPABASE_SERVICE_KEY", "label": "TECH"},
    "pet":  {"url_env": "SUPABASE_PET_URL", "key_env": "SUPABASE_PET_SERVICE_KEY", "label": "PET"},
    "baby": {"url_env": "SUPABASE_BABY_URL", "key_env": "SUPABASE_BABY_SERVICE_KEY", "label": "BABY"},
}


class SupabaseStorage:
    """Upload images to Supabase Storage and retrieve public URLs.

    Supports three Supabase projects (tech/pet/baby) via domain-based routing:
    - tech: SUPABASE_URL + SUPABASE_SERVICE_KEY
    - pet:  SUPABASE_PET_URL + SUPABASE_PET_SERVICE_KEY
    - baby: SUPABASE_BABY_URL + SUPABASE_BABY_SERVICE_KEY
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        bucket: str = DEFAULT_BUCKET,
        domain: str = "tech",
    ):
        env_cfg = STORAGE_DOMAIN_ENV_MAP.get(domain, STORAGE_DOMAIN_ENV_MAP["tech"])
        self._url = supabase_url or os.getenv(env_cfg["url_env"], "")
        self._key = supabase_key or os.getenv(env_cfg["key_env"], "")
        self._bucket = bucket
        self._domain = domain
        self._client = None

    def _get_client(self):
        """Lazy-initialize Supabase client."""
        if self._client is not None:
            return self._client
        if not self._url or not self._key:
            env_cfg = STORAGE_DOMAIN_ENV_MAP.get(self._domain, STORAGE_DOMAIN_ENV_MAP["tech"])
            raise ValueError(
                f"{env_cfg['label']} blog: {env_cfg['url_env']} / {env_cfg['key_env']} "
                f"must be set in .env. See config/.env.example."
            )
        from supabase import create_client

        self._client = create_client(self._url, self._key)
        return self._client

    def get_public_url(self, path: str) -> str:
        """Build the public URL for a storage object.

        Args:
            path: Storage path relative to bucket root.

        Returns:
            Full public URL (e.g. https://xxx.supabase.co/storage/v1/object/public/product-images/...)
        """
        url = self._url.rstrip("/")
        return f"{url}/storage/v1/object/public/{self._bucket}/{path}"

    def file_exists(self, path: str) -> bool:
        """Check if a file already exists in storage (idempotency)."""
        try:
            client = self._get_client()
            # List objects in the parent folder
            folder = "/".join(path.split("/")[:-1])
            filename = path.split("/")[-1]
            result = client.storage.from_(self._bucket).list(folder)
            return any(item.get("name") == filename for item in result)
        except Exception as e:
            logger.warning("Could not check file existence for %s: %s", path, e)
            return False

    def upload(
        self,
        data: bytes,
        path: str,
        content_type: str = "image/webp",
    ) -> UploadResult:
        """Upload a single file to Supabase Storage.

        Args:
            data: File bytes.
            path: Storage path (e.g. "로봇청소기/slug/slug_0.webp").
            content_type: MIME type.

        Returns:
            UploadResult with public_url on success.
        """
        try:
            # Skip if already uploaded (idempotency)
            if self.file_exists(path):
                logger.info("File already exists, skipping: %s", path)
                return UploadResult(
                    path=path,
                    public_url=self.get_public_url(path),
                    success=True,
                )

            client = self._get_client()
            client.storage.from_(self._bucket).upload(
                path=path,
                file=data,
                file_options={"content-type": content_type},
            )

            public_url = self.get_public_url(path)
            logger.info("Uploaded: %s → %s", path, public_url)
            return UploadResult(path=path, public_url=public_url, success=True)

        except Exception as e:
            logger.error("Upload failed for %s: %s", path, e)
            return UploadResult(
                path=path,
                public_url="",
                success=False,
                error=str(e),
            )

    @staticmethod
    def _ascii_safe_path(text: str) -> str:
        """Convert Korean/mixed text to ASCII-safe storage path component.

        Supabase Storage requires ASCII-only keys.
        Uses the publisher's brand/model slug helpers when available.
        """
        import re as _re
        # Strip Korean characters
        ascii_only = _re.sub(r"[가-힣]+", "", text).strip()
        ascii_only = ascii_only.lower()
        ascii_only = _re.sub(r"[^a-z0-9\s_-]", "", ascii_only)
        ascii_only = _re.sub(r"[\s_]+", "-", ascii_only)
        ascii_only = _re.sub(r"-{2,}", "-", ascii_only)
        ascii_only = ascii_only.strip("-")
        if ascii_only:
            return ascii_only
        # Fallback: resolve via config YAML filename
        config_dir = Path(__file__).resolve().parents[3] / "config"
        if config_dir.exists():
            for cf in sorted(config_dir.glob("category_*.yaml")):
                try:
                    content = cf.read_text(encoding="utf-8")
                    if text in content:
                        return cf.stem.replace("category_", "").replace("_", "-")
                except Exception:
                    continue
        return f"cat-{abs(hash(text)) % 100000}"

    def upload_product_images(
        self,
        images: list[ProcessedImage],
        category: str,
        product_slug: str,
    ) -> list[UploadResult]:
        """Upload a batch of processed images for one product.

        Path pattern: {category_ascii}/{product_slug_ascii}/{filename}

        Args:
            images: List of ProcessedImage from ImageProcessor.
            category: Category name (e.g. "로봇청소기").
            product_slug: Product slug (e.g. "roborock-s9-maxv").

        Returns:
            List of UploadResult (one per image).
        """
        # Supabase Storage requires ASCII-only keys
        cat_ascii = self._ascii_safe_path(category)
        slug_ascii = self._ascii_safe_path(product_slug)

        results = []
        for img in images:
            # Also ensure filename is ASCII-safe
            filename = self._ascii_safe_path(
                img.filename.rsplit(".", 1)[0]
            )
            ext = img.filename.rsplit(".", 1)[-1] if "." in img.filename else "webp"
            safe_filename = f"{filename}.{ext}"
            path = f"{cat_ascii}/{slug_ascii}/{safe_filename}"
            result = self.upload(
                data=img.data,
                path=path,
                content_type=img.content_type,
            )
            results.append(result)
        return results
