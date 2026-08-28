"""Editor View for AI News Studio.

Provides a professional multi-track project timeline editor, preview monitor canvas,
playback loops (Play, Pause, Stop, Loop, frame step buttons), track lock/mute/solo controls,
zoom adjustments, cache monitors, and asynchronous render triggers.
"""

import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import time
import math
from typing import TYPE_CHECKING, List, Optional, Dict

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk

from app.theme import Theme
from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene
from core.timeline.timeline_job import TimelineRenderJob

if TYPE_CHECKING:
    from app.gui import MainWindow


class EditorView(ctk.CTkFrame):
    """Rich multi-track editing workspace viewport."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize EditorView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self.selected_clip: Optional[TimelineClip] = None
        self.selected_track_type: Optional[str] = None
        
        # Timeline visual parameters
        self.zoom_factor = 30.0  # pixels per second
        self.track_height = 34
        self.track_spacing = 6
        self.ruler_height = 25
        self.track_header_width = 140

        # State tracking for animation ticks
        self._play_loop_active = False

        # Grid configuration: 3 rows: Header, Monitor/Sidebars, Timeline canvas
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=3) # Monitor / parameters
        self.grid_rowconfigure(2, weight=2) # Multi-track canvas grid

        self._create_header()
        self._create_top_panels()
        self._create_bottom_timeline()

        # Start playback animation loop
        self._start_playback_poller()

    def _create_header(self) -> None:
        """Create title bar."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        ctk.CTkLabel(
            header_f,
            text="Cinematic Multi-Track Video Editor",
            font=Theme.get_font(22, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # Project status
        self.lbl_active_proj = ctk.CTkLabel(
            header_f,
            text="Active Project: None",
            font=Theme.get_font(11, "italic"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.lbl_active_proj.pack(side="right", padx=10)

    def _create_top_panels(self) -> None:
        """Construct Preview Monitor, Scene Storyboard snapping lists, and History panel."""
        top_grid = ctk.CTkFrame(self, fg_color="transparent")
        top_grid.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        top_grid.grid_columnconfigure(0, weight=1, minsize=260)  # Left panel: Scenes/History
        top_grid.grid_columnconfigure(1, weight=3, minsize=460)  # Center: Preview Monitor
        top_grid.grid_columnconfigure(2, weight=1, minsize=260)  # Right: Parameters
        top_grid.grid_rowconfigure(0, weight=1)

        # 1. Left Panel (Storyboard Scenes Snapper & History Actions)
        left_panel = ctk.CTkFrame(
            top_grid,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        left_panel.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=3) # Scenes
        left_panel.rowconfigure(3, weight=2) # History

        ctk.CTkLabel(left_panel, text="🎬 Scene Snapper Index", font=Theme.get_font(12, "bold")).grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        self.scenes_list_scroll = ctk.CTkScrollableFrame(left_panel, fg_color="transparent", height=120)
        self.scenes_list_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        ctk.CTkLabel(left_panel, text="📝 Edit Actions History", font=Theme.get_font(12, "bold")).grid(row=2, column=0, padx=10, pady=(5, 2), sticky="w")
        self.history_list_scroll = ctk.CTkScrollableFrame(left_panel, fg_color="transparent", height=80)
        self.history_list_scroll.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # 2. Center Panel (Preview Monitor screen)
        monitor_card = ctk.CTkFrame(
            top_grid,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        monitor_card.grid(row=0, column=1, padx=5, sticky="nsew")
        monitor_card.columnconfigure(0, weight=1)
        monitor_card.rowconfigure(1, weight=1) # preview expands

        # Title / Timecode header
        mon_hdr = ctk.CTkFrame(monitor_card, fg_color="transparent")
        mon_hdr.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        
        ctk.CTkLabel(mon_hdr, text="🖥️ Composite Preview Monitor", font=Theme.get_font(12, "bold")).pack(side="left")
        
        self.lbl_timecode = ctk.CTkLabel(mon_hdr, text="00:00:00:00", font=("Courier New", 13, "bold"), text_color=Theme.ACCENT[1])
        self.lbl_timecode.pack(side="right")

        # Canvas for composited video frame drawings
        self.preview_canvas = ctk.CTkCanvas(
            monitor_card,
            bg=Theme.BG_MAIN[1],
            highlightthickness=0
        )
        self.preview_canvas.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")
        self.preview_canvas_image_id = None

        # Playback controls bar
        ctrl_bar = ctk.CTkFrame(monitor_card, fg_color="transparent")
        ctrl_bar.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        # Buttons
        ctk.CTkButton(ctrl_bar, text="🔄 Loop", font=Theme.get_font(10, "bold"), width=55, height=24, fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, command=self._toggle_loop).pack(side="left", padx=2)
        ctk.CTkButton(ctrl_bar, text="⏮️ Step L", font=Theme.get_font(10, "bold"), width=55, height=24, fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, command=self._on_prev_frame).pack(side="left", padx=2)
        self.btn_play = ctk.CTkButton(ctrl_bar, text="▶️ Play", font=Theme.get_font(11, "bold"), width=65, height=24, fg_color=Theme.SUCCESS, command=self._on_play_toggle)
        self.btn_play.pack(side="left", padx=2)
        ctk.CTkButton(ctrl_bar, text="⏹️ Stop", font=Theme.get_font(10, "bold"), width=55, height=24, fg_color=Theme.DANGER, command=self._on_stop).pack(side="left", padx=2)
        ctk.CTkButton(ctrl_bar, text="⏭️ Step R", font=Theme.get_font(10, "bold"), width=55, height=24, fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, command=self._on_next_frame).pack(side="left", padx=2)

        # Resolution dropdown selector
        self.preview_res_opt = ctk.CTkOptionMenu(
            ctrl_bar,
            values=["Low Res (Fast)", "Full Res (Accurate)"],
            font=Theme.get_font(9),
            width=110,
            height=24
        )
        self.preview_res_opt.pack(side="right", padx=2)

        # 3. Right Panel (Timeline parameter adjustments & Renderer export status)
        right_panel = ctk.CTkFrame(
            top_grid,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        right_panel.grid(row=0, column=2, padx=(5, 0), sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1) # settings scroll expands

        ctk.CTkLabel(right_panel, text="⚙️ Assembly Controls", font=Theme.get_font(12, "bold")).grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        
        self.settings_scroll = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.settings_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.settings_scroll.columnconfigure(0, weight=1)

        self._populate_settings_controls()

    def _populate_settings_controls(self) -> None:
        """Draw settings knobs, sliders, and background rendering tags inside the right panel."""
        for w in self.settings_scroll.winfo_children():
            w.destroy()

        # Selection info tag
        self.lbl_selection = ctk.CTkLabel(
            self.settings_scroll,
            text="No clip selected.\nClick a clip box on the tracks below to split, trim, or move it.",
            font=Theme.get_font(10),
            text_color=Theme.TEXT_MUTED,
            wraplength=200,
            justify="center"
        )
        self.lbl_selection.pack(pady=10)

        # Action Buttons
        self.edit_btn_f = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        self.edit_btn_f.pack(fill="x", pady=5)
        self.edit_btn_f.columnconfigure(0, weight=1)
        self.edit_btn_f.columnconfigure(1, weight=1)

        self.btn_split = ctk.CTkButton(self.edit_btn_f, text="✂️ Split Clip", font=Theme.get_font(10, "bold"), height=24, state="disabled", command=self._on_split_clicked)
        self.btn_split.grid(row=0, column=0, padx=2, sticky="ew")
        
        self.btn_delete = ctk.CTkButton(self.edit_btn_f, text="🗑️ Delete", font=Theme.get_font(10, "bold"), fg_color=Theme.DANGER, hover_color=Theme.DANGER, height=24, state="disabled", command=self._on_delete_clicked)
        self.btn_delete.grid(row=0, column=1, padx=2, sticky="ew")

        # Trim & Nudge control row
        self.nudge_f = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        self.nudge_f.pack(fill="x", pady=5)
        self.nudge_f.columnconfigure(0, weight=1)
        self.nudge_f.columnconfigure(1, weight=1)

        self.btn_trim_left = ctk.CTkButton(self.nudge_f, text="◀ Trim L", font=Theme.get_font(10, "bold"), height=24, state="disabled", command=lambda: self._on_trim_nudge("start", -0.5))
        self.btn_trim_left.grid(row=0, column=0, padx=2, sticky="ew")
        self.btn_trim_right = ctk.CTkButton(self.nudge_f, text="Trim R ▶", font=Theme.get_font(10, "bold"), height=24, state="disabled", command=lambda: self._on_trim_nudge("end", -0.5))
        self.btn_trim_right.grid(row=0, column=1, padx=2, sticky="ew")

        # Divider
        ctk.CTkFrame(self.settings_scroll, height=1, fg_color=Theme.BORDER_COLOR).pack(fill="x", pady=10)

        # Undo / Redo controls
        hist_f = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        hist_f.pack(fill="x", pady=2)
        hist_f.columnconfigure(0, weight=1)
        hist_f.columnconfigure(1, weight=1)
        
        self.btn_undo = ctk.CTkButton(hist_f, text="↩️ Undo Edit", font=Theme.get_font(10, "bold"), height=24, fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, command=self._on_undo_clicked)
        self.btn_undo.grid(row=0, column=0, padx=2, sticky="ew")
        self.btn_redo = ctk.CTkButton(hist_f, text="↪️ Redo Edit", font=Theme.get_font(10, "bold"), height=24, fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, command=self._on_redo_clicked)
        self.btn_redo.grid(row=0, column=1, padx=2, sticky="ew")

        # Cache viewer
        ctk.CTkFrame(self.settings_scroll, height=1, fg_color=Theme.BORDER_COLOR).pack(fill="x", pady=10)
        ctk.CTkLabel(self.settings_scroll, text="📦 Render Cache Manager", font=Theme.get_font(11, "bold"), text_color=Theme.TEXT_SECONDARY).pack(anchor="w")
        
        self.lbl_cache_size = ctk.CTkLabel(self.settings_scroll, text="Cache folder size: Calculating...", font=Theme.get_font(10), text_color=Theme.TEXT_MUTED)
        self.lbl_cache_size.pack(anchor="w", pady=2)

        ctk.CTkButton(self.settings_scroll, text="🧹 Clear Frames Cache", font=Theme.get_font(10, "bold"), fg_color=Theme.BG_MAIN, text_color=Theme.TEXT_PRIMARY, height=24, command=self._on_clear_cache).pack(fill="x", pady=4)

        # Background Renderer trigger
        ctk.CTkFrame(self.settings_scroll, height=1, fg_color=Theme.BORDER_COLOR).pack(fill="x", pady=10)
        ctk.CTkLabel(self.settings_scroll, text="🎞️ Render Composition Video", font=Theme.get_font(11, "bold"), text_color=Theme.TEXT_SECONDARY).pack(anchor="w")

        self.btn_render = ctk.CTkButton(
            self.settings_scroll,
            text="⚡ Render Video Project",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._on_render_project_clicked
        )
        self.btn_render.pack(fill="x", pady=6)

        # Render Progress Queue bar
        self.render_pbar = ctk.CTkProgressBar(self.settings_scroll, progress_color=Theme.ACCENT, height=6)
        self.render_pbar.pack(fill="x", pady=2)
        self.render_pbar.set(0.0)
        self.render_pbar.pack_forget() # Hide initially

        self.lbl_render_status = ctk.CTkLabel(self.settings_scroll, text="", font=Theme.get_font(10), text_color=Theme.TEXT_MUTED)
        self.lbl_render_status.pack(anchor="w")

        self._refresh_cache_size()

    def _create_bottom_timeline(self) -> None:
        """Construct the horizontal multi-track scrollable timeline grid canvas (row 2)."""
        self.timeline_panel = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.timeline_panel.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.timeline_panel.grid_columnconfigure(0, weight=1)
        self.timeline_panel.grid_rowconfigure(1, weight=1)

        # Zoom & time indicator row
        zoom_bar = ctk.CTkFrame(self.timeline_panel, fg_color="transparent", height=30)
        zoom_bar.grid(row=0, column=0, padx=10, pady=(5, 2), sticky="ew")
        
        ctk.CTkLabel(zoom_bar, text="🔍 Zoom Horizontal Scaling:", font=Theme.get_font(10, "bold"), text_color=Theme.TEXT_SECONDARY).pack(side="left")
        self.zoom_slider = ctk.CTkSlider(
            zoom_bar,
            from_=10.0,
            to=100.0,
            width=150,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            command=self._on_zoom_changed
        )
        self.zoom_slider.pack(side="left", padx=10)
        self.zoom_slider.set(self.zoom_factor)

        self.lbl_timeline_duration = ctk.CTkLabel(zoom_bar, text="Total Project Duration: 0.0s", font=Theme.get_font(10, "bold"), text_color=Theme.TEXT_SECONDARY)
        self.lbl_timeline_duration.pack(side="right", padx=10)

        # Main timeline workspace split layout:
        # Left sidebar: Track headers stacked vertically (mute/solo/lock controls)
        # Right area: Scrollable tracks timeline canvas drawing clips
        t_workspace = ctk.CTkFrame(self.timeline_panel, fg_color="transparent")
        t_workspace.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        t_workspace.columnconfigure(0, weight=0) # Headers
        t_workspace.columnconfigure(1, weight=1) # Scrollable tracks canvas
        t_workspace.rowconfigure(0, weight=1)

        # a. Left track headers container stack
        self.headers_frame = ctk.CTkFrame(t_workspace, fg_color="transparent", width=self.track_header_width)
        self.headers_frame.grid(row=0, column=0, sticky="ns", pady=(self.ruler_height, 0))
        self.headers_frame.grid_propagate(False)

        # b. Right Scrollable Canvas viewport
        self.timeline_scroll_x = ctk.CTkScrollbar(self.timeline_panel, orientation="horizontal")
        self.timeline_scroll_x.grid(row=2, column=0, sticky="ew", padx=10)

        self.timeline_canvas = ctk.CTkCanvas(
            t_workspace,
            bg=Theme.BG_MAIN[1],
            highlightthickness=0,
            xscrollcommand=self.timeline_scroll_x.set
        )
        self.timeline_canvas.grid(row=0, column=1, sticky="nsew")
        
        self.timeline_scroll_x.configure(command=self.timeline_canvas.xview)

        # Bind timeline events
        self.timeline_canvas.bind("<Button-1>", self._on_timeline_canvas_click)
        self.timeline_canvas.bind("<B1-Motion>", self._on_timeline_canvas_drag)

    def on_show(self) -> None:
        """Triggered automatically when view is swapped in."""
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            if self.main_window.current_project:
                self.lbl_active_proj.configure(text=f"Active Project: {self.main_window.current_project.name}")
                engine.load_project_timeline(self.main_window.current_project.id)
            else:
                self.lbl_active_proj.configure(text="Active Project: None (Load Standalone)")
                engine.controller._load_empty_timeline()

        self._refresh_scenes_snapper()
        self._refresh_history_actions()
        self._refresh_track_headers()
        self._redraw_timeline_canvas()
        self._draw_monitor_preview()

    def _refresh_scenes_snapper(self) -> None:
        """Draw storyboard scenes list row triggers."""
        for widget in self.scenes_list_scroll.winfo_children():
            widget.destroy()

        engine = getattr(self.main_window, "timeline_engine", None)
        scenes = engine.get_scenes() if engine else []

        if not scenes:
            ctk.CTkLabel(self.scenes_list_scroll, text="No storyboard scenes.", font=Theme.get_font(10), text_color=Theme.TEXT_MUTED).pack()
            return

        for scene in scenes:
            row = ctk.CTkFrame(self.scenes_list_scroll, fg_color=Theme.BG_MAIN, corner_radius=Theme.CORNER_RADIUS - 6)
            row.pack(fill="x", pady=2, ipady=1)
            row.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(
                row,
                text=f"Scene {scene.scene_number} ({scene.scene_type}) | {scene.duration:.1f}s",
                font=Theme.get_font(10, "bold"),
                anchor="w"
            )
            lbl.grid(row=0, column=0, padx=8, pady=2, sticky="w")

            btn_snap = ctk.CTkButton(
                row,
                text="Snap ➔",
                font=Theme.get_font(9, "bold"),
                width=55,
                height=18,
                fg_color=Theme.BG_CARD,
                text_color=Theme.TEXT_PRIMARY,
                hover_color=Theme.BG_CARD_HOVER,
                command=lambda s=scene: self._snap_playhead_to_scene(s)
            )
            btn_snap.grid(row=0, column=1, padx=5, pady=2)

    def _refresh_history_actions(self) -> None:
        """Re-draw undo/redo stack logs list."""
        for widget in self.history_list_scroll.winfo_children():
            widget.destroy()

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        undo_stack = engine.controller.history.undo_stack
        
        if not undo_stack:
            ctk.CTkLabel(self.history_list_scroll, text="No editing actions yet.", font=Theme.get_font(10), text_color=Theme.TEXT_MUTED).pack()
            return

        # List in reverse order (newest on top)
        for idx, snapshot in enumerate(reversed(undo_stack)):
            lbl = ctk.CTkLabel(
                self.history_list_scroll,
                text=f"Edit state snapshot #{len(undo_stack) - idx}",
                font=Theme.get_font(9),
                text_color=Theme.TEXT_SECONDARY,
                anchor="w"
            )
            lbl.pack(fill="x", padx=5, pady=1)

    def _refresh_track_headers(self) -> None:
        """Rebuild stacked track control labels."""
        for widget in self.headers_frame.winfo_children():
            widget.destroy()

        engine = getattr(self.main_window, "timeline_engine", None)
        tracks = engine.get_tracks() if engine else []

        for idx, track in enumerate(tracks):
            y_pos = idx * (self.track_height + self.track_spacing) + 2
            
            box = ctk.CTkFrame(
                self.headers_frame,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 6,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR,
                width=self.track_header_width,
                height=self.track_height
            )
            box.place(x=0, y=y_pos)
            box.grid_propagate(False)
            box.columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(
                box,
                text=track.name,
                font=Theme.get_font(10, "bold"),
                text_color=Theme.TEXT_PRIMARY
            )
            lbl.grid(row=0, column=0, columnspan=3, padx=5, pady=(2, 0), sticky="w")

            # Mute toggle button (M)
            m_col = Theme.ACCENT if track.muted else Theme.BG_CARD
            btn_m = ctk.CTkButton(
                box, text="M", font=Theme.get_font(8, "bold"), width=16, height=14,
                fg_color=m_col, text_color=Theme.TEXT_PRIMARY,
                command=lambda t=track.track_type: self._toggle_mute(t)
            )
            btn_m.grid(row=1, column=0, padx=2, pady=1)

            # Lock toggle button (L)
            l_col = Theme.ACCENT if track.locked else Theme.BG_CARD
            btn_l = ctk.CTkButton(
                box, text="L", font=Theme.get_font(8, "bold"), width=16, height=14,
                fg_color=l_col, text_color=Theme.TEXT_PRIMARY,
                command=lambda t=track.track_type: self._toggle_lock(t)
            )
            btn_l.grid(row=1, column=1, padx=2, pady=1)

            # Visibility toggle button (V)
            v_col = Theme.SUCCESS if track.visible else Theme.BG_CARD
            btn_v = ctk.CTkButton(
                box, text="V", font=Theme.get_font(8, "bold"), width=16, height=14,
                fg_color=v_col, text_color=Theme.TEXT_PRIMARY,
                command=lambda t=track.track_type: self._toggle_visible(t)
            )
            btn_v.grid(row=1, column=2, padx=2, pady=1)

    def _redraw_timeline_canvas(self) -> None:
        """Clear canvas and paint ruler divisions, visual track rows, clip blocks, and playhead line."""
        self.timeline_canvas.delete("all")

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        tracks = engine.get_tracks()
        scenes = engine.get_scenes()
        total_duration = engine.get_total_duration()

        # Canvas width bounds based on zoom
        canvas_width = int(max(total_duration + 5.0, 15.0) * self.zoom_factor)
        canvas_height = len(tracks) * (self.track_height + self.track_spacing) + self.ruler_height + 20
        
        # Configure scrollable region
        self.timeline_canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

        # 1. Paint Time Ruler (seconds tick markings)
        self.timeline_canvas.create_rectangle(0, 0, canvas_width, self.ruler_height, fill="#1c1917", outline="#27272a", width=1)
        
        sec_step = 1 if self.zoom_factor > 25 else (5 if self.zoom_factor > 8 else 10)
        for t in range(0, int(total_duration + 10), sec_step):
            x = int(t * self.zoom_factor)
            self.timeline_canvas.create_line(x, 15, x, self.ruler_height, fill="#71717a", width=1)
            self.timeline_canvas.create_text(x + 5, 8, text=f"{t}s", fill="#a1a1aa", font=Theme.get_font(8, "normal"))

        # 2. Paint track row backgrounds and clip boxes
        clip_colors = {
            "Presenter": "#3b82f6",     # Blue
            "Voice": "#8b5cf6",         # Purple
            "B-roll": "#f59e0b",        # Amber
            "Music": "#10b981",         # Emerald
            "Text": "#6366f1",          # Indigo
            "Camera": "#71717a"         # Zinc Gray
        }

        for idx, track in enumerate(tracks):
            y_pos = idx * (self.track_height + self.track_spacing) + self.ruler_height
            
            # Row track background lane line
            self.timeline_canvas.create_rectangle(
                0, y_pos + 1, canvas_width, y_pos + self.track_height - 1,
                fill="#18181c" if idx % 2 == 0 else "#1c1c20",
                outline="#27272a", width=1
            )

            # Paint clip boxes
            for clip in track.clips:
                cx1 = int(clip.start_time * self.zoom_factor)
                cx2 = int((clip.start_time + clip.duration) * self.zoom_factor)
                cy1 = y_pos + 3
                cy2 = y_pos + self.track_height - 3

                # Highlight clip if currently selected
                outline_color = "#ffffff" if self.selected_clip and self.selected_clip.clip_id == clip.clip_id else "#27272a"
                border_w = 2 if self.selected_clip and self.selected_clip.clip_id == clip.clip_id else 1
                bg_color = clip_colors.get(track.track_type, "#52525b")

                # Clip rounded box shape simulation
                clip_rect_id = self.timeline_canvas.create_rectangle(
                    cx1, cy1, cx2, cy2,
                    fill=bg_color,
                    outline=outline_color,
                    width=border_w
                )

                # Clip Text details inside box
                title_text = clip.name
                # Strip text if box is too small
                max_w = cx2 - cx1
                if max_w > 20:
                    truncated = title_text
                    if len(truncated) * 6 > max_w:
                        truncated = truncated[:int(max_w / 6) - 2] + ".."
                    
                    self.timeline_canvas.create_text(
                        cx1 + max_w // 2, cy1 + (cy2 - cy1) // 2,
                        text=truncated,
                        fill="#ffffff",
                        font=Theme.get_font(9, "bold")
                    )

                # Attach metadata tags to canvas item to bind events
                self.timeline_canvas.itemconfig(clip_rect_id, tags=("clip", clip.clip_id, track.track_type))

        # 3. Paint Playhead line
        playhead_x = int(engine.get_playback_time() * self.zoom_factor)
        self.timeline_canvas.create_line(
            playhead_x, 0, playhead_x, canvas_height,
            fill="#ef4444", width=2, tags="playhead"
        )
        # Playhead triangle banner on top ruler
        self.timeline_canvas.create_polygon(
            [playhead_x - 6, 0, playhead_x + 6, 0, playhead_x, 8],
            fill="#ef4444", tags="playhead"
        )

        self.lbl_timeline_duration.configure(text=f"Total Project Duration: {total_duration:.1f}s")

    def _draw_monitor_preview(self) -> None:
        """Compose frames at playhead time and render pixels onto Canvas."""
        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        t = engine.get_playback_time()
        
        # Calculate timecode text formats
        total_seconds = int(t)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        frames = int((t - total_seconds) * engine.controller.playback.fps)
        self.lbl_timecode.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}")

        # Render composite frame array
        low_res_preview = "Low Res" in self.preview_res_opt.get()
        
        # Determine canvas size
        self.update_idletasks()
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            cw, ch = 480, 270 # fallbacks

        frame_np = engine.controller.renderer.get_frame_at_time(
            t=t,
            tracks=engine.get_tracks(),
            scenes=engine.get_scenes(),
            aspect_ratio=self.main_window.current_project.aspect_ratio if self.main_window.current_project else "16:9",
            fps=engine.controller.playback.fps,
            low_res=low_res_preview
        )

        try:
            # Resize numpy array to fit canvas viewport
            img_pil = Image.fromarray(frame_np)
            img_pil = img_pil.resize((cw, ch), Image.NEAREST)
            
            # Draw on canvas
            self.tk_image = ImageTk.PhotoImage(image=img_pil)
            if self.preview_canvas_image_id is None:
                self.preview_canvas_image_id = self.preview_canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
            else:
                self.preview_canvas.itemconfig(self.preview_canvas_image_id, image=self.tk_image)
        except Exception as e:
            self._logger.debug(f"Failed drawing preview canvas frame: {e}")

    def _snap_playhead_to_scene(self, scene: TimelineScene) -> None:
        """Reposition timeline playback cursor start of selected scene."""
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.playback.set_time(scene.start_time, engine.get_total_duration())
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _toggle_mute(self, track_type: str) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.toggle_track_mute(track_type)
            self._refresh_track_headers()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _toggle_lock(self, track_type: str) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.toggle_track_lock(track_type)
            self._refresh_track_headers()

    def _toggle_visible(self, track_type: str) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.toggle_track_visibility(track_type)
            self._refresh_track_headers()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    # --- Timeline Canvas Clicks / Interactions ---

    def _on_timeline_canvas_click(self, event: tk.Event) -> None:
        """Handle clip selection clicks or timecode playhead scrubbing."""
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        # Check if clicked on a Clip box
        clicked_items = self.timeline_canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        clip_clicked = False
        
        for item in clicked_items:
            tags = self.timeline_canvas.gettags(item)
            if "clip" in tags:
                clip_id = tags[1]
                track_type = tags[2]
                
                # Retrieve clip details
                track = next((t for t in engine.get_tracks() if t.track_type == track_type), None)
                if track:
                    clip = track.get_clip(clip_id)
                    if clip:
                        self.selected_clip = clip
                        self.selected_track_type = track_type
                        clip_clicked = True
                        break

        if clip_clicked and self.selected_clip:
            # Highlight selected clip
            self._redraw_timeline_canvas()
            self.lbl_selection.configure(
                text=f"Selected: {self.selected_clip.name}\nTrack: {self.selected_track_type}\nStart: {self.selected_clip.start_time:.1f}s | Dur: {self.selected_clip.duration:.1f}s",
                text_color=Theme.ACCENT[1]
            )
            # Enable clip buttons
            self.btn_split.configure(state="normal")
            self.btn_delete.configure(state="normal")
            self.btn_trim_left.configure(state="normal")
            self.btn_trim_right.configure(state="normal")
        else:
            # Scrub playhead if clicked ruler
            if canvas_y <= self.ruler_height + 5:
                target_t = canvas_x / self.zoom_factor
                engine.controller.playback.set_time(target_t, engine.get_total_duration())
                
                # Deselect clip
                self.selected_clip = None
                self.selected_track_type = None
                self.lbl_selection.configure(
                    text="No clip selected.\nClick a clip box on the tracks below to split, trim, or move it.",
                    text_color=Theme.TEXT_MUTED
                )
                self.btn_split.configure(state="disabled")
                self.btn_delete.configure(state="disabled")
                self.btn_trim_left.configure(state="disabled")
                self.btn_trim_right.configure(state="disabled")
                
                self._redraw_timeline_canvas()
                self._draw_monitor_preview()

    def _on_timeline_canvas_drag(self, event: tk.Event) -> None:
        """Support playhead scrubbing by drag click on time ruler."""
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        if canvas_y <= self.ruler_height + 15:
            target_t = canvas_x / self.zoom_factor
            engine.controller.playback.set_time(target_t, engine.get_total_duration())
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _on_zoom_changed(self, val: float) -> None:
        """Update timeline ruler width pixels scaling factors."""
        self.zoom_factor = val
        self._redraw_timeline_canvas()

    # --- Playback Controls Actions ---

    def _on_play_toggle(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        playback = engine.controller.playback
        if playback.playing:
            playback.pause()
            self.btn_play.configure(text="▶ Play", fg_color=Theme.SUCCESS)
        else:
            playback.play()
            self.btn_play.configure(text="⏸ Pause", fg_color=Theme.WARNING)

    def _on_stop(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.playback.stop()
            self.btn_play.configure(text="▶ Play", fg_color=Theme.SUCCESS)
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _on_next_frame(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.playback.next_frame(engine.get_total_duration())
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _on_prev_frame(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.playback.prev_frame()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

    def _toggle_loop(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            playback = engine.controller.playback
            playback.loop = not playback.loop
            msg = "Loop Active" if playback.loop else "Loop Off"
            self.main_window.update_status(f"Timeline: {msg}")

    # --- Animation tick loop ---

    def _start_playback_poller(self) -> None:
        self._play_loop_active = True
        self._playback_poll_loop()

    def _playback_poll_loop(self) -> None:
        if not self._play_loop_active:
            return

        # Skip heavy rendering when the editor view is not visible (tab switched away)
        try:
            is_visible = self.winfo_viewable()
        except Exception:
            is_visible = True

        engine = getattr(self.main_window, "timeline_engine", None)
        if is_visible and engine and engine.controller.playback.playing:
            # Tick clock playhead updates
            engine.controller.playback.update_tick(engine.get_total_duration())

            # Redraw preview monitors and vertical playheads
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()

            # Schedule fast update (e.g. 20ms for ~50fps)
            self.after(20, self._playback_poll_loop)
        elif engine and engine.controller.playback.playing and not is_visible:
            # Still tick the clock even when hidden, but skip expensive rendering
            engine.controller.playback.update_tick(engine.get_total_duration())
            self.after(200, self._playback_poll_loop)
        else:
            # Paced idle updates (e.g. every 200ms when paused)
            self.after(200, self._playback_poll_loop)

    # --- Clip editing actions ---

    def _on_split_clicked(self) -> None:
        """Split selected clip at current playhead position."""
        if not self.selected_clip or not self.selected_track_type:
            return

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        t = engine.get_playback_time()
        success = engine.controller.split_clip(self.selected_track_type, self.selected_clip.clip_id, t)
        
        if success:
            self.selected_clip = None
            self.selected_track_type = None
            self._refresh_history_actions()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()
            self.main_window.update_status("Timeline: Clip split successfully.")
        else:
            self.main_window.show_error("Edit Blocked", "Playhead must be inside clip bounds to split.")

    def _on_delete_clicked(self) -> None:
        """Delete selected clip."""
        if not self.selected_clip or not self.selected_track_type:
            return

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        success = engine.controller.delete_clip(self.selected_track_type, self.selected_clip.clip_id)
        if success:
            self.selected_clip = None
            self.selected_track_type = None
            self._refresh_history_actions()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()
            self.main_window.update_status("Timeline: Clip deleted.")

    def _on_trim_nudge(self, side: str, delta: float) -> None:
        """Trim selected clip boundary left or right by delta."""
        if not self.selected_clip or not self.selected_track_type:
            return

        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        success = engine.controller.trim_clip(self.selected_track_type, self.selected_clip.clip_id, side, delta)
        if success:
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()
            self.main_window.update_status(f"Timeline: Trimmed clip {side} boundary.")

    def _on_undo_clicked(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            success = engine.controller.undo()
            if success:
                self.selected_clip = None
                self.selected_track_type = None
                self._refresh_history_actions()
                self._redraw_timeline_canvas()
                self._draw_monitor_preview()
                self.main_window.update_status("Timeline: Undo complete.")

    def _on_redo_clicked(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            success = engine.controller.redo()
            if success:
                self.selected_clip = None
                self.selected_track_type = None
                self._refresh_history_actions()
                self._redraw_timeline_canvas()
                self._draw_monitor_preview()
                self.main_window.update_status("Timeline: Redo complete.")

    # --- Cache viewer size calculation ---

    def _refresh_cache_size(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        try:
            cache_dir = engine.controller.renderer.cache_dir
            # Sum up sizes of PNGs inside
            total_size = sum(f.stat().st_size for f in cache_dir.glob("*") if f.is_file())
            # Format readable
            mb_sz = total_size / (1024 * 1024)
            self.lbl_cache_size.configure(text=f"Cache folder size: {mb_sz:.2f} MB")
        except Exception:
            self.lbl_cache_size.configure(text="Cache folder size: 0.0 MB")

    def _on_clear_cache(self) -> None:
        engine = getattr(self.main_window, "timeline_engine", None)
        if engine:
            engine.controller.renderer.clear_readers()
            # Delete cached PNG files
            cache_dir = engine.controller.renderer.cache_dir
            for f in cache_dir.glob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                except Exception:
                    pass
            self._refresh_cache_size()
            self._redraw_timeline_canvas()
            self._draw_monitor_preview()
            self.main_window.update_status("Timeline: Cached preview frames cleared.")

    # --- Background rendering trigger ---

    def _on_render_project_clicked(self) -> None:
        """Trigger background thread project video compilation render."""
        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine:
            return

        if engine.controller.active_job and engine.controller.active_job.status in ["pending", "running"]:
            self.main_window.show_error("Execution Active", "A rendering task is already running.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Export Finished Broadcast Video",
            defaultextension=".mp4",
            filetypes=[("MP4 Videos", "*.mp4")]
        )
        if not filepath:
            return

        self._logger.info(f"Submitting project video render: {filepath}")
        self.btn_render.configure(state="disabled", text="Rendering...")
        self.render_pbar.pack(fill="x", pady=2)
        self.render_pbar.set(0.0)

        # Trigger background render
        engine.render_video(
            output_path=Path(filepath),
            low_res=False,
            progress_callback=self._update_render_progress
        )

        self._poll_render_queue()

    def _update_render_progress(self, prog: float) -> None:
        """Update progress bar values."""
        self.render_pbar.set(prog)

    def _poll_render_queue(self) -> None:
        """Poll rendering jobs and reset controls when complete."""
        engine = getattr(self.main_window, "timeline_engine", None)
        if not engine or not engine.controller.active_job:
            return

        job = engine.controller.active_job
        status = job.status

        if status == "completed":
            self.btn_render.configure(state="normal", text="⚡ Render Video Project")
            self.render_pbar.pack_forget()
            self.lbl_render_status.configure(text="Render complete!", text_color=Theme.SUCCESS)
            self.main_window.update_status(f"Render completed: {job.output_path.name}")
            
            # Record in history logs manager
            self.main_window.history_mgr.add_entry(
                project_id=self.main_window.current_project.id if self.main_window.current_project else "Standalone",
                project_name=self.main_window.current_project.name if self.main_window.current_project else "Standalone",
                status="Success",
                details=f"Finished video rendered: {job.output_path.name}"
            )
        elif status == "failed":
            self.btn_render.configure(state="normal", text="⚡ Render Video Project")
            self.render_pbar.pack_forget()
            self.lbl_render_status.configure(text="Render failed.", text_color=Theme.DANGER)
            self.main_window.show_error("Rendering Error", job.error_message or "Compositor execution failure.")
        else:
            # Poll status log
            msg = f"Stitching frames and mixing soundtracks... ({int(job.progress * 100)}%)"
            self.lbl_render_status.configure(text=msg, text_color=Theme.TEXT_SECONDARY)
            self.after(200, self._poll_render_queue)

    def destroy(self) -> None:
        """Halt loops on cleanup."""
        self._play_loop_active = False
        super().destroy()
