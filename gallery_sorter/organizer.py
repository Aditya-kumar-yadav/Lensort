"""
Core Organizer Engine.
Calculates target folder paths, handles collision avoidance, performs safe copy/move/hardlink,
tracks manifest for full 1-click Undo / Rollback.
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass, asdict

from .config import OrganizerConfig
from .metadata import FileMetadata
from .classifier import MediaClassifier
from .geocoder import reverse_geocode
from .duplicates import DuplicateDetector

@dataclass
class PlannedOperation:
    source_path: Path
    dest_path: Path
    category: str
    date_str: str
    is_duplicate: bool = False
    duplicate_type: str = "" # "exact" or "similar"
    duplicate_of: Optional[Path] = None
    file_size: int = 0
    status: str = "pending" # "pending", "success", "skipped", "failed"
    error: str = ""

@dataclass
class SortReport:
    total_scanned: int = 0
    total_size_bytes: int = 0
    planned_operations: List[PlannedOperation] = None
    category_counts: Dict[str, int] = None
    exact_duplicates_count: int = 0
    similar_duplicates_count: int = 0
    duplicate_saved_bytes: int = 0
    manifest_path: Optional[Path] = None
    action: str = "dry-run"
    duration_seconds: float = 0.0

    def __post_init__(self):
        if self.planned_operations is None:
            self.planned_operations = []
        if self.category_counts is None:
            self.category_counts = {}

class GallerySorter:
    def __init__(self, config: OrganizerConfig):
        self.config = config

    def scan_files(self) -> List[Path]:
        """Find all supported media files in source directory."""
        supported_exts = set(ext.lower() for ext in self.config.supported_extensions)
        files = []

        if self.config.recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for p in self.config.source_dir.glob(pattern):
            if p.is_file() and p.suffix.lower() in supported_exts:
                # Do not re-scan the destination directory if inside source
                try:
                    p.relative_to(self.config.dest_dir)
                    continue # Skip files already in destination
                except ValueError:
                    pass
                # Skip hidden files or temporary files
                if p.name.startswith((".", "~$", "desktop.ini", "Thumbs.db")):
                    continue
                files.append(p)

        return sorted(files)

    def plan(self, progress_callback=None) -> SortReport:
        """Scan, extract metadata in parallel, classify, detect duplicates, and stream live operations."""
        import concurrent.futures
        start_time = datetime.now()
        report = SortReport(action=self.config.action)

        files = self.scan_files()
        report.total_scanned = len(files)

        if not files:
            report.duration_seconds = (datetime.now() - start_time).total_seconds()
            return report

        # Step 1: Parallel Metadata Extraction with live progress
        metadata_map: Dict[Path, FileMetadata] = {}
        processed_count = 0
        total_files = len(files)

        # Notify start
        if progress_callback:
            progress_callback({
                "stage": "scanning",
                "current": 0,
                "total": total_files,
                "file": "",
                "category": "",
                "target": ""
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            future_to_path = {executor.submit(FileMetadata, p): p for p in files}
            for future in concurrent.futures.as_completed(future_to_path):
                p = future_to_path[future]
                try:
                    meta = future.result()
                except Exception:
                    meta = FileMetadata(p)
                metadata_map[p] = meta
                report.total_size_bytes += meta.file_size
                processed_count += 1

                if progress_callback and (processed_count % 15 == 0 or processed_count == total_files):
                    category_hint = MediaClassifier.classify(meta)
                    progress_callback({
                        "stage": "analyzing",
                        "current": processed_count,
                        "total": total_files,
                        "file": meta.filename,
                        "category": category_hint,
                        "target": f"📁 {category_hint}/..."
                    })

        # Step 2: Duplicate Detection
        exact_dups: Set[Path] = set()
        exact_hash_map: Dict[str, List[Path]] = {}
        similar_dups_list: List[Tuple[Path, Path, int]] = []
        similar_dup_map: Dict[Path, Tuple[Path, int]] = {}

        if self.config.detect_duplicates:
            exact_hash_map, exact_dups = DuplicateDetector.find_exact_duplicates(files)
            report.exact_duplicates_count = len(exact_dups)

            if self.config.detect_similar:
                similar_dups_list = DuplicateDetector.find_perceptual_duplicates(
                    files,
                    already_exact_duplicates=exact_dups,
                    threshold=self.config.similarity_threshold
                )
                report.similar_duplicates_count = len(similar_dups_list)
                for orig, dup, dist in similar_dups_list:
                    similar_dup_map[dup] = (orig, dist)

        for dup in exact_dups:
            report.duplicate_saved_bytes += metadata_map[dup].file_size
        for dup in similar_dup_map:
            report.duplicate_saved_bytes += metadata_map[dup].file_size

        # Step 3: Stream Planned Destinations
        dest_taken_names: Set[Path] = set()
        operations: List[PlannedOperation] = []

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        for idx, p in enumerate(files):
            meta = metadata_map[p]
            category = MediaClassifier.classify(meta)
            report.category_counts[category] = report.category_counts.get(category, 0) + 1

            dt = meta.date_taken or datetime.now()
            year_str = f"{dt.year:04d}"
            month_num_str = f"{dt.month:02d}"
            month_name = month_names[dt.month - 1]
            date_folder_str = f"{month_num_str} - {month_name}"

            is_dup = False
            dup_type = ""
            dup_of = None

            if p in exact_dups:
                is_dup = True
                dup_type = "exact"
                fhash = DuplicateDetector.compute_sha256(p)
                all_with_hash = exact_hash_map.get(fhash, [])
                dup_of = all_with_hash[0] if all_with_hash else None
            elif p in similar_dup_map:
                is_dup = True
                dup_type = "similar"
                dup_of = similar_dup_map[p][0]

            if is_dup and self.config.duplicate_action == "isolate":
                target_folder = self.config.dest_dir / "_Duplicates" / (
                    "Exact" if dup_type == "exact" else "Similar"
                ) / year_str
            elif is_dup and self.config.duplicate_action == "skip":
                target_folder = self.config.dest_dir / "_Skipped_Duplicates"
            else:
                target_folder = self._compute_target_folder(
                    meta, category, year_str, month_num_str, month_name, date_folder_str
                )

            final_dest = self._resolve_collision(target_folder / p.name, dest_taken_names)
            dest_taken_names.add(final_dest)

            op = PlannedOperation(
                source_path=p,
                dest_path=final_dest,
                category=category,
                date_str=dt.strftime("%Y-%m-%d"),
                is_duplicate=is_dup,
                duplicate_type=dup_type,
                duplicate_of=dup_of,
                file_size=meta.file_size
            )
            operations.append(op)

            if progress_callback and (idx % 20 == 0 or idx == len(files) - 1):
                progress_callback({
                    "stage": "planning",
                    "current": idx + 1,
                    "total": len(files),
                    "file": p.name,
                    "category": category,
                    "target": str(final_dest.parent.name),
                    "operation": op,
                    "category_counts": dict(report.category_counts),
                    "duplicates_count": report.exact_duplicates_count + report.similar_duplicates_count
                })

        report.planned_operations = operations
        report.duration_seconds = (datetime.now() - start_time).total_seconds()
        return report

        report.planned_operations = operations
        report.duration_seconds = (datetime.now() - start_time).total_seconds()
        return report

    def _compute_target_folder(
        self,
        meta: FileMetadata,
        category: str,
        year: str,
        month: str,
        month_name: str,
        date_folder: str
    ) -> Path:
        """Determines destination subfolder according to chosen mode."""
        base = self.config.dest_dir

        # Check for GPS Location & Trips mode
        city_location = None
        if self.config.enable_geocoding and meta.gps_lat and meta.gps_lon:
            city_location = reverse_geocode(meta.gps_lat, meta.gps_lon)

        # Mode: trips
        if self.config.mode == "trips":
            if city_location:
                # E.g.: Trips/Goa_2024/ or Trips/Paris_2023/
                trip_folder_name = f"{city_location.city}_{year}"
                return base / "Trips" / trip_folder_name
            # If no GPS found, fall through to source-date logic below

        # Mode: source-date (Default & Most Practical)
        if self.config.mode == "source-date":
            if category == MediaClassifier.CATEGORY_SCREENSHOTS:
                # Screenshots are best by year only (keeps it clean)
                return base / "Screenshots" / year
            elif category == MediaClassifier.CATEGORY_VIDEOS:
                # Videos sorted by year and category
                return base / "Videos" / year
            elif category == MediaClassifier.CATEGORY_DOCUMENTS:
                return base / "Documents & Scans" / year
            elif category == MediaClassifier.CATEGORY_WHATSAPP:
                return base / "WhatsApp & Social" / year / date_folder
            elif category == MediaClassifier.CATEGORY_CAMERA:
                return base / "Camera Originals" / year / date_folder
            else:
                return base / "General Photos" / year / date_folder

        # Mode: date-only
        elif self.config.mode == "date-only":
            return base / year / date_folder

        # Mode: source-only
        elif self.config.mode == "source-only":
            return base / category

        # Mode: custom
        elif self.config.mode == "custom":
            city_val = city_location.city if city_location else "Unknown_City"
            interpolated = self.config.custom_pattern.format(
                source=category,
                year=year,
                month=month,
                month_name=month_name,
                city=city_val
            )
            return base / Path(interpolated)

        # Fallback
        return base / year / date_folder

    def _resolve_collision(self, candidate_path: Path, reserved_set: Set[Path]) -> Path:
        """Appends (1), (2) etc. if a destination file with the same name exists or is reserved."""
        if not candidate_path.exists() and candidate_path not in reserved_set:
            return candidate_path

        parent = candidate_path.parent
        stem = candidate_path.stem
        suffix = candidate_path.suffix

        counter = 1
        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists() and new_path not in reserved_set:
                return new_path
            counter += 1

    def execute(self, report: SortReport, progress_callback=None) -> SortReport:
        """Executes the planned operations (copy, move, hardlink) with live progress streaming."""
        action = self.config.action
        if action == "dry-run":
            return report

        manifest_ops = []
        total = len(report.planned_operations)

        for idx, op in enumerate(report.planned_operations):
            # Skip duplicate if duplicate_action is 'skip'
            if op.is_duplicate and self.config.duplicate_action == "skip":
                op.status = "skipped"
                continue

            try:
                op.dest_path.parent.mkdir(parents=True, exist_ok=True)

                if action == "copy":
                    shutil.copy2(op.source_path, op.dest_path)
                    op.status = "success"
                elif action == "move":
                    shutil.move(str(op.source_path), str(op.dest_path))
                    op.status = "success"
                elif action == "hardlink":
                    try:
                        os.link(op.source_path, op.dest_path)
                        op.status = "success"
                    except OSError:
                        shutil.copy2(op.source_path, op.dest_path)
                        op.status = "success"

                manifest_ops.append({
                    "source": str(op.source_path),
                    "dest": str(op.dest_path),
                    "action": action,
                    "category": op.category,
                    "size": op.file_size
                })

            except Exception as e:
                op.status = "failed"
                op.error = str(e)

            if progress_callback and (idx % 10 == 0 or idx == total - 1):
                progress_callback({
                    "stage": "sorting",
                    "current": idx + 1,
                    "total": total,
                    "file": op.source_path.name,
                    "category": op.category,
                    "target": str(op.dest_path.parent.name)
                })

        # Write manifest file for undo
        if self.config.create_undo_manifest and manifest_ops:
            manifest_file = self.config.dest_dir / f".sort_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "version": "1.0",
                        "timestamp": datetime.now().isoformat(),
                        "action": action,
                        "source_dir": str(self.config.source_dir),
                        "dest_dir": str(self.config.dest_dir),
                        "operations": manifest_ops
                    }, f, indent=2)
                report.manifest_path = manifest_file
            except Exception:
                pass

        return report

def run_sort(config: OrganizerConfig) -> SortReport:
    """Convenience helper to plan and execute sorting."""
    sorter = GallerySorter(config)
    report = sorter.plan()
    if config.action != "dry-run":
        report = sorter.execute(report)
    return report

def run_undo(manifest_path: Path) -> Tuple[int, int, List[str]]:
    """
    Rolls back an executed sorting session using its manifest JSON file.
    Returns (success_count, fail_count, errors).
    """
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    operations = data.get("operations", [])
    action = data.get("action", "copy")

    success = 0
    fail = 0
    errors = []

    for op in reversed(operations):
        src = Path(op["source"])
        dst = Path(op["dest"])

        try:
            if not dst.exists():
                continue

            if action == "move":
                # Move back from dest to src
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                success += 1
            elif action in ("copy", "hardlink"):
                # Delete copied/hardlinked file at dest
                dst.unlink()
                success += 1
        except Exception as e:
            fail += 1
            errors.append(f"{dst} -> {src}: {e}")

    # Remove manifest after successful rollback
    try:
        manifest_path.unlink()
    except Exception:
        pass

    return success, fail, errors
