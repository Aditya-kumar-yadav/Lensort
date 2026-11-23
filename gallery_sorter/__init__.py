"""
GallerySorter - Next-Gen Photo, Screenshot & Video Organizer
A high-performance, modular organizer for any PC (Windows, macOS, Linux).
"""

__version__ = "1.0.0"

from .config import OrganizerConfig
from .organizer import GallerySorter, run_sort, run_undo

__all__ = ["OrganizerConfig", "GallerySorter", "run_sort", "run_undo"]
