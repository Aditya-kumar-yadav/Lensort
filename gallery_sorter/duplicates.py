"""
High-Performance Duplicate and Similar Image Detection.
Stage 1: Fast grouping by file size.
Stage 2: Exact byte-by-byte SHA-256 hash.
Stage 3: Perceptual Difference Hash (dHash) for visually identical/resized photos.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
from PIL import Image

class DuplicateDetector:
    """Detects exact duplicates and perceptual near-duplicates."""

    @staticmethod
    def compute_sha256(path: Path, chunk_size: int = 65536) -> str:
        """Compute SHA-256 hash of a file in streaming chunks."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def compute_dhash(path: Path, hash_size: int = 8) -> Optional[int]:
        """
        Calculate Difference Hash (dHash) of an image.
        Downsamples to (hash_size + 1, hash_size) grayscale and compares adjacent pixels.
        Returns a 64-bit integer.
        """
        try:
            with Image.open(path) as img:
                # Convert to grayscale
                gray = img.convert("L")

                # Guard: If image is completely uniform/blank (e.g. solid color canvas),
                # min and max pixel values are identical, meaning no perceptual features.
                extrema = gray.getextrema()
                if extrema[0] == extrema[1]:
                    return None

                # Resize to (hash_size + 1, hash_size)
                resized = gray.resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
                if hasattr(resized, "get_flattened_data"):
                    pixels = list(resized.get_flattened_data())
                else:
                    pixels = list(resized.getdata())

                # Compare consecutive horizontal pixels
                diff = 0
                for row in range(hash_size):
                    for col in range(hash_size):
                        idx = row * (hash_size + 1) + col
                        left = pixels[idx]
                        right = pixels[idx + 1]
                        diff = (diff << 1) | (1 if left > right else 0)
                return diff
        except Exception:
            return None

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """Count differing bits between two 64-bit integer hashes."""
        return bin(hash1 ^ hash2).count("1")

    @classmethod
    def find_exact_duplicates(cls, file_paths: List[Path]) -> Tuple[Dict[str, List[Path]], Set[Path]]:
        """
        Finds exact duplicates using file size grouping followed by SHA-256.
        Returns (hash_map, set_of_duplicate_paths).
        First file in list is considered original; subsequent files are duplicates.
        """
        # Step 1: Group by file size
        size_groups = defaultdict(list)
        for p in file_paths:
            try:
                size = os.path.getsize(p)
                if size > 0:
                    size_groups[size].append(p)
            except OSError:
                continue

        # Step 2: For groups with >1 file, compute SHA256
        hash_to_files = defaultdict(list)
        duplicates: Set[Path] = set()

        for size, candidates in size_groups.items():
            if len(candidates) < 2:
                continue

            for p in candidates:
                try:
                    fhash = cls.compute_sha256(p)
                    hash_to_files[fhash].append(p)
                except Exception:
                    continue

        # Mark duplicates (keep primary as canonical original)
        for fhash, files in hash_to_files.items():
            if len(files) > 1:
                # Rank candidates: penalty if name contains 'copy', '(1)', etc.
                def original_score(p: Path) -> Tuple[int, int, str]:
                    name_lower = p.name.lower()
                    penalty = 0
                    if "copy" in name_lower:
                        penalty += 10
                    if re.search(r"\(\d+\)", name_lower):
                        penalty += 10
                    if "_dup" in name_lower or "-dup" in name_lower:
                        penalty += 10
                    # Lower penalty is better; then prefer original WhatsApp/IMG prefixes
                    return (penalty, -len(p.name), str(p))

                sorted_files = sorted(files, key=original_score)
                # Primary is sorted_files[0]; the rest are duplicates
                for dup in sorted_files[1:]:
                    duplicates.add(dup)

        return hash_to_files, duplicates

    @classmethod
    def find_perceptual_duplicates(
        cls,
        image_paths: List[Path],
        already_exact_duplicates: Set[Path],
        threshold: int = 4
    ) -> List[Tuple[Path, Path, int]]:
        """
        Finds visually similar/resized images using dHash.
        Returns list of (original, duplicate, distance).
        """
        candidates = [p for p in image_paths if p not in already_exact_duplicates]
        hashes: List[Tuple[Path, int]] = []

        for p in candidates:
            # Skip video extensions
            if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".webm"}:
                continue
            h = cls.compute_dhash(p)
            if h is not None:
                hashes.append((p, h))

        similar_pairs: List[Tuple[Path, Path, int]] = []
        seen_dups: Set[Path] = set()

        # O(N^2) comparison with early exits or bucket optimization
        # For typical batch sizes this is fast because it's pure bitwise XOR in C
        n = len(hashes)
        for i in range(n):
            path_i, hash_i = hashes[i]
            if path_i in seen_dups:
                continue
            for j in range(i + 1, n):
                path_j, hash_j = hashes[j]
                if path_j in seen_dups:
                    continue
                dist = cls.hamming_distance(hash_i, hash_j)
                if dist <= threshold:
                    # Larger file is considered the original (higher quality)
                    try:
                        size_i = os.path.getsize(path_i)
                        size_j = os.path.getsize(path_j)
                        if size_i >= size_j:
                            orig, dup = path_i, path_j
                        else:
                            orig, dup = path_j, path_i
                    except OSError:
                        orig, dup = path_i, path_j

                    similar_pairs.append((orig, dup, dist))
                    seen_dups.add(dup)

        return similar_pairs
