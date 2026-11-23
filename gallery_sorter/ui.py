"""
User Interface & Reporting Engine.
Renders beautiful tables, progress summaries, and dry-run previews using Rich (with plain-text fallback).
"""

from typing import List, Optional
from pathlib import Path
from .organizer import SortReport, PlannedOperation

def format_bytes(size: int) -> str:
    """Format bytes into readable KB, MB, GB."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

class TerminalUI:
    @staticmethod
    def show_banner():
        try:
            from rich.console import Console
            from rich.panel import Panel
            console = Console()
            banner_text = (
                "[bold cyan]Lensort — Smart Media Organizer[/bold cyan]\n"
                "[dim]Organize Photos, Screenshots, WhatsApp & Videos with EXIF, GPS & Duplicate Detection[/dim]"
            )
            console.print(Panel(banner_text, border_style="cyan", expand=False))
        except ImportError:
            print("=" * 60)
            print(" Lensort — Smart Media Organizer")
            print("=" * 60)

    @staticmethod
    def render_report(report: SortReport, preview_limit: int = 10):
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            console = Console()

            # 1. Summary Statistics Table
            summary_table = Table(title="📊 Scan & Analysis Summary", border_style="blue")
            summary_table.add_column("Metric", style="bold white", width=26)
            summary_table.add_column("Details", style="cyan")

            summary_table.add_row("Total Media Files Found", str(report.total_scanned))
            summary_table.add_row("Total Size", format_bytes(report.total_size_bytes))
            summary_table.add_row("Scan Duration", f"{report.duration_seconds:.2f} seconds")

            action_color = "yellow" if report.action == "dry-run" else "green"
            summary_table.add_row("Action Mode", f"[{action_color}]{report.action.upper()}[/{action_color}]")

            # Categories Breakdown
            cat_breakdown = ", ".join(f"{k}: [bold]{v}[/bold]" for k, v in report.category_counts.items())
            summary_table.add_row("Category Breakdown", cat_breakdown or "None")

            # Duplicates
            dup_text = f"Exact: [red]{report.exact_duplicates_count}[/red] | Similar: [yellow]{report.similar_duplicates_count}[/yellow]"
            summary_table.add_row("Duplicates Detected", dup_text)
            summary_table.add_row("Reclaimable Disk Space", f"[bold green]{format_bytes(report.duplicate_saved_bytes)}[/bold green]")

            console.print()
            console.print(summary_table)

            # 2. Preview Operations Table
            if report.planned_operations:
                preview_table = Table(title=f"📁 Destination Preview (Sample {min(len(report.planned_operations), preview_limit)} of {len(report.planned_operations)} files)", border_style="magenta")
                preview_table.add_column("Original File", style="white", no_wrap=True)
                preview_table.add_column("Category", style="cyan")
                preview_table.add_column("Date", style="dim")
                preview_table.add_column("Target Destination", style="green")
                preview_table.add_column("Status / Note", style="yellow")

                for op in report.planned_operations[:preview_limit]:
                    note = ""
                    if op.is_duplicate:
                        note = f"⚠️ Duplicate ({op.duplicate_type})"
                    elif op.status != "pending":
                        note = op.status

                    preview_table.add_row(
                        op.source_path.name,
                        op.category,
                        op.date_str,
                        str(op.dest_path.relative_to(op.dest_path.parents[3]) if len(op.dest_path.parents) >= 4 else op.dest_path.name),
                        note
                    )

                console.print()
                console.print(preview_table)

            # 3. Action Guidance
            if report.action == "dry-run":
                console.print(Panel(
                    "[bold yellow]⚠️  DRY RUN MODE ACTIVE:[/bold yellow] No files were moved or copied on disk.\n"
                    "To execute actual organization:\n"
                    "  • [bold green]Safe Copy (leaves original intact):[/bold green] add [cyan]--action copy[/cyan]\n"
                    "  • [bold red]Fast Move (reorganizes folder):[/bold red] add [cyan]--action move[/cyan]\n"
                    "  • [bold blue]Zero-Space Hardlink (instant):[/bold blue] add [cyan]--action hardlink[/cyan]",
                    border_style="yellow",
                    expand=False
                ))
            elif report.manifest_path:
                console.print(Panel(
                    f"[bold green]✅ Organization Complete![/bold green]\n"
                    f"Session manifest saved to:\n[dim]{report.manifest_path}[/dim]\n\n"
                    f"To 1-click [bold]UNDO[/bold] this session, run:\n"
                    f"[cyan]python main.py --undo \"{report.manifest_path}\"[/cyan]",
                    border_style="green",
                    expand=False
                ))

        except ImportError:
            # Plain Text Fallback
            print("\n" + "=" * 50)
            print("SCAN & ANALYSIS SUMMARY")
            print("=" * 50)
            print(f"Total Scanned: {report.total_scanned} ({format_bytes(report.total_size_bytes)})")
            print(f"Action: {report.action.upper()}")
            for k, v in report.category_counts.items():
                print(f"  - {k}: {v}")
            print(f"Duplicates: Exact={report.exact_duplicates_count}, Similar={report.similar_duplicates_count}")
            print(f"Potential Space Saved: {format_bytes(report.duplicate_saved_bytes)}")
            print("=" * 50)
