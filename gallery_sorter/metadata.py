"""
Metadata extraction engine for Images and Videos.
Handles EXIF extraction, GPS parsing, smart date fallbacks, and dimensions.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ExifTags

class FileMetadata:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.filename = self.path.name
        self.suffix = self.path.suffix.lower()
        self.is_video = self.suffix in {
            ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp"
        }
        self.is_image = not self.is_video

        # Core Metadata
        self.date_taken: Optional[datetime] = None
        self.date_source: str = "none" # "exif", "filename", "filesystem"
        self.camera_make: Optional[str] = None
        self.camera_model: Optional[str] = None
        self.software: Optional[str] = None
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.gps_lat: Optional[float] = None
        self.gps_lon: Optional[float] = None
        self.file_size: int = 0

        self._extract()

    def _extract(self):
        try:
            self.file_size = os.path.getsize(self.path)
        except OSError:
            self.file_size = 0

        if self.is_image:
            self._extract_image_metadata()

        # Fallback date extraction if EXIF didn't yield a valid date
        if not self.date_taken:
            self._extract_date_from_filename()

        if not self.date_taken:
            self._extract_date_from_filesystem()

    def _extract_image_metadata(self):
        try:
            with Image.open(self.path) as img:
                self.width, self.height = img.size
                exif_data = img._getexif()
                raw_exif = img.getexif()

                tag_map = {}
                if exif_data:
                    tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}

                # Fallback to raw_exif if _getexif() was empty or missing tags
                if raw_exif:
                    for k, v in raw_exif.items():
                        tag_name = ExifTags.TAGS.get(k, k)
                        if tag_name not in tag_map:
                            tag_map[tag_name] = v

                    # Check Exif IFD for DateTimeOriginal
                    try:
                        exif_ifd = raw_exif.get_ifd(ExifTags.IFD.Exif)
                        if exif_ifd:
                            for k, v in exif_ifd.items():
                                tag_name = ExifTags.TAGS.get(k, k)
                                if tag_name not in tag_map:
                                    tag_map[tag_name] = v
                    except Exception:
                        pass

                    # Check GPS IFD
                    try:
                        gps_ifd = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
                        if gps_ifd:
                            self._parse_gps_dict(gps_ifd)
                    except Exception:
                        pass

                if not tag_map and not self.gps_lat:
                    return

                # 1. Camera Make & Model
                if "Make" in tag_map and isinstance(tag_map["Make"], str):
                    self.camera_make = tag_map["Make"].strip().strip("\x00")
                if "Model" in tag_map and isinstance(tag_map["Model"], str):
                    self.camera_model = tag_map["Model"].strip().strip("\x00")
                if "Software" in tag_map and isinstance(tag_map["Software"], str):
                    self.software = tag_map["Software"].strip().strip("\x00")

                # 2. Date Taken
                for date_key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                    if date_key in tag_map and tag_map[date_key]:
                        dt = self._parse_exif_date(str(tag_map[date_key]))
                        if dt:
                            self.date_taken = dt
                            self.date_source = "exif"
                            break

                # 3. GPS Coordinates from classic GPSInfo tag if not already parsed
                if not self.gps_lat and "GPSInfo" in tag_map and isinstance(tag_map["GPSInfo"], dict):
                    self._parse_gps_dict(tag_map["GPSInfo"])

        except Exception:
            # Corrupted image, unsupported format, or pillow error
            pass

    def _parse_exif_date(self, val: str) -> Optional[datetime]:
        """Parse EXIF date string (typically 'YYYY:MM:DD HH:MM:SS')."""
        val = val.strip().strip("\x00")
        for fmt in (
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d",
        ):
            try:
                # Handle possible timezone suffix if any
                clean_val = val[:19] if len(val) >= 19 and fmt == "%Y:%m:%d %H:%M:%S" else val
                return datetime.strptime(clean_val, fmt)
            except (ValueError, TypeError):
                continue
        return None

    def _parse_gps_dict(self, gps_info: dict):
        """Extract decimal degrees from EXIF GPSInfo dictionary (tagged or numeric keys)."""
        try:
            # Standard numeric keys: 1: LatRef, 2: Lat, 3: LonRef, 4: Lon
            lat_val = gps_info.get(2) or gps_info.get("GPSLatitude")
            lat_ref = gps_info.get(1) or gps_info.get("GPSLatitudeRef")
            lon_val = gps_info.get(4) or gps_info.get("GPSLongitude")
            lon_ref = gps_info.get(3) or gps_info.get("GPSLongitudeRef")

            if lat_val and lat_ref and lon_val and lon_ref:
                lat = self._convert_dms_to_degrees(lat_val)
                lon = self._convert_dms_to_degrees(lon_val)

                ref_str = str(lat_ref).upper()
                if "S" in ref_str:
                    lat = -lat
                ref_lon_str = str(lon_ref).upper()
                if "W" in ref_lon_str:
                    lon = -lon

                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    self.gps_lat = round(lat, 5)
                    self.gps_lon = round(lon, 5)
        except Exception:
            pass

    @staticmethod
    def _convert_dms_to_degrees(dms_tuple) -> float:
        """Convert DMS (degrees, minutes, seconds) tuple to decimal degrees."""
        def to_float(val):
            if isinstance(val, (int, float)):
                return float(val)
            # IFD rational (e.g., IFDRational or tuple (num, denom))
            if hasattr(val, "numerator") and hasattr(val, "denominator"):
                return val.numerator / val.denominator if val.denominator != 0 else 0.0
            if isinstance(val, (tuple, list)) and len(val) == 2:
                return float(val[0]) / float(val[1]) if val[1] != 0 else 0.0
            return float(val)

        d = to_float(dms_tuple[0])
        m = to_float(dms_tuple[1])
        s = to_float(dms_tuple[2])
        return d + (m / 60.0) + (s / 3600.0)

    def _extract_date_from_filename(self):
        """Smart date detection from common filename naming conventions."""
        name = self.filename

        # Pattern 1: WhatsApp (IMG-20231104-WA0002.jpg / VID-20240115-WA0010.mp4)
        m = re.search(r'(?:IMG|VID|DOC)-(\d{4})(\d{2})(\d{2})-WA', name, re.IGNORECASE)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                self.date_taken = datetime(y, mo, d)
                self.date_source = "filename"
                return

        # Pattern 2: Android / iOS / Camera (Screenshot_20240512-143021 / IMG_20240512_143021)
        m = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_](\d{2})(\d{2})(\d{2})', name)
        if m:
            y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
            if 2000 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31 and h < 24 and mi < 60 and s < 60:
                self.date_taken = datetime(y, mo, d, h, mi, s)
                self.date_source = "filename"
                return

        # Pattern 3: Date only (2024-05-12 / 20240512)
        m = re.search(r'(?:^|[^\d])(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?:[^\d]|$)', name)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                self.date_taken = datetime(y, mo, d)
                self.date_source = "filename"
                return

    def _extract_date_from_filesystem(self):
        """Final fallback: File modification time from the OS."""
        try:
            stat = self.path.stat()
            # On Windows, st_ctime is creation time, st_mtime is modification time.
            # Earliest timestamp is usually closest to photo capture.
            mtime = stat.st_mtime
            ctime = getattr(stat, "st_ctime", mtime)
            earliest = min(mtime, ctime) if ctime > 0 else mtime
            self.date_taken = datetime.fromtimestamp(earliest)
            self.date_source = "filesystem"
        except Exception:
            self.date_taken = datetime.now()
            self.date_source = "now"
