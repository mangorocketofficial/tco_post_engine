"""Tests for Supabase Storage upload module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.part_b.publisher.storage import (
    SupabaseStorage,
    UploadResult,
)


# --- Public URL generation ---


class TestPublicUrl:
    """Test public URL construction (no network calls)."""

    def test_basic_url(self):
        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )
        url = storage.get_public_url("로봇청소기/slug/slug_0.webp")
        assert url == (
            "https://test.supabase.co/storage/v1/object/public/"
            "product-images/로봇청소기/slug/slug_0.webp"
        )

    def test_url_strips_trailing_slash(self):
        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co/",
            supabase_key="test-key",
        )
        url = storage.get_public_url("cat/slug/file.webp")
        assert "supabase.co//storage" not in url
        assert "/storage/v1/object/public/" in url

    def test_custom_bucket(self):
        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            bucket="my-bucket",
        )
        url = storage.get_public_url("path/file.webp")
        assert "my-bucket" in url
        assert "product-images" not in url

    def test_nested_path(self):
        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )
        url = storage.get_public_url("a/b/c/d/file.webp")
        assert url.endswith("a/b/c/d/file.webp")


# --- Credential validation ---


class TestCredentials:
    """Test credential checking on client initialization."""

    def test_missing_url_raises(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

        storage = SupabaseStorage(supabase_url="", supabase_key="")
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            storage._get_client()

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

        storage = SupabaseStorage(supabase_url="https://x.supabase.co", supabase_key="")
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            storage._get_client()


# --- Upload path rules ---


class TestUploadPath:
    """Test storage path construction for product images."""

    @patch("src.part_b.publisher.storage.SupabaseStorage._get_client")
    @patch("src.part_b.publisher.storage.SupabaseStorage.file_exists", return_value=False)
    def test_upload_path_pattern(self, mock_exists, mock_client):
        """Upload should use {category}/{slug}/{filename} path."""
        mock_storage = MagicMock()
        mock_client.return_value.storage.from_.return_value = mock_storage

        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )

        # Create a mock ProcessedImage
        from src.part_b.cta_manager.image_processor import ProcessedImage
        images = [ProcessedImage(
            data=b"fake-webp-data",
            filename="roborock-s9-maxv_0.webp",
            content_type="image/webp",
            width=800,
            height=800,
            original_url="https://example.com/img.jpg",
        )]

        storage.upload_product_images(images, "로봇청소기", "roborock-s9-maxv")

        # Verify upload was called with correct path
        mock_storage.upload.assert_called_once()
        call_kwargs = mock_storage.upload.call_args
        assert call_kwargs.kwargs["path"] == "로봇청소기/roborock-s9-maxv/roborock-s9-maxv_0.webp"

    @patch("src.part_b.publisher.storage.SupabaseStorage._get_client")
    @patch("src.part_b.publisher.storage.SupabaseStorage.file_exists", return_value=False)
    def test_upload_multiple_images(self, mock_exists, mock_client):
        """Multiple images should generate sequential paths."""
        mock_storage = MagicMock()
        mock_client.return_value.storage.from_.return_value = mock_storage

        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )

        from src.part_b.cta_manager.image_processor import ProcessedImage
        images = [
            ProcessedImage(b"data0", "slug_0.webp", "image/webp", 800, 800, ""),
            ProcessedImage(b"data1", "slug_1.webp", "image/webp", 800, 600, ""),
            ProcessedImage(b"data2", "slug_2.webp", "image/webp", 700, 800, ""),
        ]

        results = storage.upload_product_images(images, "category", "slug")
        assert len(results) == 3


# --- Idempotency (file_exists) ---


class TestIdempotency:
    """Test duplicate upload prevention."""

    @patch("src.part_b.publisher.storage.SupabaseStorage._get_client")
    @patch("src.part_b.publisher.storage.SupabaseStorage.file_exists", return_value=True)
    def test_skip_existing_file(self, mock_exists, mock_client):
        """Upload should be skipped if file already exists."""
        mock_storage = MagicMock()
        mock_client.return_value.storage.from_.return_value = mock_storage

        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )

        result = storage.upload(b"data", "cat/slug/file.webp", "image/webp")
        assert result.success is True
        assert result.public_url != ""
        # upload should NOT have been called
        mock_storage.upload.assert_not_called()

    @patch("src.part_b.publisher.storage.SupabaseStorage._get_client")
    def test_file_exists_list_check(self, mock_client):
        """file_exists should check folder listing for filename."""
        mock_storage_bucket = MagicMock()
        mock_storage_bucket.list.return_value = [
            {"name": "existing_0.webp"},
            {"name": "existing_1.webp"},
        ]
        mock_client.return_value.storage.from_.return_value = mock_storage_bucket

        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )

        assert storage.file_exists("cat/slug/existing_0.webp") is True
        assert storage.file_exists("cat/slug/nonexistent.webp") is False


# --- Upload error handling ---


class TestUploadErrors:
    """Test graceful error handling during upload."""

    @patch("src.part_b.publisher.storage.SupabaseStorage._get_client")
    @patch("src.part_b.publisher.storage.SupabaseStorage.file_exists", return_value=False)
    def test_upload_failure_returns_error(self, mock_exists, mock_client):
        """Failed upload should return UploadResult with success=False."""
        mock_storage = MagicMock()
        mock_storage.upload.side_effect = Exception("Network error")
        mock_client.return_value.storage.from_.return_value = mock_storage

        storage = SupabaseStorage(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )

        result = storage.upload(b"data", "path/file.webp", "image/webp")
        assert result.success is False
        assert "Network error" in result.error
        assert result.public_url == ""


# --- UploadResult dataclass ---


class TestUploadResult:
    """Test UploadResult structure."""

    def test_success_result(self):
        result = UploadResult(
            path="cat/slug/file.webp",
            public_url="https://x.supabase.co/storage/v1/object/public/bucket/cat/slug/file.webp",
            success=True,
        )
        assert result.error == ""

    def test_error_result(self):
        result = UploadResult(
            path="cat/slug/file.webp",
            public_url="",
            success=False,
            error="timeout",
        )
        assert result.error == "timeout"
