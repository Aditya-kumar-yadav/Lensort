"""
Desktop Graphical User Interface (GUI) for LuminaSort.
Built using Python's native Tkinter + ttk (zero third-party dependencies required).
Runs out-of-the-box on Windows, macOS, and Linux.
"""

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .config import OrganizerConfig
from .organizer import GallerySorter, run_undo, SortReport
from .ui import format_bytes

class LuminaSortGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lensort — Smart Gallery & Photo Organizer")
        self.root.geometry("980x720")
        self.root.minsize(800, 600)

        # Apply Modern Dark Styling
        self._setup_styles()

        # State Variables
        self.source_dir_var = tk.StringVar(value="")
        self.dest_dir_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="source-date")
        self.action_var = tk.StringVar(value="copy") # copy or move
        self.dedup_var = tk.BooleanVar(value=True)
        self.similar_var = tk.BooleanVar(value=True)
        self.geo_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready. Select a folder to scan.")

        self.current_report: SortReport = None
        self.manifest_path: Path = None

        self._build_ui()

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Dark Theme Palette
        self.bg_color = "#18181b"      # Zinc 900
        self.card_bg = "#27272a"       # Zinc 800
        self.accent_color = "#38bdf8"   # Sky 400
        self.text_color = "#f4f4f5"     # Zinc 100
        self.dim_text = "#a1a1aa"       # Zinc 400
        self.success_color = "#4ade80"  # Green 400
        self.warning_color = "#facc15"  # Yellow 400

        self.root.configure(bg=self.bg_color)

        self.style.configure(".", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("Card.TFrame", background=self.card_bg)
        self.style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.accent_color, background=self.bg_color)
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground=self.dim_text, background=self.bg_color)
        self.style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.text_color, background=self.card_bg)

        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), foreground="#000000", background=self.accent_color)
        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), foreground="#000000", background=self.success_color)

        # Treeview styling
        self.style.configure("Treeview",
                             background="#27272a",
                             foreground="#f4f4f5",
                             fieldbackground="#27272a",
                             rowheight=26,
                             font=("Segoe UI", 9))
        self.style.map("Treeview", background=[("selected", "#0284c7")])
        self.style.configure("Treeview.Heading",
                             background="#3f3f46",
                             foreground="#ffffff",
                             font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        ttk.Label(header_frame, text="📸 LuminaSort", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header_frame,
            text="AI-Assisted Photo, Screenshot & Video Organizer with EXIF, GPS & Duplicate Detection",
            style="Subtitle.TLabel"
        ).pack(anchor=tk.W)

        # Paths Config Card
        path_card = ttk.Frame(self.root, style="Card.TFrame", padding=12)
        path_card.pack(fill=tk.X, padx=20, pady=5)

        # Source Row
        ttk.Label(path_card, text="📁 Source Folder (Messy):", style="Section.TLabel").grid(row=0, column=0, sticky=tk.W, pady=3)
        src_entry = ttk.Entry(path_card, textvariable=self.source_dir_var, width=65)
        src_entry.grid(row=0, column=1, padx=10, pady=3, sticky=tk.EW)
        ttk.Button(path_card, text="Browse...", command=self._browse_source).grid(row=0, column=2, padx=3)

        # Destination Row
        ttk.Label(path_card, text="📂 Destination Folder:", style="Section.TLabel").grid(row=1, column=0, sticky=tk.W, pady=3)
        dest_entry = ttk.Entry(path_card, textvariable=self.dest_dir_var, width=65)
        dest_entry.grid(row=1, column=1, padx=10, pady=3, sticky=tk.EW)
        ttk.Button(path_card, text="Browse...", command=self._browse_dest).grid(row=1, column=2, padx=3)

        path_card.columnconfigure(1, weight=1)

        # Options Card
        opts_card = ttk.Frame(self.root, style="Card.TFrame", padding=12)
        opts_card.pack(fill=tk.X, padx=20, pady=5)

        # Mode Selection
        ttk.Label(opts_card, text="Sorting Mode:", style="Section.TLabel").grid(row=0, column=0, sticky=tk.W, padx=5)
        modes = [
            ("Camera/Screenshots/Date (Smart)", "source-date"),
            ("Date Only (YYYY/MM)", "date-only"),
            ("Trips & Vacations (GPS to Cities)", "trips"),
            ("Source Category Only", "source-only")
        ]
        for col_idx, (text, val) in enumerate(modes):
            r = tk.Radiobutton(
                opts_card, text=text, value=val, variable=self.mode_var,
                bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
                activebackground=self.card_bg, activeforeground=self.accent_color
            )
            r.grid(row=0, column=col_idx + 1, padx=8, sticky=tk.W)

        # Checkboxes for Duplicates and Features
        chk_frame = ttk.Frame(opts_card, style="Card.TFrame")
        chk_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))

        tk.Checkbutton(
            chk_frame, text="Exact Duplicates (SHA-256)", variable=self.dedup_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
            activebackground=self.card_bg, activeforeground=self.accent_color
        ).pack(side=tk.LEFT, padx=8)

        tk.Checkbutton(
            chk_frame, text="Visual Similarities (pHash/dHash)", variable=self.similar_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
            activebackground=self.card_bg, activeforeground=self.accent_color
        ).pack(side=tk.LEFT, padx=8)

        tk.Checkbutton(
            chk_frame, text="Offline GPS Reverse-Geocoding", variable=self.geo_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
            activebackground=self.card_bg, activeforeground=self.accent_color
        ).pack(side=tk.LEFT, padx=8)

        # Action Selector
        ttk.Label(chk_frame, text="Action:", style="Section.TLabel").pack(side=tk.LEFT, padx=(20, 5))
        tk.Radiobutton(
            chk_frame, text="Safe Copy", value="copy", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
            activebackground=self.card_bg, activeforeground=self.accent_color
        ).pack(side=tk.LEFT, padx=5)

        tk.Radiobutton(
            chk_frame, text="Fast Move", value="move", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#3f3f46",
            activebackground=self.card_bg, activeforeground=self.accent_color
        ).pack(side=tk.LEFT, padx=5)

        # Summary Bar (Cards)
        self.summary_frame = ttk.Frame(self.root, style="Card.TFrame", padding=10)
        self.summary_frame.pack(fill=tk.X, padx=20, pady=5)

        self.lbl_scanned = ttk.Label(self.summary_frame, text="Scanned: 0 files", style="Section.TLabel")
        self.lbl_scanned.pack(side=tk.LEFT, padx=12)

        self.lbl_dups = ttk.Label(self.summary_frame, text="Duplicates: 0 (0 B saveable)", style="Section.TLabel")
        self.lbl_dups.pack(side=tk.LEFT, padx=12)

        self.lbl_breakdown = ttk.Label(self.summary_frame, text="Categories: None", foreground=self.dim_text)
        self.lbl_breakdown.pack(side=tk.LEFT, padx=12)

        # Preview Table (Treeview)
        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        columns = ("file", "category", "date", "target", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("file", text="Original File Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("date", text="Capture Date")
        self.tree.heading("target", text="Target Destination Folder")
        self.tree.heading("note", text="Status / Duplicate")

        self.tree.column("file", width=200, anchor=tk.W)
        self.tree.column("category", width=120, anchor=tk.CENTER)
        self.tree.column("date", width=100, anchor=tk.CENTER)
        self.tree.column("target", width=340, anchor=tk.W)
        self.tree.column("note", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Action Bar
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=20, pady=(10, 15))

        # Status Label
        ttk.Label(bottom_frame, textvariable=self.status_var, font=("Segoe UI", 9, "italic"), foreground=self.dim_text).pack(side=tk.LEFT, padx=5)

        # Buttons
        self.btn_undo = ttk.Button(bottom_frame, text="🔄 1-Click Undo", command=self._on_undo)
        self.btn_undo.pack(side=tk.RIGHT, padx=5)

        self.btn_execute = ttk.Button(bottom_frame, text="🚀 Execute Sorting", style="Success.TButton", command=self._on_execute)
        self.btn_execute.pack(side=tk.RIGHT, padx=5)

        self.btn_preview = ttk.Button(bottom_frame, text="🔍 Dry Run Preview", style="Primary.TButton", command=self._on_preview)
        self.btn_preview.pack(side=tk.RIGHT, padx=5)

    def _browse_source(self):
        d = filedialog.askdirectory(title="Select Folder to Organize")
        if d:
            self.source_dir_var.set(d)
            if not self.dest_dir_var.get():
                self.dest_dir_var.set(str(Path(d) / "Organized_Gallery"))

    def _browse_dest(self):
        d = filedialog.askdirectory(title="Select Destination Folder")
        if d:
            self.dest_dir_var.set(d)

    def _get_config(self, action="dry-run") -> OrganizerConfig:
        src = self.source_dir_var.get().strip()
        if not src or not Path(src).is_dir():
            raise ValueError("Please select a valid Source directory.")
        dst = self.dest_dir_var.get().strip() or None

        return OrganizerConfig(
            source_dir=Path(src),
            dest_dir=Path(dst) if dst else None,
            mode=self.mode_var.get(),
            action=action,
            detect_duplicates=self.dedup_var.get(),
            detect_similar=self.similar_var.get(),
            enable_geocoding=self.geo_var.get(),
            duplicate_action="isolate"
        )

    def _on_preview(self):
        try:
            config = self._get_config(action="dry-run")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        self.status_var.set("Scanning and analyzing media files...")
        self.btn_preview.configure(state=tk.DISABLED)

        def worker():
            sorter = GallerySorter(config)
            report = sorter.plan()
            self.root.after(0, lambda: self._update_preview_results(report))

        threading.Thread(target=worker, daemon=True).start()

    def _update_preview_results(self, report: SortReport):
        self.btn_preview.configure(state=tk.NORMAL)
        self.current_report = report

        # Clear Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Populate rows
        for op in report.planned_operations:
            note = ""
            if op.is_duplicate:
                note = f"⚠️ Dup ({op.duplicate_type})"

            try:
                rel_target = str(op.dest_path.relative_to(op.dest_path.parents[2]))
            except Exception:
                rel_target = op.dest_path.name

            self.tree.insert("", tk.END, values=(
                op.source_path.name,
                op.category,
                op.date_str,
                rel_target,
                note
            ))

        # Update Summary Badges
        self.lbl_scanned.config(text=f"Scanned: {report.total_scanned} files ({format_bytes(report.total_size_bytes)})")
        dup_total = report.exact_duplicates_count + report.similar_duplicates_count
        self.lbl_dups.config(text=f"Duplicates: {dup_total} ({format_bytes(report.duplicate_saved_bytes)} saveable)")

        cat_summary = " | ".join(f"{k}: {v}" for k, v in report.category_counts.items())
        self.lbl_breakdown.config(text=cat_summary or "None")

        self.status_var.set(f"Dry-run scan complete in {report.duration_seconds:.2f}s. Review preview above.")

    def _on_execute(self):
        try:
            action = self.action_var.get()
            config = self._get_config(action=action)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        if not self.current_report or not self.current_report.planned_operations:
            messagebox.showwarning("Notice", "Please click 'Dry Run Preview' first to analyze files.")
            return

        confirm_msg = (
            f"Are you sure you want to execute sorting?\n\n"
            f"• Action: {action.upper()}\n"
            f"• Source: {config.source_dir}\n"
            f"• Destination: {config.dest_dir}\n"
            f"• Total Files: {len(self.current_report.planned_operations)}\n\n"
            f"A 1-click Undo manifest will be generated."
        )
        if not messagebox.askyesno("Confirm Organization", confirm_msg):
            return

        self.status_var.set(f"Executing {action.upper()} operations...")
        self.btn_execute.configure(state=tk.DISABLED)

        def worker():
            sorter = GallerySorter(config)
            # Re-use planned report or plan fresh
            rep = sorter.execute(self.current_report)
            self.root.after(0, lambda: self._on_execute_complete(rep))

        threading.Thread(target=worker, daemon=True).start()

    def _on_execute_complete(self, report: SortReport):
        self.btn_execute.configure(state=tk.NORMAL)
        self.manifest_path = report.manifest_path

        self.status_var.set(f"✅ Sorting complete! Manifest saved.")
        msg = f"Organization successfully completed!\n\nManifest saved to:\n{report.manifest_path}\n\nYou can undo this anytime using the '1-Click Undo' button."
        messagebox.showinfo("Success", msg)

    def _on_undo(self):
        manifest = filedialog.askopenfilename(
            title="Select Sort Manifest File to Undo",
            filetypes=[("JSON Manifest", "*.json")]
        )
        if not manifest:
            return

        if not messagebox.askyesno("Confirm Undo", f"Revert operations from manifest:\n{manifest}?"):
            return

        try:
            success, fail, errors = run_undo(Path(manifest))
            msg = f"Rollback Complete!\n\nReverted files: {success}"
            if fail > 0:
                msg += f"\nFailed/Warnings: {fail}"
            messagebox.showinfo("Undo Results", msg)
            self.status_var.set(f"Undo completed: {success} files reverted.")
        except Exception as e:
            messagebox.showerror("Undo Error", str(e))

def start_gui():
    root = tk.Tk()
    app = LuminaSortGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_gui()
