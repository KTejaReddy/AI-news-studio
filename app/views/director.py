"""AI Director View for AI News Studio.

Provides an interactive studio to analyze narration scripts, segment scenes,
view timelines, edit scene storyboard cards, and import/export plans as JSON.
"""

import json
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING, Dict, List, Optional

import customtkinter as ctk

from app.theme import Theme
from core.director.director_job import DirectorJob
from core.director.scene_plan import ScenePlan
from core.director.scene_timeline import SceneTimeline
from core.director.timeline_exporter import TimelineExporter

if TYPE_CHECKING:
    from app.gui import MainWindow


class DirectorView(ctk.CTkFrame):
    """View managing script analysis inputs, scene timelines, and storyboard parameter forms."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize DirectorView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_timeline = SceneTimeline()
        self._active_job: Optional[DirectorJob] = None
        self._monitor_active = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Main scrollable card view expands

        self._create_header()
        self._create_content()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(
            header_f,
            text="AI Director Storyboard Planner",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # Hardware display indicator
        device = "AI Orchestration Active"
        ctk.CTkLabel(
            header_f,
            text=f" ({device})",
            font=Theme.get_font(12, "italic"),
            text_color=Theme.SUCCESS
        ).pack(side="left", padx=5, pady=(8, 0))

    def _create_content(self) -> None:
        """Construct the configuration panels and editor workflow grids."""
        content_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content_scroll.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        content_scroll.columnconfigure(0, weight=1)

        # --- Section 1: Script Editor & Controls ---
        script_card = ctk.CTkFrame(
            content_scroll,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        script_card.pack(fill="x", pady=(0, 15), ipady=10)

        ctk.CTkLabel(
            script_card,
            text="Input Broadcast Narration Script:",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 5))

        self.script_text = ctk.CTkTextbox(
            script_card,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 2,
            height=110
        )
        self.script_text.pack(fill="x", padx=15, pady=(0, 12))
        self.script_text.insert(
            "1.0",
            "Welcome to AI News Studio! Today we are introducing our new automated production workflow. "
            "A standard speech segment like this estimated in real-time runs about five to ten seconds. "
            "For example, let's explore statistics: 85% of content creators prefer visual scripts. "
            "Remember, a wise engineer once said: 'Automated video planning is the key to scaling storytelling.' "
            "Subscribe to our channel for more exciting updates and check the link below to get started today!"
        )

        # Control Row
        ctrl_f = ctk.CTkFrame(script_card, fg_color="transparent")
        ctrl_f.pack(fill="x", padx=15, pady=5)

        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            ctrl_f,
            text="🧠 Analyze Script",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            command=self._on_analyze_clicked
        )
        self.analyze_btn.pack(side="left", padx=(0, 10))

        # Import
        self.import_btn = ctk.CTkButton(
            ctrl_f,
            text="📁 Import Storyboard",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            command=self._on_import_clicked
        )
        self.import_btn.pack(side="left", padx=5)

        # Export
        self.export_btn = ctk.CTkButton(
            ctrl_f,
            text="💾 Export Storyboard",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            state="disabled",
            command=self._on_export_clicked
        )
        self.export_btn.pack(side="left", padx=5)

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(
            script_card,
            progress_color=Theme.ACCENT,
            height=6
        )
        self.prog_bar.pack(fill="x", padx=15, pady=(10, 0))
        self.prog_bar.set(0.0)

        # --- Section 2: Summary Stats Banner ---
        self.stats_card = ctk.CTkFrame(
            content_scroll,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        self.stats_card.pack(fill="x", pady=(0, 15), ipady=5)

        self.stats_lbl = ctk.CTkLabel(
            self.stats_card,
            text="Estimated Video Length: 0.0s  |  Total Storyboard Scenes: 0",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.stats_lbl.pack(pady=10)

        # --- Section 3: Timeline Visualizer ---
        self.timeline_card = ctk.CTkFrame(
            content_scroll,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.timeline_card.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            self.timeline_card,
            text="Timeline Pace Visualization",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.timeline_canvas = ctk.CTkCanvas(
            self.timeline_card,
            bg=Theme.BG_MAIN[1],
            highlightthickness=0,
            height=40
        )
        self.timeline_canvas.pack(fill="x", padx=15, pady=(0, 15))

        # --- Section 4: Scrollable Scene Cards Editor ---
        self.editor_title_lbl = ctk.CTkLabel(
            content_scroll,
            text="Storyboard Scene Timeline Editor:",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        self.editor_title_lbl.pack(anchor="w", pady=(5, 5))

        self.scenes_container = ctk.CTkFrame(content_scroll, fg_color="transparent")
        self.scenes_container.pack(fill="x")

        # Bottom action triggers: Add scene
        self.add_scene_btn = ctk.CTkButton(
            content_scroll,
            text="➕ Append Storyboard Scene",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            command=self._on_add_scene_clicked
        )
        self.add_scene_btn.pack(pady=10)

    def on_show(self) -> None:
        """Triggered automatically when pageFocused."""
        self._refresh_timeline_views()

    def _on_analyze_clicked(self) -> None:
        """Submits script narration to DirectorController."""
        if self._active_job and self._active_job.status in ["pending", "running"]:
            self.main_window.show_error("Execution Active", "A script analysis job is already running.")
            return

        script = self.script_text.get("1.0", tk.END).strip()
        if not script:
            self.main_window.show_error("Validation Error", "Narration text field cannot be empty.")
            return

        self.analyze_btn.configure(state="disabled", text="Analyzing...")
        self._write_status("Running NLP sentence pacing analysis...")

        engine = getattr(self.main_window, "director_engine", None)
        if not engine:
            self.main_window.show_error("Engine Error", "DirectorEngine is not registered.")
            self.analyze_btn.configure(state="normal", text="🧠 Analyze Script")
            return

        self._active_job = engine.generate_timeline(script_text=script)
        self._monitor_active = True
        self._poll_progress()

    def _poll_progress(self) -> None:
        """Track background scheduler task updates."""
        if not self._active_job or not self._monitor_active:
            return

        status = self._active_job.status
        progress = self._active_job.progress

        self.prog_bar.set(progress)

        if status == "running":
            msg = f"Parsing sentences and planning camera motions... ({int(progress * 100)}%)"
            self._write_status(msg)
            self.after(100, self._poll_progress)
        elif status == "completed":
            self.analyze_btn.configure(state="normal", text="🧠 Analyze Script")
            self._monitor_active = False
            self._active_timeline = self._active_job.output_timeline or SceneTimeline()
            self._write_status("Analysis complete.")
            self._refresh_timeline_views()
        elif status == "failed":
            self.analyze_btn.configure(state="normal", text="🧠 Analyze Script")
            self._monitor_active = False
            self._write_status("Analysis failed.")
            self.main_window.show_error("Planning Error", self._active_job.error_message or "Unknown parsing exception.")

    def _on_import_clicked(self) -> None:
        """Import timeline from JSON file dialog."""
        filepath = filedialog.askopenfilename(
            title="Import Storyboard JSON",
            filetypes=[("JSON Files", "*.json")]
        )
        if filepath:
            try:
                self._active_timeline = TimelineExporter.import_from_file(Path(filepath))
                self._write_status(f"Storyboard loaded: {Path(filepath).name}")
                self._refresh_timeline_views()
            except Exception as e:
                self._logger.error(f"Import failure: {e}")
                self.main_window.show_error("Import Error", f"Could not parse timeline file:\n{e}")

    def _on_export_clicked(self) -> None:
        """Export timeline to JSON file dialog."""
        if not self._active_timeline.scenes:
            self.main_window.show_error("Validation Error", "No scene plans available to export.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Export Storyboard JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        if filepath:
            try:
                TimelineExporter.export_to_file(self._active_timeline, Path(filepath))
                self._write_status(f"Storyboard exported: {Path(filepath).name}")
            except Exception as e:
                self._logger.error(f"Export failure: {e}")
                self.main_window.show_error("Export Error", f"Could not write timeline file:\n{e}")

    def _on_add_scene_clicked(self) -> None:
        """Append a fresh customizable scene block to timeline list."""
        num = len(self._active_timeline.scenes) + 1
        new_scene = ScenePlan(
            scene_number=num,
            scene_type="Main Point",
            duration=5.0,
            narration="New narration segment.",
            presenter_visibility="Presenter",
            broll_keywords="news, studio"
        )
        self._active_timeline.scenes.append(new_scene)
        self._refresh_timeline_views()

    def _on_delete_scene(self, idx: int) -> None:
        """Remove a scene from the active timeline."""
        if 0 <= idx < len(self._active_timeline.scenes):
            self._active_timeline.scenes.pop(idx)
            
            # Recalculate indices
            for i, scene in enumerate(self._active_timeline.scenes):
                scene.scene_number = i + 1
                
            self._refresh_timeline_views()

    def _refresh_timeline_views(self) -> None:
        """Recalculate runtime sums, redraw horizontal pace visualization bars, and rebuild editable cards list."""
        # 1. Update stats text banner
        duration = self._active_timeline.total_duration
        count = len(self._active_timeline.scenes)
        
        mins = int(duration // 60)
        secs = int(duration % 60)
        self.stats_lbl.configure(
            text=f"Estimated Video Length: {mins}m {secs}s ({round(duration, 1)}s)  |  Total Storyboard Scenes: {count}"
        )

        if count > 0:
            self.export_btn.configure(state="normal")
        else:
            self.export_btn.configure(state="disabled")

        # 2. Redraw horizontal visualization timeline canvas
        self._draw_pace_timeline_canvas()

        # 3. Clear and draw editable scene cards scrollable items
        for widget in self.scenes_container.winfo_children():
            widget.destroy()

        for idx, scene in enumerate(self._active_timeline.scenes):
            card = ctk.CTkFrame(
                self.scenes_container,
                fg_color=Theme.BG_CARD,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            card.pack(fill="x", pady=4, ipady=5)

            # Row 0: Header & Action Row
            hdr_f = ctk.CTkFrame(card, fg_color="transparent")
            hdr_f.pack(fill="x", padx=15, pady=(10, 5))

            ctk.CTkLabel(
                hdr_f,
                text=f"🎬 SCENE {scene.scene_number}",
                font=Theme.get_font(12, "bold"),
                text_color=Theme.ACCENT
            ).pack(side="left")

            ctk.CTkButton(
                hdr_f,
                text="🗑️ Delete",
                font=Theme.get_font(10, "bold"),
                width=65,
                height=22,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda i=idx: self._on_delete_scene(i)
            ).pack(side="right")

            # Row 1: Core Content Forms Grid (Narration & Keywords)
            form_f = ctk.CTkFrame(card, fg_color="transparent")
            form_f.pack(fill="x", padx=15, pady=5)
            form_f.columnconfigure(0, weight=2)
            form_f.columnconfigure(1, weight=1)

            # Narration
            narr_f = ctk.CTkFrame(form_f, fg_color="transparent")
            narr_f.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            ctk.CTkLabel(
                narr_f,
                text="Narration voice-over segment:",
                font=Theme.get_font(10, "bold"),
                text_color=Theme.TEXT_SECONDARY
            ).pack(anchor="w", pady=(0, 2))

            narr_entry = ctk.CTkEntry(
                narr_f,
                font=Theme.get_font(11),
                fg_color=Theme.BG_MAIN,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR,
                corner_radius=Theme.CORNER_RADIUS - 4,
                height=28
            )
            narr_entry.pack(fill="x")
            narr_entry.insert(0, scene.narration)
            
            # Bind live typing modifications
            narr_entry.bind(
                "<KeyRelease>",
                lambda event, s=scene, entry=narr_entry: self._update_narration(s, entry.get())
            )

            # Keywords B-roll
            key_f = ctk.CTkFrame(form_f, fg_color="transparent")
            key_f.grid(row=0, column=1, sticky="nsew")
            ctk.CTkLabel(
                key_f,
                text="B-roll keywords (comma separated):",
                font=Theme.get_font(10, "bold"),
                text_color=Theme.TEXT_SECONDARY
            ).pack(anchor="w", pady=(0, 2))

            key_entry = ctk.CTkEntry(
                key_f,
                font=Theme.get_font(11),
                fg_color=Theme.BG_MAIN,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR,
                corner_radius=Theme.CORNER_RADIUS - 4,
                height=28
            )
            key_entry.pack(fill="x")
            key_entry.insert(0, scene.broll_keywords)
            
            # Bind typing
            key_entry.bind(
                "<KeyRelease>",
                lambda event, s=scene, entry=key_entry: self._update_keywords(s, entry.get())
            )

            # Row 2: Secondary forms option menus
            opts_f = ctk.CTkFrame(card, fg_color="transparent")
            opts_f.pack(fill="x", padx=15, pady=5)

            # Segmented columns layout
            # 1. Type
            type_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            type_f.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(type_f, text="Scene Type:", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            type_opt = ctk.CTkOptionMenu(
                type_f,
                values=["Hook", "Introduction", "Main Point", "Example", "Statistic", "Quote", "CTA", "Ending"],
                font=Theme.get_font(10),
                dropdown_font=Theme.get_font(10),
                width=90,
                height=24,
                command=lambda val, s=scene: self._update_scene_type(s, val)
            )
            type_opt.pack()
            type_opt.set(scene.scene_type)

            # 2. Duration
            dur_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            dur_f.pack(side="left", padx=10)
            ctk.CTkLabel(dur_f, text="Duration (s):", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            dur_entry = ctk.CTkEntry(dur_f, font=Theme.get_font(10), width=50, height=24)
            dur_entry.pack()
            dur_entry.insert(0, str(scene.duration))
            dur_entry.bind(
                "<KeyRelease>",
                lambda event, s=scene, entry=dur_entry: self._update_duration(s, entry.get())
            )

            # 3. Presenter visibility
            vis_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            vis_f.pack(side="left", padx=10)
            ctk.CTkLabel(vis_f, text="Visibility:", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            vis_opt = ctk.CTkOptionMenu(
                vis_f,
                values=["Presenter", "B-roll", "Mixed"],
                font=Theme.get_font(10),
                dropdown_font=Theme.get_font(10),
                width=85,
                height=24,
                command=lambda val, s=scene: setattr(s, "presenter_visibility", val)
            )
            vis_opt.pack()
            vis_opt.set(scene.presenter_visibility)

            # 4. Camera Shot
            shot_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            shot_f.pack(side="left", padx=10)
            ctk.CTkLabel(shot_f, text="Camera Shot:", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            shot_opt = ctk.CTkOptionMenu(
                shot_f,
                values=["Close-up", "Medium Shot", "Wide Shot"],
                font=Theme.get_font(10),
                dropdown_font=Theme.get_font(10),
                width=90,
                height=24,
                command=lambda val, s=scene: setattr(s, "camera_shot", val)
            )
            shot_opt.pack()
            shot_opt.set(scene.camera_shot)

            # 5. Camera Movement
            mov_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            mov_f.pack(side="left", padx=10)
            ctk.CTkLabel(mov_f, text="Movement:", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            mov_opt = ctk.CTkOptionMenu(
                mov_f,
                values=["Static", "Pan Left", "Pan Right", "Tilt Up", "Zoom In", "Zoom Out"],
                font=Theme.get_font(10),
                dropdown_font=Theme.get_font(10),
                width=95,
                height=24,
                command=lambda val, s=scene: setattr(s, "camera_movement", val)
            )
            mov_opt.pack()
            mov_opt.set(scene.camera_movement)

            # 6. Emotion
            em_f = ctk.CTkFrame(opts_f, fg_color="transparent")
            em_f.pack(side="left", padx=10)
            ctk.CTkLabel(em_f, text="Emotion:", font=Theme.get_font(9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
            em_opt = ctk.CTkOptionMenu(
                em_f,
                values=["Neutral", "Excited", "Serious", "Warm", "Happy"],
                font=Theme.get_font(10),
                dropdown_font=Theme.get_font(10),
                width=80,
                height=24,
                command=lambda val, s=scene: setattr(s, "emotion", val)
            )
            em_opt.pack()
            em_opt.set(scene.emotion)

    # --- Live Form Bindings Updates ---
    def _update_narration(self, scene: ScenePlan, text: str) -> None:
        """Sync narration strings directly."""
        scene.narration = text

    def _update_keywords(self, scene: ScenePlan, text: str) -> None:
        """Sync keywords details."""
        scene.broll_keywords = text

    def _update_scene_type(self, scene: ScenePlan, val: str) -> None:
        """Update type category and redraw canvas color block grids."""
        scene.scene_type = val
        self._draw_pace_timeline_canvas()

    def _update_duration(self, scene: ScenePlan, text: str) -> None:
        """Verify float typing entry and trigger runtime summation banner redraws."""
        try:
            val = float(text.strip())
            if val > 0:
                scene.duration = val
                
                # Recalculate duration text
                duration = self._active_timeline.total_duration
                mins = int(duration // 60)
                secs = int(duration % 60)
                self.stats_lbl.configure(
                    text=f"Estimated Video Length: {mins}m {secs}s ({round(duration, 1)}s)  |  Total Storyboard Scenes: {len(self._active_timeline.scenes)}"
                )
                self._draw_pace_timeline_canvas()
        except ValueError:
            pass  # Ignore invalid numbers during active typing

    def _draw_pace_timeline_canvas(self) -> None:
        """Calculate durations proportions and paint sequential color grids on canvas."""
        self.timeline_canvas.delete("all")
        
        scenes = self._active_timeline.scenes
        total = self._active_timeline.total_duration

        if total <= 0 or not scenes:
            return

        # Width calculation bounds
        self.update_idletasks()
        width = self.timeline_canvas.winfo_width()
        if width <= 1:
            width = 500  # Fallback size

        height = 40
        current_x = 0

        # Colors mapping per type category
        colors_map = {
            "Hook": "#6366f1",         # indigo
            "Introduction": "#3b82f6", # blue
            "Statistic": "#ef4444",    # red
            "Example": "#eab308",      # yellow
            "Quote": "#a855f7",        # purple
            "CTA": "#22c55e",          # green
            "Ending": "#f97316",       # orange
            "Main Point": "#71717a"    # zinc gray
        }

        for scene in scenes:
            # Fraction width
            fract = scene.duration / total
            w = int(fract * width)
            w = max(5, w) # minimum bar width

            bg_col = colors_map.get(scene.scene_type, "#71717a")

            # Draw block rectangle
            self.timeline_canvas.create_rectangle(
                current_x, 0, current_x + w, height,
                fill=bg_col, outline="#27272a", width=1
            )

            # Write text index label centered if width allows
            if w > 18:
                self.timeline_canvas.create_text(
                    current_x + w // 2, height // 2,
                    text=str(scene.scene_number),
                    fill="#ffffff", font=Theme.get_font(10, "bold")
                )

            current_x += w

    def _write_status(self, text: str) -> None:
        """Update information text displays."""
        self.main_window.update_status(f"AI Director: {text}")
