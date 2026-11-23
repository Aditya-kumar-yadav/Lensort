"""
Desktop Graphical User Interface (GUI) for Lensort.
Features high-contrast dark theme, live multithreaded scanning,
aesthetic visual sorting conveyor animation, live table checkoffs,
speedometer, and explicit clarity on Safe Copy vs Fast Move.
"""

import os
import sys
import time
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
        self.root.geometry("1080x780")
        self.root.minsize(860, 620)

        # High-Contrast Dark Theme Palette
        self.bg_color = "#0f172a"      # Deep Slate 900
        self.card_bg = "#1e293b"       # Slate 800
        self.entry_bg = "#0f172a"      # Slate 900
        self.accent_cyan = "#38bdf8"    # Sky 400
        self.accent_hover = "#0284c7"
        self.text_color = "#ffffff"
        self.dim_text = "#94a3b8"       # Slate 400
        self.success_color = "#22c55e"  # Emerald 500
        self.warning_color = "#facc15"  # Amber 400
        self.purple_color = "#c084fc"   # Purple 400
        self.badge_bg = "#334155"       # Slate 700

        self.root.configure(bg=self.bg_color)
        self._setup_styles()

        # State Variables
        self.source_dir_var = tk.StringVar(value="")
        self.dest_dir_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="source-date")
        self.action_var = tk.StringVar(value="copy")  # "copy" or "move"
        self.dedup_var = tk.BooleanVar(value=True)
        self.similar_var = tk.BooleanVar(value=True)
        self.geo_var = tk.BooleanVar(value=True)

        # Dynamic Live Stats
        self.status_var = tk.StringVar(value="Ready. Select folder and click '1. RUN DRY-RUN PREVIEW'.")
        self.progress_pct_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="0 / 0 files (0%)")
        self.speed_text_var = tk.StringVar(value="Speed: 0 files/s")

        # Conveyor Visual State
        self.curr_source_file = tk.StringVar(value="Ready for sorting...")
        self.curr_target_folder = tk.StringVar(value="Organized_Gallery")
        self.arrow_animation_phase = 0
        self.arrow_symbols = ["──►", "───►", "────►", "─────►", "──────►", "───────►"]

        # Live Badges
        self.count_screenshots = tk.StringVar(value="📱 Screenshots: 0")
        self.count_whatsapp = tk.StringVar(value="💬 WhatsApp: 0")
        self.count_camera = tk.StringVar(value="📷 Camera: 0")
        self.count_videos = tk.StringVar(value="🎥 Videos: 0")
        self.count_dups = tk.StringVar(value="⚠️ Duplicates: 0")

        # Mapping for table row lookups (for instant live checkoffs)
        self.tree_item_map = {}

        self.current_report: SortReport = None
        self.manifest_path: Path = None
        self.is_animating = False

        self._build_ui()

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure(".", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("Horizontal.TProgressbar",
                             background="#38bdf8",
                             troughcolor="#0f172a",
                             bordercolor="#1e293b",
                             lightcolor="#38bdf8",
                             darkcolor="#0284c7")

        # Treeview styling
        self.style.configure("Treeview",
                             background="#131d2e",
                             foreground="#ffffff",
                             fieldbackground="#131d2e",
                             rowheight=26,
                             font=("Segoe UI", 9))
        self.style.map("Treeview", background=[("selected", "#0284c7")])
        self.style.configure("Treeview.Heading",
                             background="#1e293b",
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
            fg=self.accent_cyan,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        tk.Label(
            header_frame,
            text="Aesthetic & Intelligent Media Sorter — Live Dynamic Motion Engine",
            font=("Segoe UI", 9),
            fg=self.dim_text,
            bg=self.bg_color
        ).pack(anchor=tk.W)

        # 2. Paths Card
        path_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=8, relief="groove", bd=1)
        path_card.pack(fill=tk.X, padx=20, pady=3)

        # Source
        tk.Label(path_card, text="📁 Source Folder (Messy):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, pady=3)
        self.src_entry = tk.Entry(
            path_card, textvariable=self.source_dir_var, font=("Segoe UI", 10),
            bg=self.entry_bg, fg="#ffffff", insertbackground=self.accent_cyan,
            relief="solid", bd=1, highlightthickness=1, highlightbackground="#475569", highlightcolor=self.accent_cyan
        )
        self.src_entry.grid(row=0, column=1, padx=8, pady=3, sticky=tk.EW)
        tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#475569", fg="#ffffff", activebackground="#64748b", relief="flat", padx=10, pady=2,
            command=self._browse_source
        ).grid(row=0, column=2, padx=4)

        # Destination
        tk.Label(path_card, text="📂 Destination Folder:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_bg).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.dest_entry = tk.Entry(
            path_card, textvariable=self.dest_dir_var, font=("Segoe UI", 10),
            bg=self.entry_bg, fg="#ffffff", insertbackground=self.accent_cyan,
            relief="solid", bd=1, highlightthickness=1, highlightbackground="#475569", highlightcolor=self.accent_cyan
        )
        self.dest_entry.grid(row=1, column=1, padx=8, pady=3, sticky=tk.EW)
        tk.Button(
            path_card, text="Browse...", font=("Segoe UI", 9, "bold"),
            bg="#475569", fg="#ffffff", activebackground="#64748b", relief="flat", padx=10, pady=2,
            command=self._browse_dest
        ).grid(row=1, column=2, padx=4)

        path_card.columnconfigure(1, weight=1)

        # 3. Options Card
        opts_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=6, relief="groove", bd=1)
        opts_card.pack(fill=tk.X, padx=20, pady=3)

        # Sorting Modes
        tk.Label(opts_card, text="Mode:", font=("Segoe UI", 9, "bold"), fg=self.accent_cyan, bg=self.card_bg).grid(row=0, column=0, sticky=tk.W, padx=4)
        modes = [
            ("Camera/Screenshots/Date (Smart)", "source-date"),
            ("Date Only (YYYY/MM)", "date-only"),
            ("Trips & Vacations (GPS to Cities)", "trips"),
            ("Source Category Only", "source-only")
        ]
        for col_idx, (text, val) in enumerate(modes):
            tk.Radiobutton(
                opts_card, text=text, value=val, variable=self.mode_var,
                bg=self.card_bg, fg=self.text_color, selectcolor="#0f172a",
                activebackground=self.card_bg, activeforeground=self.accent_cyan, font=("Segoe UI", 9)
            ).grid(row=0, column=col_idx + 1, padx=5, sticky=tk.W)

        # Checkboxes & Action Toggle
        chk_frame = tk.Frame(opts_card, bg=self.card_bg)
        chk_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(4, 0))

        tk.Checkbutton(
            chk_frame, text="Exact Duplicates", variable=self.dedup_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#0f172a", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=4)

        tk.Checkbutton(
            chk_frame, text="Visual Similarities (pHash)", variable=self.similar_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#0f172a", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=4)

        tk.Checkbutton(
            chk_frame, text="Offline GPS Geocoding", variable=self.geo_var,
            bg=self.card_bg, fg=self.text_color, selectcolor="#0f172a", font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(chk_frame, text="│  Action:", font=("Segoe UI", 9, "bold"), fg=self.warning_color, bg=self.card_bg).pack(side=tk.LEFT, padx=(10, 4))
        
        # Action selector with live clarity
        tk.Radiobutton(
            chk_frame, text="🛡️ Safe Copy (Originals Untouched)", value="copy", variable=self.action_var,
            bg=self.card_bg, fg="#4ade80", selectcolor="#0f172a", font=("Segoe UI", 9, "bold"),
            command=self._update_action_banner
        ).pack(side=tk.LEFT, padx=3)

        tk.Radiobutton(
            chk_frame, text="⚡ Fast Move (Clean Up Folder)", value="move", variable=self.action_var,
            bg=self.card_bg, fg="#f87171", selectcolor="#0f172a", font=("Segoe UI", 9, "bold"),
            command=self._update_action_banner
        ).pack(side=tk.LEFT, padx=3)

        # 4. ACTION CLARITY BANNER (EXPLAINS EXACTLY COPY VS MOVE)
        self.action_info_frame = tk.Frame(self.root, bg="#1e293b", padx=12, pady=4, relief="flat")
        self.action_info_frame.pack(fill=tk.X, padx=20, pady=(3, 2))

        self.lbl_action_banner = tk.Label(
            self.action_info_frame,
            text="🛡️ MODE: SAFE COPY — Originals stay 100% UNTOUCHED in your source folder. Organized copies are created in Destination.",
            font=("Segoe UI", 9, "bold"),
            fg="#4ade80",
            bg="#1e293b"
        )
        self.lbl_action_banner.pack(anchor=tk.W)

        # 5. ACTION BUTTONS TOOLBAR
        action_toolbar = tk.Frame(self.root, bg=self.bg_color)
        action_toolbar.pack(fill=tk.X, padx=20, pady=(4, 4))

        self.btn_preview = tk.Button(
            action_toolbar, text="🔍  1. RUN DRY-RUN PREVIEW", font=("Segoe UI", 11, "bold"),
            bg=self.accent_cyan, fg="#000000", activebackground=self.accent_hover,
            relief="flat", padx=16, pady=6, cursor="hand2", command=self._on_preview
        )
        self.btn_preview.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_execute = tk.Button(
            action_toolbar, text="🚀  2. EXECUTE SORTING", font=("Segoe UI", 11, "bold"),
            bg=self.success_color, fg="#000000", activebackground="#16a34a",
            relief="flat", padx=16, pady=6, cursor="hand2", command=self._on_execute
        )
        self.btn_execute.pack(side=tk.LEFT, padx=10)

        self.btn_undo = tk.Button(
            action_toolbar, text="🔄  1-Click Undo", font=("Segoe UI", 10, "bold"),
            bg="#334155", fg="#f1f5f9", activebackground="#475569",
            relief="flat", padx=14, pady=6, cursor="hand2", command=self._on_undo
        )
        self.btn_undo.pack(side=tk.RIGHT)

        # 6. AESTHETIC VISUAL CONVEYOR & MOTION THEATER CARD
        motion_card = tk.Frame(self.root, bg=self.card_bg, padx=14, pady=8, relief="ridge", bd=1)
        motion_card.pack(fill=tk.X, padx=20, pady=3)

        # Conveyor HUD: Source File Card -> Animated Laser Arrow -> Target Folder Card
        conveyor_frame = tk.Frame(motion_card, bg=self.card_bg)
        conveyor_frame.pack(fill=tk.X, pady=(2, 6))

        # Source Box (Left)
        src_box = tk.Frame(conveyor_frame, bg="#0f172a", padx=10, pady=4, relief="solid", bd=1, highlightbackground="#38bdf8", highlightthickness=1)
        src_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(src_box, text="SOURCE MEDIA", font=("Segoe UI", 7, "bold"), fg="#38bdf8", bg="#0f172a").pack(anchor=tk.W)
        self.lbl_src_file = tk.Label(
            src_box, textvariable=self.curr_source_file, font=("Segoe UI", 10, "bold"),
            fg="#ffffff", bg="#0f172a", anchor=tk.W, no_wrap=True
        )
        self.lbl_src_file.pack(fill=tk.X)

        # Animated Motion Stream (Center)
        self.stream_frame = tk.Frame(conveyor_frame, bg=self.card_bg, padx=15)
        self.stream_frame.pack(side=tk.LEFT)

        self.lbl_motion_arrow = tk.Label(
            self.stream_frame,
            text="──► 🚀 ──►",
            font=("Consolas", 14, "bold"),
            fg="#facc15",
            bg=self.card_bg
        )
        self.lbl_motion_arrow.pack()

        # Destination Box (Right)
        dest_box = tk.Frame(conveyor_frame, bg="#0f172a", padx=10, pady=4, relief="solid", bd=1, highlightbackground="#22c55e", highlightthickness=1)
        dest_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(dest_box, text="TARGET DESTINATION FOLDER", font=("Segoe UI", 7, "bold"), fg="#22c55e", bg="#0f172a").pack(anchor=tk.W)
        self.lbl_dest_folder = tk.Label(
            dest_box, textvariable=self.curr_target_folder, font=("Segoe UI", 10, "bold"),
            fg="#4ade80", bg="#0f172a", anchor=tk.W
        )
        self.lbl_dest_folder.pack(fill=tk.X)

        # Progress Bar & Live Speedometer
        progress_info_frame = tk.Frame(motion_card, bg=self.card_bg)
        progress_info_frame.pack(fill=tk.X, pady=(2, 2))

        tk.Label(progress_info_frame, textvariable=self.progress_text_var, font=("Segoe UI", 9, "bold"), fg=self.accent_cyan, bg=self.card_bg).pack(side=tk.LEFT)
        tk.Label(progress_info_frame, textvariable=self.speed_text_var, font=("Segoe UI", 9, "bold"), fg=self.warning_color, bg=self.card_bg).pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(
            motion_card, orient=tk.HORIZONTAL, mode="determinate",
            variable=self.progress_pct_var, style="Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill=tk.X, pady=(2, 4))

        # Ticking Category Badges
        badge_frame = tk.Frame(motion_card, bg=self.card_bg)
        badge_frame.pack(fill=tk.X, pady=(2, 2))

        def create_badge(parent, textvar, color):
            b = tk.Label(
                parent, textvariable=textvar, font=("Segoe UI", 9, "bold"),
                bg=self.badge_bg, fg=color, padx=10, pady=2, relief="flat"
            )
            b.pack(side=tk.LEFT, padx=3)
            return b

        create_badge(badge_frame, self.count_screenshots, "#38bdf8")
        create_badge(badge_frame, self.count_whatsapp, "#4ade80")
        create_badge(badge_frame, self.count_camera, "#f472b6")
        create_badge(badge_frame, self.count_videos, "#a78bfa")
        create_badge(badge_frame, self.count_dups, "#fbbf24")

        # 7. Bottom Status Bar (Packed Bottom First so it Never Disappears)
        bottom_frame = tk.Frame(self.root, bg=self.bg_color, padx=4, pady=2)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(2, 4))

        tk.Label(
            bottom_frame, textvariable=self.status_var,
            font=("Segoe UI", 9, "italic"), fg=self.accent_cyan, bg=self.bg_color
        ).pack(side=tk.LEFT)

        # 8. Interactive Preview Table
        table_frame = tk.Frame(self.root, bg=self.bg_color)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=2)

        columns = ("file", "category", "date", "target", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("file", text="Original File Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("date", text="Capture Date")
        self.tree.heading("target", text="Target Destination Folder")
        self.tree.heading("note", text="Sorting Status")

        self.tree.column("file", width=220, anchor=tk.W)
        self.tree.column("category", width=130, anchor=tk.CENTER)
        self.tree.column("date", width=110, anchor=tk.CENTER)
        self.tree.column("target", width=360, anchor=tk.W)
        self.tree.column("note", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Start background arrow pulse animation loop
        self._animate_conveyor_pulse()

    def _update_action_banner(self):
        """Update clarity banner when radio button toggles."""
        if self.action_var.get() == "copy":
            self.lbl_action_banner.config(
                text="🛡️ MODE: SAFE COPY — Originals stay 100% UNTOUCHED in source folder. Clean organized copies are created.",
                fg="#4ade80"
            )
        else:
            self.lbl_action_banner.config(
                text="⚡ MODE: FAST MOVE — Files are RELOCATED from source to Destination. Cleans up messy folder and saves space.",
                fg="#f87171"
            )

    def _animate_conveyor_pulse(self):
        """Infinite pulse loop for arrow when active."""
        if self.is_animating:
            self.arrow_animation_phase = (self.arrow_animation_phase + 1) % len(self.arrow_symbols)
            symbol = self.arrow_symbols[self.arrow_animation_phase]
            action_icon = "📋" if self.action_var.get() == "copy" else "✈️"
            self.lbl_motion_arrow.config(text=f"{symbol} {action_icon} {symbol}")
        self.root.after(150, self._animate_conveyor_pulse)

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

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_item_map.clear()

        self.btn_preview.configure(state=tk.DISABLED, text="⏳ Analyzing Live...")
        self.progress_pct_var.set(0.0)
        self.is_animating = True
        self.status_var.set("Scanning media files in parallel...")

        # Reset counters
        self.count_screenshots.set("📱 Screenshots: 0")
        self.count_whatsapp.set("💬 WhatsApp: 0")
        self.count_camera.set("📷 Camera: 0")
        self.count_videos.set("🎥 Videos: 0")
        self.count_dups.set("⚠️ Duplicates: 0")

        start_time = time.time()

        def on_progress(data: dict):
            self.root.after(0, lambda: self._handle_progress_update(data, start_time))

        def worker():
            sorter = GallerySorter(config)
            report = sorter.plan(progress_callback=on_progress)
            self.root.after(0, lambda: self._on_preview_complete(report))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_progress_update(self, data: dict, start_time: float):
        current = data.get("current", 0)
        total = max(1, data.get("total", 1))
        pct = (current / total) * 100.0
        self.progress_pct_var.set(pct)
        self.progress_text_var.set(f"{current:,} / {total:,} files ({pct:.1f}%)")

        elapsed = max(0.01, time.time() - start_time)
        rate = current / elapsed
        self.speed_text_var.set(f"⚡ {rate:.0f} files/s")

        filename = data.get("file", "")
        target = data.get("target", "")

        # Dynamic Conveyor Animation
        if filename:
            self.curr_source_file.set(filename)
            self.curr_target_folder.set(f"📁 {target}")
            self.status_var.set(f"Analyzing: {filename} ──► {target}")

        # Live Badges
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
            note = f"⚠️ Dup ({op.duplicate_type})" if op.is_duplicate else "⏳ Pending"
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
            self.tree_item_map[op.source_path.name] = item
            self.tree.see(item)

    def _on_preview_complete(self, report: SortReport):
        self.btn_preview.configure(state=tk.NORMAL, text="🔍  1. RUN DRY-RUN PREVIEW")
        self.current_report = report
        self.progress_pct_var.set(100.0)
        self.is_animating = False

        cats = report.category_counts
        self.count_screenshots.set(f"📱 Screenshots: {cats.get('Screenshots', 0)}")
        self.count_whatsapp.set(f"💬 WhatsApp: {cats.get('WhatsApp & Social', 0)}")
        self.count_camera.set(f"📷 Camera: {cats.get('Camera Originals', 0)}")
        self.count_videos.set(f"🎥 Videos: {cats.get('Videos', 0)}")
        dup_total = report.exact_duplicates_count + report.similar_duplicates_count
        self.count_dups.set(f"⚠️ Duplicates: {dup_total}")

        self.curr_source_file.set("✨ All media analyzed!")
        self.curr_target_folder.set(f"Ready in: {report.total_scanned:,} files")
        self.progress_text_var.set(f"Complete: {report.total_scanned:,} / {report.total_scanned:,} (100%)")
        self.status_var.set(f"Dry-run scan complete in {report.duration_seconds:.2f}s! Click '🚀 2. EXECUTE SORTING' to organize.")

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

        action_title = "SAFE COPY" if action == "copy" else "FAST MOVE"
        action_detail = (
            "• Originals stay 100% UNTOUCHED in source folder.\n• New clean copies will be created in Organized_Gallery."
            if action == "copy" else
            "• Files will be MOVED from source to Organized_Gallery.\n• Source folder will be cleaned up and disk space freed."
        )

        confirm_msg = (
            f"Ready to execute sorting with {action_title}?\n\n"
            f"{action_detail}\n\n"
            f"• Total Files: {len(self.current_report.planned_operations):,}\n"
            f"• Destination: {config.dest_dir}\n\n"
            f"A 1-click Undo manifest will be generated automatically for rollback."
        )
        if not messagebox.askyesno("Confirm Organization", confirm_msg):
            return

        self.btn_execute.configure(state=tk.DISABLED, text="🚀 Sorting Live...")
        self.progress_pct_var.set(0.0)
        self.is_animating = True

        start_time = time.time()

        def on_sort_progress(data: dict):
            self.root.after(0, lambda: self._handle_sort_progress(data, action, start_time))

        def worker():
            sorter = GallerySorter(config)
            rep = sorter.execute(self.current_report, progress_callback=on_sort_progress)
            self.root.after(0, lambda: self._on_execute_complete(rep))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_sort_progress(self, data: dict, action: str, start_time: float):
        current = data.get("current", 0)
        total = max(1, data.get("total", 1))
        pct = (current / total) * 100.0
        self.progress_pct_var.set(pct)
        self.progress_text_var.set(f"{current:,} / {total:,} ({pct:.1f}%)")

        elapsed = max(0.01, time.time() - start_time)
        rate = current / elapsed
        self.speed_text_var.set(f"⚡ {rate:.0f} files/s")

        filename = data.get("file", "")
        target = data.get("target", "")
        if filename:
            self.curr_source_file.set(f"{filename}")
            action_tag = "COPIED" if action == "copy" else "MOVED"
            self.curr_target_folder.set(f"[{action_tag}] ──► 📁 {target}")
            self.status_var.set(f"Processing ({action_tag}): {filename} ──► {target}")

            # Animate checkoff in the Treeview row
            if filename in self.tree_item_map:
                item_id = self.tree_item_map[filename]
                old_vals = list(self.tree.item(item_id, "values"))
                if old_vals:
                    old_vals[4] = f"✅ {action_tag}"
                    self.tree.item(item_id, values=old_vals)
                    self.tree.see(item_id)

    def _on_execute_complete(self, report: SortReport):
        self.btn_execute.configure(state=tk.NORMAL, text="🚀  2. EXECUTE SORTING")
        self.progress_pct_var.set(100.0)
        self.manifest_path = report.manifest_path
        self.is_animating = False

        action_name = "COPIED" if self.action_var.get() == "copy" else "MOVED"
        self.curr_source_file.set("🎉 All files sorted!")
        self.curr_target_folder.set(f"Organized: {report.total_scanned:,} files")
        self.status_var.set(f"✅ Sorting complete! Files successfully {action_name.lower()}.")

        msg = (
            f"🎉 Organization Successfully Completed!\n\n"
            f"• Action: {action_name}\n"
            f"• Total Files: {report.total_scanned:,}\n"
            f"• Manifest: {report.manifest_path.name}\n\n"
            f"You can undo this operation anytime using the '1-Click Undo' button."
        )
        messagebox.showinfo("Sorting Complete", msg)

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
