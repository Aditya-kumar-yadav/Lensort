"""
Desktop Graphical User Interface (GUI) for Lensort.
Features high-contrast dark theme, live multithreaded scanning,
dynamic motion animation of files moving to target folders, and live ticking badges.
"""

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .config import OrganizerConfig
from .organizer import GallerySorter, run_undo, SortReport, PlannedOperation
from .ui import format_bytes

class LensortGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lensort — Smart Gallery & Photo Organizer")
        self.root.geometry("1060x760")
        self.root.minsize(840, 600)

        # High-Contrast Dark Theme Palette
        self.bg_color = "#121214"
        self.card_bg = "#1e1e24"
        self.entry_bg = "#272730"
        self.accent_color = "#38bdf8"   # Sky 400
        self.accent_hover = "#0284c7"
        self.text_color = "#ffffff"
        self.dim_text = "#9ca3af"
        self.success_color = "#22c55e"  # Green 500
        self.warning_color = "#facc15"  # Amber 400
        self.badge_bg = "#2d2d38"

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

        # Dynamic Live Stats
        self.status_var = tk.StringVar(value="Ready. Select folder and click 'RUN DRY-RUN PREVIEW'.")
        self.active_file_var = tk.StringVar(value="Waiting to start...")
        self.progress_pct_var = tk.DoubleVar(value=0.0)

        # Live Badges
        self.count_screenshots = tk.StringVar(value="📱 Screenshots: 0")
        self.count_whatsapp = tk.StringVar(value="💬 WhatsApp: 0")
        self.count_camera = tk.StringVar(value="📷 Camera: 0")
        self.count_videos = tk.StringVar(value="🎥 Videos: 0")
        self.count_dups = tk.StringVar(value="⚠️ Duplicates: 0")

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
        self.style.configure("Horizontal.TProgressbar", background="#38bdf8", troughcolor="#272730", bordercolor="#1e1e24")

        # Treeview styling
        self.style.configure("Treeview",
                             background="#1a1a20",
                             foreground="#ffffff",
                             fieldbackground="#1a1a20",
                             rowheight=25,
                             font=("Segoe UI", 9))
        self.style.map("Treeview", background=[("selected", "#0284c7")])
        self.style.configure("Treeview.Heading",
                             background="#272730",
                             foreground="#38bdf8",
                             font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # 1. Header Frame
        header_frame = tk.Frame(self.root, bg=self.bg_color)
        header_frame.pack(fill=tk.X, padx=20, pady=(10, 4))

        tk.Label(
            header_frame,
            text="📸 Lensort",
            font=("Segoe UI", 18, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        tk.Label(
            header_frame,
            text="Intelligent Photo, Screenshot & Video Organizer with Live Dynamic Sorting",
            font=("Segoe UI", 9),
            fg=self.dim_text,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        # 2. Paths Input Card
        path_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=8, relief="groove", bd=1)
        path_card.pack(fill=tk.X, padx=20, pady=3)

        # Source
        tk.Label(path_card, text="📁 Source Folder (Messy):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, pady=3)
        self.src_entry = tk.Entry(
            path_card, textvariable=self.source_dir_var, font=("Segoe UI", 10),
            bg=self.entry_bg, fg="#ffffff", insertbackground=self.accent_color,
            relief="solid", bd=1, highlightthickness=1, highlightbackground="#3f3f46", highlightcolor=self.accent_color
        )
        self.src_entry.grid(row=0, column=1, padx=8, pady=3, sticky=tk.EW)
        tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#3f3f46", fg="#ffffff", activebackground="#52525b", relief="flat", padx=10, pady=2,
            command=self._browse_source
        ).grid(row=0, column=2, padx=4)

        # Destination
        tk.Label(path_card, text="📂 Destination Folder:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.dest_entry = tk.Entry(
            path_card, textvariable=self.dest_dir_var, font=("Segoe UI", 10),
            bg=self.entry_bg, fg="#ffffff", insertbackground=self.accent_color,
            relief="solid", bd=1, highlightthickness=1, highlightbackground="#3f3f46", highlightcolor=self.accent_color
        )
        self.dest_entry.grid(row=1, column=1, padx=8, pady=3, sticky=tk.EW)
        tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#3f3f46", fg="#ffffff", activebackground="#52525b", relief="flat", padx=10, pady=2,
            command=self._browse_dest
        ).grid(row=1, column=2, padx=4)

        path_card.columnconfigure(1, weight=1)

        # 3. Mode & Options Card
        opts_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=6, relief="groove", bd=1)
        opts_card.pack(fill=tk.X, padx=20, pady=3)

        tk.Label(opts_card, text="Sorting Mode:", font=("Segoe UI", 9, "bold"), fg=self.accent_color, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, padx=4)
        modes = [
            ("Camera/Screenshots/Date (Smart)", "source-date"),
            ("Date Only (YYYY/MM)", "date-only"),
            ("Trips & Vacations (GPS to Cities)", "trips"),
            ("Source Category Only", "source-only")
        ]
        for col_idx, (text, val) in enumerate(modes):
            tk.Radiobutton(
                opts_card, text=text, value=val, variable=self.mode_var,
                bg=self.card_bg, fg=self.text_color, selectcolor="#121214",
                activebackground=self.card_bg, activeforeground=self.accent_color, font=("Segoe UI", 9)
            ).grid(row=0, column=col_idx + 1, padx=5, sticky=tk.W)

        chk_frame = tk.Frame(opts_card, bg=self.card_bg)
        chk_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(4, 0))

        tk.Checkbutton(
            chk_frame, text="Exact Duplicates (SHA-256)", variable=self.dedup_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(
            chk_frame, text="Visual Similarities (pHash)", variable=self.similar_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(
            chk_frame, text="Offline GPS Geocoding", variable=self.geo_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(chk_frame, text="│  Action:", font=("Segoe UI", 9, "bold"), fg=self.warning_color, bg=self.card_bg).pack(side=tk.LEFT, padx=(12, 4))
        tk.Radiobutton(
            chk_frame, text="Safe Copy", value="copy", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214", font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=3)
        tk.Radiobutton(
            chk_frame, text="Fast Move", value="move", variable=self.action_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#121214", font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT, padx=3)

        # 4. Action Toolbar
        action_toolbar = tk.Frame(self.root, bg=self.bg_color)
        action_toolbar.pack(fill=tk.X, padx=20, pady=(6, 4))

        self.btn_preview = tk.Button(
            action_toolbar, text="🔍  1. RUN DRY-RUN PREVIEW", font=("Segoe UI", 11, "bold"),
            bg=self.accent_color, fg="#000000", activebackground=self.accent_hover,
            relief="flat", padx=16, pady=7, cursor="hand2", command=self._on_preview
        )
        self.btn_preview.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_execute = tk.Button(
            action_toolbar, text="🚀  2. EXECUTE SORTING", font=("Segoe UI", 11, "bold"),
            bg=self.success_color, fg="#000000", activebackground="#16a34a",
            relief="flat", padx=16, pady=7, cursor="hand2", command=self._on_execute
        )
        self.btn_execute.pack(side=tk.LEFT, padx=10)

        self.btn_undo = tk.Button(
            action_toolbar, text="🔄  1-Click Undo", font=("Segoe UI", 10, "bold"),
            bg="#374151", fg="#f3f4f6", activebackground="#4b5563",
            relief="flat", padx=14, pady=7, cursor="hand2", command=self._on_undo
        )
        self.btn_undo.pack(side=tk.RIGHT)

        # 5. DYNAMIC LIVE ANIMATION & TICKING BADGES CARD
        anim_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=6, relief="ridge", bd=1)
        anim_card.pack(fill=tk.X, padx=20, pady=3)

        # Row 1: Live Animated Moving Banner
        banner_frame = tk.Frame(anim_card, bg=self.card_bg)
        banner_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            banner_frame, text="⚡ Live Action:", font=("Segoe UI", 9, "bold"),
            fg=self.warning_color, bg=self.card_bg
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Dynamic Ticker label showing current image flying to folder
        self.lbl_ticker = tk.Label(
            banner_frame, textvariable=self.active_file_var, font=("Segoe UI", 9, "bold"),
            fg="#38bdf8", bg=self.card_bg, anchor=tk.W
        )
        self.lbl_ticker.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 2: Live Progress Bar
        self.progress_bar = ttk.Progressbar(
            anim_card, orient=tk.HORIZONTAL, mode="determinate",
            variable=self.progress_pct_var, style="Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill=tk.X, pady=3)

        # Row 3: Live Ticking Category Badges
        badge_frame = tk.Frame(anim_card, bg=self.card_bg)
        badge_frame.pack(fill=tk.X, pady=(4, 2))

        def create_badge(parent, textvar, color):
            b = tk.Label(
                parent, textvariable=textvar, font=("Segoe UI", 9, "bold"),
                bg=self.badge_bg, fg=color, padx=10, pady=2, relief="flat"
            )
            b.pack(side=tk.LEFT, padx=4)
            return b

        create_badge(badge_frame, self.count_screenshots, "#38bdf8")
        create_badge(badge_frame, self.count_whatsapp, "#4ade80")
        create_badge(badge_frame, self.count_camera, "#f472b6")
        create_badge(badge_frame, self.count_videos, "#a78bfa")
        create_badge(badge_frame, self.count_dups, "#fbbf24")

        # 6. Bottom Status Bar (Packed Bottom First)
        bottom_frame = tk.Frame(self.root, bg=self.bg_color, padx=4, pady=3)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(2, 6))

        tk.Label(
            bottom_frame, textvariable=self.status_var,
            font=("Segoe UI", 9, "italic"), fg=self.accent_color, bg=self.bg_color
        ).pack(side=tk.LEFT)

        # 7. Preview Table (Fills All Remaining Space in Middle)
        table_frame = tk.Frame(self.root, bg=self.bg_color)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=3)

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

        # Clear existing Treeview rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.btn_preview.configure(state=tk.DISABLED, text="⏳ Analyzing Live...")
        self.progress_pct_var.set(0.0)
        self.status_var.set("Scanning media files in parallel...")

        # Reset category counters
        self.count_screenshots.set("📱 Screenshots: 0")
        self.count_whatsapp.set("💬 WhatsApp: 0")
        self.count_camera.set("📷 Camera: 0")
        self.count_videos.set("🎥 Videos: 0")
        self.count_dups.set("⚠️ Duplicates: 0")

        def on_progress(data: dict):
            # Thread-safe UI update
            self.root.after(0, lambda: self._handle_progress_update(data))

        def worker():
            sorter = GallerySorter(config)
            report = sorter.plan(progress_callback=on_progress)
            self.root.after(0, lambda: self._on_preview_complete(report))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_progress_update(self, data: dict):
        current = data.get("current", 0)
        total = max(1, data.get("total", 1))
        pct = (current / total) * 100.0
        self.progress_pct_var.set(pct)

        stage = data.get("stage", "")
        filename = data.get("file", "")
        category = data.get("category", "")
        target = data.get("target", "")

        # Dynamic motion banner animation
        if filename:
            self.active_file_var.set(f"[{filename}]  ────────►  📁 {target}")
            self.status_var.set(f"Processed: {current} / {total} files ({pct:.1f}%)")

        # Live Badges update
        cat_counts = data.get("category_counts", {})
        if cat_counts:
            self.count_screenshots.set(f"📱 Screenshots: {cat_counts.get('Screenshots', 0)}")
            self.count_whatsapp.set(f"💬 WhatsApp: {cat_counts.get('WhatsApp & Social', 0)}")
            self.count_camera.set(f"📷 Camera: {cat_counts.get('Camera Originals', 0)}")
            self.count_videos.set(f"🎥 Videos: {cat_counts.get('Videos', 0)}")
        if "duplicates_count" in data:
            self.count_dups.set(f"⚠️ Duplicates: {data['duplicates_count']}")

        # Stream row into Treeview live
        op: PlannedOperation = data.get("operation")
        if op:
            note = f"⚠️ Dup ({op.duplicate_type})" if op.is_duplicate else ""
            try:
                rel_target = str(op.dest_path.relative_to(op.dest_path.parents[2]))
            except Exception:
                rel_target = op.dest_path.name

            item = self.tree.insert("", tk.END, values=(
                op.source_path.name,
                op.category,
                op.date_str,
                rel_target,
                note
            ))
            # Auto-scroll to show dynamic movement
            self.tree.see(item)

    def _on_preview_complete(self, report: SortReport):
        self.btn_preview.configure(state=tk.NORMAL, text="🔍  1. RUN DRY-RUN PREVIEW")
        self.current_report = report
        self.progress_pct_var.set(100.0)

        # Final category badges
        cats = report.category_counts
        self.count_screenshots.set(f"📱 Screenshots: {cats.get('Screenshots', 0)}")
        self.count_whatsapp.set(f"💬 WhatsApp: {cats.get('WhatsApp & Social', 0)}")
        self.count_camera.set(f"📷 Camera: {cats.get('Camera Originals', 0)}")
        self.count_videos.set(f"🎥 Videos: {cats.get('Videos', 0)}")
        dup_total = report.exact_duplicates_count + report.similar_duplicates_count
        self.count_dups.set(f"⚠️ Duplicates: {dup_total}")

        self.active_file_var.set(f"✨ Ready! {report.total_scanned} files analyzed in {report.duration_seconds:.2f}s ({format_bytes(report.duplicate_saved_bytes)} saveable).")
        self.status_var.set(f"Dry-run scan complete! Click '🚀 2. EXECUTE SORTING' to begin.")

    def _on_execute(self):
        try:
            action = self.action_var.get()
            config = self._get_config(action=action)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        if not self.current_report or not self.current_report.planned_operations:
            messagebox.showwarning("Notice", "Please click '🔍 1. RUN DRY-RUN PREVIEW' first to analyze your files.")
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

        self.btn_execute.configure(state=tk.DISABLED, text="🚀 Sorting Live...")
        self.progress_pct_var.set(0.0)

        def on_sort_progress(data: dict):
            self.root.after(0, lambda: self._handle_sort_progress(data))

        def worker():
            sorter = GallerySorter(config)
            rep = sorter.execute(self.current_report, progress_callback=on_sort_progress)
            self.root.after(0, lambda: self._on_execute_complete(rep))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_sort_progress(self, data: dict):
        current = data.get("current", 0)
        total = max(1, data.get("total", 1))
        pct = (current / total) * 100.0
        self.progress_pct_var.set(pct)

        filename = data.get("file", "")
        target = data.get("target", "")
        if filename:
            self.active_file_var.set(f"🚀 Moving [{filename}]  ────────►  📁 {target}")
            self.status_var.set(f"Sorting in progress: {current} / {total} files ({pct:.1f}%)")

    def _on_execute_complete(self, report: SortReport):
        self.btn_execute.configure(state=tk.NORMAL, text="🚀  2. EXECUTE SORTING")
        self.progress_pct_var.set(100.0)
        self.manifest_path = report.manifest_path

        self.active_file_var.set("🎉 All files sorted successfully!")
        self.status_var.set(f"✅ Organization complete! Manifest saved.")

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
