"""
Command Line Interface for LuminaSort.
"""

import sys
import argparse
from pathlib import Path

from .config import OrganizerConfig
from .organizer import run_sort, run_undo
from .ui import TerminalUI

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="LuminaSort",
        description="Smart Photo, Screenshot & Video Organizer for any PC with EXIF, GPS & Duplicate Detection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Safe Dry-Run (preview changes without moving files):
  python main.py "C:\\Users\\bitd\\Downloads"

  # Organize with Copy mode (preserves original files):
  python main.py "C:\\Users\\bitd\\Pictures" --dest "D:\\Photos_Clean" --action copy

  # Organize with Move mode (fast, cleans messy folder):
  python main.py "C:\\Users\\bitd\\Downloads" --action move

  # Trip-based organization (groups GPS photos by City_Year):
  python main.py "C:\\Users\\bitd\\Pictures" --mode trips --action copy

  # 1-Click Rollback / Undo a previous session:
  python main.py --undo "D:\\Photos_Clean\\.sort_manifest_20261123_183000.json"
        """
    )

    # Positional or primary options
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Source directory containing unorganized photos and videos."
    )
    parser.add_argument(
        "-d", "--dest",
        default=None,
        help="Destination directory for organized folders (Default: <source>/Organized_Gallery)."
    )

    # Action Mode
    parser.add_argument(
        "-a", "--action",
        choices=["dry-run", "copy", "move", "hardlink"],
        default="dry-run",
        help="Action to perform: 'dry-run' (preview only), 'copy' (safest), 'move' (fast reorganization), 'hardlink' (0 disk space). Default: dry-run."
    )

    # Organization Mode
    parser.add_argument(
        "-m", "--mode",
        choices=["source-date", "date-only", "source-only", "trips", "custom"],
        default="source-date",
        help="Folder structure layout. Default: source-date (Camera/2024/05, Screenshots/2024, etc.)."
    )

    parser.add_argument(
        "--pattern",
        default="{source}/{year}/{month} - {month_name}",
        help="Custom folder pattern when --mode custom is selected."
    )

    # Duplicate Controls
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable exact duplicate detection."
    )
    parser.add_argument(
        "--no-similar",
        action="store_true",
        help="Disable perceptual (visual similarity) duplicate detection."
    )
    parser.add_argument(
        "--dup-action",
        choices=["isolate", "skip", "delete"],
        default="isolate",
        help="What to do with duplicates: 'isolate' (move to _Duplicates folder), 'skip', or 'delete'. Default: isolate."
    )
    parser.add_argument(
        "--similarity-threshold",
        type=int,
        default=4,
        help="Max Hamming distance for perceptual duplicate match (0-64). Default: 4."
    )

    # Geocoding Controls
    parser.add_argument(
        "--no-geo",
        action="store_true",
        help="Disable offline GPS reverse geocoding."
    )

    # GUI option
    parser.add_argument(
        "-g", "--gui",
        action="store_true",
        help="Launch the desktop graphical user interface (GUI)."
    )

    # Undo / Rollback
    parser.add_argument(
        "--undo",
        metavar="MANIFEST_FILE",
        default=None,
        help="Path to .sort_manifest_*.json to rollback an earlier organization session."
    )

    # Interactive wizard
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Launch interactive wizard to choose options step-by-step."
    )

    return parser

def interactive_wizard() -> OrganizerConfig:
    TerminalUI.show_banner()
    print("\n🧙 Welcome to the LuminaSort Interactive Setup!\n")

    # 1. Source Dir
    while True:
        src_input = input("👉 Enter the folder path to organize (e.g. C:\\Users\\...\\Downloads): ").strip().strip('"')
        if src_input and Path(src_input).is_dir():
            source_dir = Path(src_input)
            break
        print("❌ Invalid directory path, please try again.")

    # 2. Dest Dir
    dest_input = input(f"👉 Enter destination folder [Press Enter for '{source_dir / 'Organized_Gallery'}']: ").strip().strip('"')
    dest_dir = Path(dest_input) if dest_input else source_dir / "Organized_Gallery"

    # 3. Action Mode
    print("\nSelect Action:")
    print("  1. Dry Run (Preview only, safe)")
    print("  2. Copy (Leaves originals untouched)")
    print("  3. Move (Reorganizes and frees source space)")
    print("  4. Hardlink (Instant, consumes 0 extra disk space)")
    act_choice = input("Enter choice [1-4, default: 1]: ").strip()
    action_map = {"1": "dry-run", "2": "copy", "3": "move", "4": "hardlink"}
    action = action_map.get(act_choice, "dry-run")

    # 4. Mode
    print("\nSelect Organization Layout:")
    print("  1. Source + Date (Camera Originals/2024/05, Screenshots/2024, WhatsApp/...) [Recommended]")
    print("  2. Date Only (2024/05 - May/...)")
    print("  3. Trips & Vacations (Trips/Delhi_2024/ using GPS + fallback)")
    print("  4. Source Only (Screenshots/, WhatsApp/, Camera/...)")
    mode_choice = input("Enter choice [1-4, default: 1]: ").strip()
    mode_map = {"1": "source-date", "2": "date-only", "3": "trips", "4": "source-only"}
    mode = mode_map.get(mode_choice, "source-date")

    return OrganizerConfig(
        source_dir=source_dir,
        dest_dir=dest_dir,
        mode=mode,
        action=action,
        detect_duplicates=True,
        detect_similar=True,
        enable_geocoding=True
    )

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Launch GUI if requested
    if args.gui:
        from .gui import start_gui
        start_gui()
        return

    # Handle Undo
    if args.undo:
        TerminalUI.show_banner()
        print(f"🔄 Rolling back session from manifest: {args.undo}")
        try:
            success, fail, errors = run_undo(Path(args.undo))
            print(f"✅ Rollback Complete! Restored/reverted: {success} files.")
            if fail > 0:
                print(f"⚠️ Warnings / Failed: {fail}")
                for err in errors[:5]:
                    print(f"  • {err}")
        except Exception as e:
            print(f"❌ Error during rollback: {e}")
            sys.exit(1)
        return

    # Check if interactive mode or no arguments
    if args.interactive or not args.source:
        if not args.source:
            config = interactive_wizard()
        else:
            config = interactive_wizard()
    else:
        source_path = Path(args.source)
        if not source_path.is_dir():
            print(f"❌ Error: Source directory does not exist: {source_path}")
            sys.exit(1)

        dest_path = Path(args.dest) if args.dest else None

        config = OrganizerConfig(
            source_dir=source_path,
            dest_dir=dest_path,
            mode=args.mode,
            custom_pattern=args.pattern,
            action=args.action,
            detect_duplicates=not args.no_dedup,
            detect_similar=not args.no_similar,
            duplicate_action=args.dup_action,
            similarity_threshold=args.similarity_threshold,
            enable_geocoding=not args.no_geo
        )

    TerminalUI.show_banner()
    print(f"🔍 Scanning directory: {config.source_dir}...")
    report = run_sort(config)
    TerminalUI.render_report(report)

if __name__ == "__main__":
    main()
