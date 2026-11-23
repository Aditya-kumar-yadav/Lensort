"""
Desktop Graphical User Interface (GUI) for Lensort.
Built using Python's native Tkinter + ttk (zero third-party dependencies required).
Runs out-of-the-box on Windows, macOS, and Linux with a high-contrast dark theme.
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

class LensortGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lensort — Smart Gallery & Photo Organizer")
        self.root.geometry("1020x720")
        self.root.minsize(800, 560)

        # High-Contrast Dark Theme Palette
        self.bg_color = "#121214"      # Dark background
        self.card_bg = "#1e1e24"       # Dark Card background
        self.entry_bg = "#272730"      # High contrast entry field background
        self.accent_color = "#38bdf8"   # Bright Sky Blue 400
        self.accent_hover = "#0284c7"   # Sky Blue 600
        self.text_color = "#ffffff"     # Pure Crisp White
        self.dim_text = "#9ca3af"       # Muted Gray
        self.success_color = "#22c55e"  # Emerald Green 500
        self.warning_color = "#eab308"  # Yellow 500
        self.danger_color = "#ef4444"   # Red 500

        self.root.configure(bg=self.bg_color)
        self._setup_styles()

        # State Variables
        self.source_dir_var = tk.StringVar(value="")
        self.dest_dir_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="source-date")
        self.action_var = tk.StringVar(value="copy")
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

        self.style.configure(".", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("Card.TFrame", background=self.card_bg)
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground=self.accent_color, background=self.bg_color)
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground=self.dim_text, background=self.bg_color)
        self.style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.text_color, background=self.card_bg)

        # Button Styles
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#3f3f46", foreground="#ffffff")
        self.style.map("TButton", background=[("active", "#52525b")])

        # Treeview styling
        self.style.configure("Treeview",
                             background="#1a1a20",
                             foreground="#ffffff",
                             fieldbackground="#1a1a20",
                             rowheight=26,
                             font=("Segoe UI", 9))
        self.style.map("Treeview", background=[("selected", "#0284c7")])
        self.style.configure("Treeview.Heading",
                             background="#272730",
                             foreground="#38bdf8",
                             font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # 1. Header Frame
        header_frame = tk.Frame(self.root, bg=self.bg_color)
        header_frame.pack(fill=tk.X, padx=20, pady=(12, 6))

        tk.Label(
            header_frame,
            text="📸 Lensort",
            font=("Segoe UI", 18, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        tk.Label(
            header_frame,
            text="Intelligent Photo, Screenshot & Video Organizer with EXIF, GPS & Duplicate Detection",
            font=("Segoe UI", 9),
            fg=self.dim_text,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        # 2. Paths Input Card (HIGH CONTRAST ENTRY BOXES)
        path_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=10, relief="groove", bd=1)
        path_card.pack(fill=tk.X, padx=20, pady=4)

        # Source Row
        tk.Label(path_card, text="📁 Source Folder (Messy):", font=("Segoe UI", 10, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, pady=4)
        
        # High Contrast Dark Entry with Pure White Text & Cyan Cursor
        self.src_entry = tk.Entry(
            path_card,
            textvariable=self.source_dir_var,
            font=("Segoe UI", 10),
            bg=self.entry_bg,
            fg="#ffffff",
            insertbackground=self.accent_color,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#3f3f46",
            highlightcolor=self.accent_color
        )
        self.src_entry.grid(row=0, column=1, padx=10, pady=4, sticky=tk.EW)
        
        btn_src = tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#3f3f46", fg="#ffffff", activebackground="#52525b", activeforeground="#ffffff",
            relief="flat", padx=10, pady=3, command=self._browse_source
        )
        btn_src.grid(row=0, column=2, padx=4)

        # Destination Row
        tk.Label(path_card, text="📂 Destination Folder:", font=("Segoe UI", 10, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=1, column=0, sticky=tk.W, pady=4)
        
        self.dest_entry = tk.Entry(
            path_card,
            textvariable=self.dest_dir_var,
            font=("Segoe UI", 10),
            bg=self.entry_bg,
            fg="#ffffff",
            insertbackground=self.accent_color,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#3f3f46",
            highlightcolor=self.accent_color
        )
        self.dest_entry.grid(row=1, column=1, padx=10, pady=4, sticky=tk.EW)

        btn_dst = tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#3f3f46", fg="#ffffff", activebackground="#52525b", activeforeground="#ffffff",
            relief="flat", padx=10, pady=3, command=self._browse_dest
        )
        btn_dst.grid(row=1, column=2, padx=4)

        path_card.columnconfigure(1, weight=1)

        # 3. Options Card
        opts_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=8, relief="groove", bd=1)
        opts_card.pack(fill=tk.X, padx=20, pady=4)

        # Row 1: Mode Selection
        tk.Label(opts_card, text="Sorting Mode:", font=("Segoe UI", 10, "bold"), fg=self.accent_color, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, padx=4)
        modes = [
            ("Camera/Screenshots/Date (Smart)", "source-date"),
            ("Date Only (YYYY/MM)", "date-only"),
            ("Trips & Vacations (GPS to Cities)", "trips"),
            ("Source Category Only", "source-only")
        ]
        for col_idx, (text, val) in enumerate(modes):
            r = tk.Radiobutton(
                opts_card, text=text, value=val, variable=self.mode_var,
                bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
                activebackground=self.card_bg, activeforeground=self.accent_color,
                font=("Segoe UI", 9)
            )
            r.grid(row=0, column=col_idx + 1, padx=6, sticky=tk.W)

        # Row 2: Duplicate Checkboxes & Actions
        chk_frame = tk.Frame(opts_card, bg=self.card_bg)
        chk_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))

        tk.Checkbutton(
            chk_frame, text="Exact Duplicates (SHA-256)", variable=self.dedup_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
            activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=6)

        tk.Checkbutton(
            chk_frame, text="Visual Similarities (pHash/dHash)", variable=self.similar_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
            activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=6)

        tk.Checkbutton(
            chk_frame, text="Offline GPS Reverse-Geocoding", variable=self.geo_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
            activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=6)

        tk.Label(chk_frame, text="│  Action:", font=("Segoe UI", 10, "bold"), fg=self.warning_color, bg=self.card_bg).pack(side=tk.LEFT, padx=(15, 6))
        tk.Radiobutton(
            chk_frame, text="Safe Copy", value="copy", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
            activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=4)

        tk.Radiobutton(
            chk_frame, text="Fast Move", value="move", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
            activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=4)

        # 4. BIG PROMINENT ACTION TOOLBAR (ALWAYS VISIBLE RIGHT IN THE CENTER)
        action_toolbar = tk.Frame(self.root, bg=self.bg_color)
        action_toolbar.pack(fill=tk.X, padx=20, pady=(6, 4))

        # Big Cyan DRY RUN PREVIEW Button
        self.btn_preview = tk.Button(
            action_toolbar,
            text="🔍  1. RUN DRY-RUN PREVIEW",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg="#000000",
            activebackground=self.accent_hover,
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_preview
        )
        self.btn_preview.pack(side=tk.LEFT, padx=(0, 10))

        # Big Green EXECUTE SORTING Button
        self.btn_execute = tk.Button(
            action_toolbar,
            text="🚀  2. EXECUTE SORTING",
            font=("Segoe UI", 11, "bold"),
            bg=self.success_color,
            fg="#000000",
            activebackground="#16a34a",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_execute
        )
        self.btn_execute.pack(side=tk.LEFT, padx=10)

        # 1-Click Undo Button
        self.btn_undo = tk.Button(
            action_toolbar,
            text="🔄  1-Click Undo",
            font=("Segoe UI", 10, "bold"),
            bg="#374151",
            fg="#f3f4f6",
            activebackground="#4b5563",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._on_undo
        )
        self.btn_undo.pack(side=tk.RIGHT)

        # 5. Summary Info Bar
        self.summary_frame = tk.Frame(self.root, bg=self.card_bg, padx=12, pady=6)
        self.summary_frame.pack(fill=tk.X, padx=20, pady=(4, 4))

        self.lbl_scanned = tk.Label(self.summary_frame, text="Scanned: 0 files", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_bg)
        self.lbl_scanned.pack(side=tk.LEFT, padx=8)

        self.lbl_dups = tk.Label(self.summary_frame, text="Duplicates: 0 (0 B saveable)", font=("Segoe UI", 9, "bold"), fg=self.warning_color, bg=self.card_bg)
        self.lbl_dups.pack(side=tk.LEFT, padx=12)

        self.lbl_breakdown = tk.Label(self.summary_frame, text="Categories: None", font=("Segoe UI", 9), fg=self.dim_text, bg=self.card_bg)
        self.lbl_breakdown.pack(side=tk.LEFT, padx=12)

        # 6. Bottom Status Bar (PACKED AT THE VERY BOTTOM FIRST SO IT NEVER DISAPPEARS)
        bottom_frame = tk.Frame(self.root, bg=self.bg_color, padx=4, pady=4)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(2, 6))

        self.lbl_status = tk.Label(
            bottom_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9, "italic"),
            fg=self.accent_color,
            bg=self.bg_color
        )
        self.lbl_status.pack(side=tk.LEFT)

        # 7. Preview Table (Fills All Remaining Space in Middle)
        table_frame = tk.Frame(self.root, bg=self.bg_color)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(2, 4))

        columns = ("file", "category", "date", "target", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("file", text="Original File Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("date", text="Capture Date")
        self.tree.heading("target", text="Target Destination Folder")
        self.tree.heading("note", text="Status / Duplicate")

        self.tree.column("file", width=220, anchor=tk.W)
        self.tree.column("category", width=130, anchor=tk.CENTER)
        self.tree.column("date", width=110, anchor=tk.CENTER)
        self.tree.column("target", width=360, anchor=tk.W)
        self.tree.column("note", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

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
            raise ValueError("Please enter or browse a valid Source directory.")
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
            messagebox.showerror("Invalid Path", str(e))
            return

        self.status_var.set("⏳ Scanning and analyzing media files... Please wait.")
        self.btn_preview.configure(state=tk.DISABLED, text="⏳ Analyzing...")

        def worker():
            sorter = GallerySorter(config)
            report = sorter.plan()
            self.root.after(0, lambda: self._update_preview_results(report))

        threading.Thread(target=worker, daemon=True).start()

    def _update_preview_results(self, report: SortReport):
        self.btn_preview.configure(state=tk.NORMAL, text="🔍  1. RUN DRY-RUN PREVIEW")
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

        self.status_var.set(f"✅ Dry-run scan complete! {report.total_scanned} files analyzed in {report.duration_seconds:.2f}s.")

    def _on_execute(self):
        try:
            action = self.action_var.get()
            config = self._get_config(action=action)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        if not self.current_report or not self.current_report.planned_operations:
            messagebox.showwarning("Notice", "Please click '🔍 RUN DRY-RUN PREVIEW' first to analyze your files.")
            return

        confirm_msg = (
            f"Are you sure you want to execute sorting?\n\n"
            f"• Action: {action.upper()}\n"
            f"• Source: {config.source_dir}\n"
            f"• Destination: {config.dest_dir}\n"
            f"• Total Files: {len(self.current_report.planned_operations)}\n\n"
            f"A 1-click Undo manifest will be generated automatically."
        )
        if not messagebox.askyesno("Confirm Organization", confirm_msg):
            return

        self.status_var.set(f"🚀 Executing {action.upper()} operations...")
        self.btn_execute.configure(state=tk.DISABLED)

        def worker():
            sorter = GallerySorter(config)
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
    app = LensortGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_gui()
