"""
Source and Type Classifier for media files.
Differentiates between Screenshots, WhatsApp & Social, Camera Originals, Videos, Documents, etc.
"""

import re
from pathlib import Path
from typing import Optional
from .metadata import FileMetadata

class MediaClassifier:
    """Classifies files into intuitive folders based on metadata, names, and dimensions."""

    CATEGORY_SCREENSHOTS = "Screenshots"
    CATEGORY_WHATSAPP = "WhatsApp & Social"
    CATEGORY_CAMERA = "Camera Originals"
    CATEGORY_VIDEOS = "Videos"
    CATEGORY_DOCUMENTS = "Documents & Scans"
    CATEGORY_GENERAL = "General Photos"

    # Known Screenshot Filename Patterns
    SCREENSHOT_REGEX = re.compile(
        r"(?:screenshot|screen\s*shot|screencap|capture|prntscr|snip)",
        re.IGNORECASE
    )

    # Social & Chat Filename Patterns
    WHATSAPP_REGEX = re.compile(
        r"^(?:IMG|VID|DOC|AUD|PTT)-\d{8}-WA\d+",
        re.IGNORECASE
    )
    SOCIAL_REGEX = re.compile(
        r"(?:telegram|instagram|twitter|reddit|tiktok|facebook|snapchat|discord|meme)",
        re.IGNORECASE
    )

    # Document keywords
    DOC_REGEX = re.compile(
        r"(?:receipt|invoice|bill|statement|aadhaar|pan|passport|scan|document|form)",
        re.IGNORECASE
    )

    @classmethod
    def classify(cls, meta: FileMetadata) -> str:
        """Determines the primary category for a media file."""
        # 1. Videos
        if meta.is_video:
            return cls.CATEGORY_VIDEOS

        filename = meta.filename

        # 2. WhatsApp & Social Chat
        if cls.WHATSAPP_REGEX.search(filename) or cls.SOCIAL_REGEX.search(filename):
            return cls.CATEGORY_WHATSAPP

        # 3. Explicit Screenshot by Filename
        if cls.SCREENSHOT_REGEX.search(filename):
            return cls.CATEGORY_SCREENSHOTS

        # 4. Aspect Ratio & Screen Dimensions (Screenshots without 'screenshot' in name)
        # Screenshots almost never have Camera Make or Camera Model EXIF.
        has_camera_exif = bool(meta.camera_make or meta.camera_model)
        if not has_camera_exif and meta.width and meta.height:
            w, h = meta.width, meta.height
            ratio = max(w, h) / max(1, min(w, h))

            # Modern phones screen aspect ratios: 16:9 (1.77), 18:9 (2.0), 19.5:9 (2.16), 20:9 (2.22), 21:9 (2.33)
            # Standard desktop 16:9 (1920x1080, 2560x1440, 3840x2160) or 16:10 (1920x1200)
            is_screen_ratio = (
                (1.75 <= ratio <= 2.35) or
                (w in {1920, 2560, 3840, 1080, 1440, 2160, 720, 1366, 1280} and
                 h in {1080, 1440, 2160, 1920, 2560, 3840, 1600, 768, 720})
            )

            # PNG format is the default for Windows, macOS, and iOS screenshots
            if meta.suffix == ".png" and is_screen_ratio:
                return cls.CATEGORY_SCREENSHOTS

        # 5. Documents & Receipts
        if cls.DOC_REGEX.search(filename):
            return cls.CATEGORY_DOCUMENTS

        # 6. Camera Originals
        # Genuine camera photos have camera manufacturer/model, or shutter/aperture data
        if has_camera_exif:
            return cls.CATEGORY_CAMERA

        # High resolution JPEGs without social markings (often camera photos where EXIF was stripped or DSLR exports)
        if meta.width and meta.height and (meta.width * meta.height) >= 6_000_000:
            return cls.CATEGORY_CAMERA

        # Default fallback
        return cls.CATEGORY_GENERAL
