from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

@dataclass
class OrganizerConfig:
    """Configuration options for GallerySorter."""
    # Source and Destination paths
    source_dir: Path
    dest_dir: Optional[Path] = None

    # Organization Mode:
    # "source-date": Camera/2024/05 - May/, Screenshots/2024/, WhatsApp/2024/
    # "date-only": 2024/05 - May/
    # "source-only": Camera Originals/, Screenshots/, WhatsApp/, Videos/
    # "trips": Trips/Delhi_2024/ (if GPS present) or fallback to source-date
    # "custom": uses custom_pattern
    mode: str = "source-date"

    # Custom organization pattern (e.g. "{source}/{year}/{month_name}")
    custom_pattern: str = "{source}/{year}/{month} - {month_name}"

    # Action: "dry-run", "copy", "move", "hardlink"
    action: str = "dry-run"

    # Duplicate detection options
    detect_duplicates: bool = True
    detect_similar: bool = True           # Perceptual hash (pHash / dHash)
    similarity_threshold: int = 4          # Max Hamming distance for perceptual match (0-64)
    # Action for duplicates: "isolate" (move to _Duplicates folder), "skip", "delete"
    duplicate_action: str = "isolate"

    # Geocoding / Location options
    enable_geocoding: bool = True
    trip_min_photos: int = 1               # Minimum photos to trigger a Trip folder

    # File scanning options
    recursive: bool = True
    include_videos: bool = True
    supported_extensions: List[str] = field(default_factory=lambda: [
        # Common Images
        ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".bmp", ".gif",
        # RAW Images
        ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
        # Common Videos
        ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp"
    ])

    # Safety & Undo
    create_undo_manifest: bool = True
    manifest_file: Optional[Path] = None

    def __post_init__(self):
        self.source_dir = Path(self.source_dir).resolve()
        if self.dest_dir is None:
            self.dest_dir = self.source_dir / "Organized_Gallery"
        else:
            self.dest_dir = Path(self.dest_dir).resolve()
