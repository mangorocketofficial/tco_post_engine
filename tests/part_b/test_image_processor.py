"""Tests for image processing pipeline."""

import struct
from io import BytesIO

import pytest
from PIL import Image

from src.part_b.cta_manager.image_processor import (
    ImageProcessor,
    ProcessedImage,
    ProcessingConfig,
    slugify,
)


# --- Test helpers ---


def _make_test_image(
    width: int = 1200,
    height: int = 900,
    color: tuple = (128, 100, 80),
    mode: str = "RGB",
    include_exif: bool = False,
) -> bytes:
    """Create a test image as PNG bytes."""
    img = Image.new(mode, (width, height), color)
    if include_exif:
        # Inject minimal EXIF data via piexif-style approach:
        # Create a simple EXIF segment (APP1 marker)
        from PIL.ExifTags import Base
        import piexif  # noqa: may not be installed
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_with_exif(width: int = 800, height: int = 600) -> bytes:
    """Create a JPEG with EXIF metadata."""
    img = Image.new("RGB", (width, height), (100, 150, 200))
    # Add EXIF by saving as JPEG (PIL adds basic EXIF markers)
    exif_data = img.getexif()
    exif_data[270] = "Test Image Description"  # ImageDescription tag
    exif_data[271] = "Test Camera Maker"  # Make tag
    buf = BytesIO()
    img.save(buf, format="JPEG", exif=exif_data.tobytes())
    return buf.getvalue()


# --- Slugify tests ---


class TestSlugify:
    """Test slug generation from Korean/English text."""

    def test_korean_text(self):
        assert slugify("로보락 S9 MaxV Ultra") == "로보락-s9-maxv-ultra"

    def test_korean_brand(self):
        assert slugify("삼성 비스포크 제트 AI") == "삼성-비스포크-제트-ai"

    def test_english_only(self):
        assert slugify("Dyson V15 Detect") == "dyson-v15-detect"

    def test_mixed_special_chars(self):
        result = slugify("제품명 (2024) - 특가!")
        assert "(" not in result
        assert ")" not in result
        assert "!" not in result

    def test_multiple_spaces(self):
        assert slugify("word1   word2") == "word1-word2"

    def test_leading_trailing_spaces(self):
        result = slugify("  hello world  ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_empty_string(self):
        assert slugify("") == ""


# --- ProcessingConfig tests ---


class TestProcessingConfig:
    """Test default config values."""

    def test_defaults(self):
        config = ProcessingConfig()
        assert config.max_width == 800
        assert config.max_height == 800
        assert config.quality == 85
        assert config.brightness_factor == 1.03
        assert config.output_format == "WEBP"

    def test_custom_config(self):
        config = ProcessingConfig(max_width=600, quality=70)
        assert config.max_width == 600
        assert config.quality == 70


# --- EXIF stripping tests ---


class TestExifStripping:
    """Test EXIF metadata removal."""

    def test_exif_removed_from_jpeg(self):
        """EXIF data should be stripped after processing."""
        raw = _make_jpeg_with_exif(800, 600)

        # Verify original has EXIF
        original = Image.open(BytesIO(raw))
        original_exif = original.getexif()
        assert len(original_exif) > 0, "Test image should have EXIF"

        processor = ImageProcessor()
        result = processor.process_bytes(raw, "test-product", 0)

        # Re-open processed image and check no EXIF
        processed = Image.open(BytesIO(result.data))
        processed_exif = processed.getexif()
        assert len(processed_exif) == 0, "Processed image should have no EXIF"

    def test_image_without_exif_still_works(self):
        """Images without EXIF should process without errors."""
        raw = _make_test_image(400, 300)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "no-exif", 0)
        assert isinstance(result, ProcessedImage)
        assert len(result.data) > 0


# --- Resize tests ---


class TestResize:
    """Test image resizing logic."""

    def test_large_landscape_downscaled(self):
        """1200x900 → should fit within 800x800 (becomes 800x600)."""
        raw = _make_test_image(1200, 900)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "landscape", 0)
        assert result.width <= 800
        assert result.height <= 800

    def test_large_portrait_downscaled(self):
        """900x1200 → should fit within 800x800 (becomes 600x800)."""
        raw = _make_test_image(900, 1200)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "portrait", 0)
        assert result.width <= 800
        assert result.height <= 800

    def test_large_square_downscaled(self):
        """1000x1000 → should become 800x800."""
        raw = _make_test_image(1000, 1000)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "square", 0)
        assert result.width == 800
        assert result.height == 800

    def test_small_image_not_upscaled(self):
        """400x300 → should stay 400x300 (no upscaling)."""
        raw = _make_test_image(400, 300)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "small", 0)
        assert result.width == 400
        assert result.height == 300

    def test_exact_max_not_resized(self):
        """800x800 → should stay 800x800."""
        raw = _make_test_image(800, 800)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "exact", 0)
        assert result.width == 800
        assert result.height == 800

    def test_aspect_ratio_preserved(self):
        """1600x800 → should become 800x400 (2:1 ratio preserved)."""
        raw = _make_test_image(1600, 800)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "wide", 0)
        assert result.width == 800
        assert result.height == 400

    def test_custom_max_dimensions(self):
        """Custom config with smaller max dimensions."""
        raw = _make_test_image(600, 400)
        config = ProcessingConfig(max_width=300, max_height=300)
        processor = ImageProcessor(config=config)
        result = processor.process_bytes(raw, "custom", 0)
        assert result.width <= 300
        assert result.height <= 300


# --- Brightness tests ---


class TestBrightness:
    """Test brightness adjustment."""

    def test_brightness_changes_pixels(self):
        """Processed image should have slightly different pixel values."""
        raw = _make_test_image(100, 100, color=(100, 100, 100))
        original = Image.open(BytesIO(raw))
        _get_data = getattr(original, "get_flattened_data", original.getdata)
        original_pixels = list(_get_data())

        processor = ImageProcessor()
        result = processor.process_bytes(raw, "brightness", 0)

        processed = Image.open(BytesIO(result.data))
        # Convert to RGB for comparison (WebP may use different mode)
        processed = processed.convert("RGB")
        _get_pdata = getattr(processed, "get_flattened_data", processed.getdata)
        processed_pixels = list(_get_pdata())

        # At least some pixels should be different
        differences = sum(
            1 for orig, proc in zip(original_pixels, processed_pixels)
            if orig != proc
        )
        assert differences > 0, "Brightness adjustment should change pixel values"

    def test_brightness_increases_values(self):
        """With factor > 1.0, pixel values should generally increase."""
        raw = _make_test_image(10, 10, color=(100, 100, 100))
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "bright", 0)

        processed = Image.open(BytesIO(result.data)).convert("RGB")
        avg_pixel = processed.getpixel((5, 5))
        # Brightness 1.03 × 100 ≈ 103
        assert avg_pixel[0] >= 100, "Brightened pixels should not decrease"


# --- WebP conversion tests ---


class TestWebPConversion:
    """Test WebP output format."""

    def test_output_is_webp(self):
        """Output bytes should be valid WebP (RIFF header)."""
        raw = _make_test_image(200, 200)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "webp-test", 0)

        # WebP magic bytes: RIFF....WEBP
        assert result.data[:4] == b"RIFF"
        assert result.data[8:12] == b"WEBP"

    def test_content_type_is_webp(self):
        raw = _make_test_image(200, 200)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "ct-test", 0)
        assert result.content_type == "image/webp"

    def test_filename_has_webp_extension(self):
        raw = _make_test_image(200, 200)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "fname-test", 3)
        assert result.filename == "fname-test_3.webp"

    def test_rgba_image_to_webp(self):
        """RGBA images (with transparency) should also convert."""
        raw = _make_test_image(200, 200, color=(100, 100, 100, 128), mode="RGBA")
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "rgba", 0)
        assert result.data[:4] == b"RIFF"


# --- Full pipeline tests ---


class TestFullPipeline:
    """Test the complete processing pipeline."""

    def test_process_bytes_returns_processed_image(self):
        raw = _make_test_image(1000, 750)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "pipeline-test", 2)

        assert isinstance(result, ProcessedImage)
        assert result.filename == "pipeline-test_2.webp"
        assert result.content_type == "image/webp"
        assert result.width <= 800
        assert result.height <= 800
        assert len(result.data) > 0
        assert result.original_url == ""

    def test_process_bytes_with_original_url(self):
        raw = _make_test_image(200, 200)
        processor = ImageProcessor()
        result = processor.process_bytes(
            raw, "url-test", 0, original_url="https://example.com/img.jpg"
        )
        assert result.original_url == "https://example.com/img.jpg"

    def test_different_indices_different_filenames(self):
        raw = _make_test_image(200, 200)
        processor = ImageProcessor()
        r0 = processor.process_bytes(raw, "multi", 0)
        r1 = processor.process_bytes(raw, "multi", 1)
        r2 = processor.process_bytes(raw, "multi", 2)
        assert r0.filename != r1.filename != r2.filename


# --- Placeholder rejection tests ---


class TestPlaceholderRejection:
    """Test that tiny placeholder images are rejected."""

    def test_tiny_1x1_rejected(self):
        """1x1 pixel image should raise ValueError."""
        raw = _make_test_image(1, 1)
        processor = ImageProcessor()
        with pytest.raises(ValueError, match="too small"):
            processor.process_bytes(raw, "tiny", 0)

    def test_tiny_5x5_rejected(self):
        """5x5 pixel image should raise ValueError."""
        raw = _make_test_image(5, 5)
        processor = ImageProcessor()
        with pytest.raises(ValueError, match="too small"):
            processor.process_bytes(raw, "tiny", 0)

    def test_10x10_accepted(self):
        """10x10 pixel image should pass validation."""
        raw = _make_test_image(10, 10)
        processor = ImageProcessor()
        result = processor.process_bytes(raw, "small-ok", 0)
        assert isinstance(result, ProcessedImage)
