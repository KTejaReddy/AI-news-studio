"""Export View Dashboard for AI News Studio.

Provides user interface controls for configuring target resolution presets,
rendering timeline outputs, and monitoring the batch export transcode queue.
"""

import logging
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING, Optional, List, Dict

import customtkinter as ctk

from app.theme import Theme
from core.export.export_settings import ExportSettings
from core.export.export_job import ExportJob

if TYPE_CHECKING:
    from app.gui import MainWindow


class ExportView(ctk.CTkFrame):
    """Dashboard view for presets configuration, thumbnail preview, queue, and history."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize ExportView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_polling = False
        self._playing_file_path: Optional[Path] = None

        # Grid configuration: 2 columns
        self.grid_columnconfigure(0, weight=3)  # Settings & Setup
        self.grid_columnconfigure(1, weight=2)  # Queue & History
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_left_panel()
        self._create_right_panel()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(
            header_f,
            text="Video Export & Rendering Studio",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # GPU acceleration badge
        ctk.CTkLabel(
            header_f,
            text=" (Hardware Acceleration Ready)",
            font=Theme.get_font(12, "italic"),
            text_color=Theme.SUCCESS
        ).pack(side="left", padx=5, pady=(8, 0))

    def _create_left_panel(self) -> None:
        """Construct the left workspace containing preset choices, and watermark/intro paths."""
        left_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        left_frame.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")

        # Title
        ctk.CTkLabel(
            left_frame,
            text="Export Configuration",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # --- Section 1: Source & Output ---
        ctk.CTkLabel(
            left_frame,
            text="1. Video Source:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        # Radio buttons to choose between Active Project Timeline and Custom Video
        self.source_var = tk.StringVar(value="timeline")
        
        self.timeline_radio = ctk.CTkRadioButton(
            left_frame,
            text="Active Project Timeline (Auto-Render)",
            variable=self.source_var,
            value="timeline",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_source_changed
        )
        self.timeline_radio.pack(anchor="w", padx=25, pady=3)

        self.custom_radio = ctk.CTkRadioButton(
            left_frame,
            text="Custom Input Video File",
            variable=self.source_var,
            value="custom",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_source_changed
        )
        self.custom_radio.pack(anchor="w", padx=25, pady=3)

        # Browse input video row (hidden/disabled by default)
        self.input_file_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.input_file_frame.pack(fill="x", padx=25, pady=(5, 10))
        self.input_file_frame.columnconfigure(0, weight=1)

        self.input_file_entry = ctk.CTkEntry(
            self.input_file_frame,
            placeholder_text="Select input video file to transcode...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.input_file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.input_file_btn = ctk.CTkButton(
            self.input_file_frame,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_input_video
        )
        self.input_file_btn.grid(row=0, column=1)

        # Target Output release path
        ctk.CTkLabel(
            left_frame,
            text="2. Destination Release Path:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        out_f = ctk.CTkFrame(left_frame, fg_color="transparent")
        out_f.pack(fill="x", padx=15, pady=(0, 10))
        out_f.columnconfigure(0, weight=1)

        self.out_file_entry = ctk.CTkEntry(
            out_f,
            placeholder_text="Choose destination MP4 path...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.out_file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            out_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_output
        ).grid(row=0, column=1)

        # --- Section 2: Preset Parameters Card ---
        params_card = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        params_card.pack(fill="x", padx=15, pady=10, ipady=5)

        ctk.CTkLabel(
            params_card,
            text="Resolution & Format Settings",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(10, 8))

        # Preset Selector
        p_row = ctk.CTkFrame(params_card, fg_color="transparent")
        p_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            p_row,
            text="Format Preset:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.preset_opt = ctk.CTkOptionMenu(
            p_row,
            values=list(ExportSettings.PRESETS.keys()),
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28,
            command=self._on_preset_changed
        )
        self.preset_opt.pack(side="right")

        # Custom dimensions (hidden/disabled unless custom preset selected)
        self.dim_row = ctk.CTkFrame(params_card, fg_color="transparent")
        self.dim_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            self.dim_row,
            text="Custom Dimensions (WxH):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.dim_h_entry = ctk.CTkEntry(self.dim_row, width=60, height=24, font=Theme.get_font(11))
        self.dim_h_entry.pack(side="right")
        ctk.CTkLabel(self.dim_row, text=" x ", font=Theme.get_font(11)).pack(side="right")
        self.dim_w_entry = ctk.CTkEntry(self.dim_row, width=60, height=24, font=Theme.get_font(11))
        self.dim_w_entry.pack(side="right")

        # FPS, Codec, Container rows
        f_row = ctk.CTkFrame(params_card, fg_color="transparent")
        f_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            f_row,
            text="Frame Rate (FPS):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.fps_opt = ctk.CTkOptionMenu(
            f_row,
            values=["24", "30", "60"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.fps_opt.set("30")
        self.fps_opt.pack(side="right")

        c_row = ctk.CTkFrame(params_card, fg_color="transparent")
        c_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            c_row,
            text="Video Codec:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.codec_opt = ctk.CTkOptionMenu(
            c_row,
            values=["H264", "H265", "AV1"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28,
            command=self._on_codec_changed
        )
        self.codec_opt.pack(side="right")

        container_row = ctk.CTkFrame(params_card, fg_color="transparent")
        container_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            container_row,
            text="File Container:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.container_opt = ctk.CTkOptionMenu(
            container_row,
            values=["MP4", "MOV", "MKV", "WEBM"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.container_opt.pack(side="right")

        b_row = ctk.CTkFrame(params_card, fg_color="transparent")
        b_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            b_row,
            text="Encoding Quality (Bitrate):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.bitrate_opt = ctk.CTkOptionMenu(
            b_row,
            values=["Low", "Medium", "High", "Lossless"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.bitrate_opt.set("Medium")
        self.bitrate_opt.pack(side="right")

        gpu_row = ctk.CTkFrame(params_card, fg_color="transparent")
        gpu_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            gpu_row,
            text="GPU Transcode Acceleration:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.gpu_opt = ctk.CTkOptionMenu(
            gpu_row,
            values=["Auto-Detect", "Force CPU"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.gpu_opt.pack(side="right")

        # --- Section 3: Branding & Overlays Card ---
        branding_card = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        branding_card.pack(fill="x", padx=15, pady=10, ipady=5)

        ctk.CTkLabel(
            branding_card,
            text="Watermark, Subtitles, Intro & Outro",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(10, 8))

        # Burn subtitles checkbox
        self.subtitles_cb = ctk.CTkCheckBox(
            branding_card,
            text="Burn Subtitles/Captions on video frames",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_PRIMARY,
            checkbox_height=18,
            checkbox_width=18
        )
        self.subtitles_cb.select()
        self.subtitles_cb.pack(anchor="w", padx=15, pady=5)

        # Watermark path browse row
        ctk.CTkLabel(
            branding_card,
            text="Watermark Overlay Image (PNG/JPG):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 1))

        wm_row = ctk.CTkFrame(branding_card, fg_color="transparent")
        wm_row.pack(fill="x", padx=15, pady=3)
        wm_row.columnconfigure(0, weight=1)

        self.watermark_entry = ctk.CTkEntry(wm_row, placeholder_text="Select watermark path...", font=Theme.get_font(10), height=28)
        self.watermark_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            wm_row,
            text="📁 Browse",
            font=Theme.get_font(10, "bold"),
            width=70,
            height=28,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_browse_watermark
        ).grid(row=0, column=1)

        # Watermark Opacity Row
        op_row = ctk.CTkFrame(branding_card, fg_color="transparent")
        op_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(
            op_row,
            text="Watermark Opacity:",
            font=Theme.get_font(10, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")
        
        self.opacity_slider = ctk.CTkSlider(op_row, from_=0.0, to=1.0, width=120, height=14)
        self.opacity_slider.set(0.5)
        self.opacity_slider.pack(side="right")

        # Intro path browse row
        ctk.CTkLabel(
            branding_card,
            text="Intro Bumper Video Clip (MP4):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 1))

        intro_row = ctk.CTkFrame(branding_card, fg_color="transparent")
        intro_row.pack(fill="x", padx=15, pady=3)
        intro_row.columnconfigure(0, weight=1)

        self.intro_entry = ctk.CTkEntry(intro_row, placeholder_text="Select intro clip path...", font=Theme.get_font(10), height=28)
        self.intro_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            intro_row,
            text="📁 Browse",
            font=Theme.get_font(10, "bold"),
            width=70,
            height=28,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_browse_intro
        ).grid(row=0, column=1)

        # Outro path browse row
        ctk.CTkLabel(
            branding_card,
            text="Outro Bumper Video Clip (MP4):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 1))

        outro_row = ctk.CTkFrame(branding_card, fg_color="transparent")
        outro_row.pack(fill="x", padx=15, pady=3)
        outro_row.columnconfigure(0, weight=1)

        self.outro_entry = ctk.CTkEntry(outro_row, placeholder_text="Select outro clip path...", font=Theme.get_font(10), height=28)
        self.outro_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            outro_row,
            text="📁 Browse",
            font=Theme.get_font(10, "bold"),
            width=70,
            height=28,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_browse_outro
        ).grid(row=0, column=1)

        # Submit button
        self.export_btn = ctk.CTkButton(
            left_frame,
            text="📤 Queue & Start Export Job",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=40,
            command=self._on_export_clicked
        )
        self.export_btn.pack(fill="x", padx=15, pady=15)

        # Initialize defaults
        self._on_preset_changed("Landscape YouTube (1920x1080)")
        self._on_source_changed()

    def _create_right_panel(self) -> None:
        """Construct Preview, Batch Queue, and History lists (right side)."""
        right_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        right_frame.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(3, weight=1)  # Queue section expands
        right_frame.rowconfigure(5, weight=1)  # History section expands

        # --- Section 1: Preview Clip Card ---
        ctk.CTkLabel(
            right_frame,
            text="Output Preview Thumbnail",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.preview_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=140
        )
        self.preview_card.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.preview_card.grid_propagate(False)
        self.preview_card.columnconfigure(0, weight=1)
        self.preview_card.rowconfigure(0, weight=1)

        self.preview_placeholder = ctk.CTkLabel(
            self.preview_card,
            text="No rendered output video preview.\nQueue and process jobs to generate outputs.",
            font=Theme.get_font(11, "italic"),
            text_color=Theme.TEXT_MUTED
        )
        self.preview_placeholder.grid(row=0, column=0)

        self.play_btn = ctk.CTkButton(
            self.preview_card,
            text="▶️ Play Rendered Release",
            font=Theme.get_font(11, "bold"),
            width=160,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_play_rendered
        )

        # --- Section 2: Batch Queue Viewer ---
        q_header = ctk.CTkFrame(right_frame, fg_color="transparent")
        q_header.grid(row=2, column=0, padx=15, pady=(5, 5), sticky="ew")
        
        ctk.CTkLabel(
            q_header,
            text="Batch Export Queue",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # Pause/Resume and Clear queue buttons
        self.pause_queue_btn = ctk.CTkButton(
            q_header,
            text="⏸️ Pause",
            font=Theme.get_font(10, "bold"),
            width=65,
            height=22,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_toggle_queue_pause
        )
        self.pause_queue_btn.pack(side="right", padx=3)

        ctk.CTkButton(
            q_header,
            text="🧹 Clear completed",
            font=Theme.get_font(10, "bold"),
            width=100,
            height=22,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            command=self._on_clear_queue
        ).pack(side="right", padx=3)

        self.queue_scroll = ctk.CTkScrollableFrame(right_frame, fg_color="transparent")
        self.queue_scroll.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="nsew")

        # --- Section 3: History List ---
        ctk.CTkLabel(
            right_frame,
            text="Export Transcode History",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=4, column=0, padx=15, pady=(5, 5), sticky="w")

        self.history_scroll = ctk.CTkScrollableFrame(right_frame, fg_color="transparent")
        self.history_scroll.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def on_show(self) -> None:
        """Triggered automatically when page is navigated to."""
        self._refresh_history_list()
        
        # Start GUI polling for progress updates
        self._active_polling = True
        self._poll_queue_progress()

    def _on_source_changed(self) -> None:
        """Enables/disables custom input path entry depending on radio settings."""
        if self.source_var.get() == "timeline":
            # Disabled input file row
            self.input_file_entry.configure(state="disabled")
            self.input_file_btn.configure(state="disabled")
            
            # Autocomplete output path from active project
            if self.main_window.current_project:
                output_dir = self.main_window.workspace_dir / "output"
                output_dir.mkdir(parents=True, exist_ok=True)
                proj_name = self.main_window.current_project.name.replace(" ", "_").lower()
                self.out_file_entry.delete(0, tk.END)
                self.out_file_entry.insert(0, str(output_dir / f"{proj_name}_release.mp4"))
        else:
            self.input_file_entry.configure(state="normal")
            self.input_file_btn.configure(state="normal")

    def _on_preset_changed(self, value: str) -> None:
        """Fills width/height inputs or disables them based on preset selection."""
        if value == "Custom Resolution":
            self.dim_w_entry.configure(state="normal")
            self.dim_h_entry.configure(state="normal")
            self.dim_w_entry.delete(0, tk.END)
            self.dim_w_entry.insert(0, "1920")
            self.dim_h_entry.delete(0, tk.END)
            self.dim_h_entry.insert(0, "1080")
        else:
            width, height = ExportSettings.PRESETS[value]
            self.dim_w_entry.configure(state="normal")
            self.dim_h_entry.configure(state="normal")
            self.dim_w_entry.delete(0, tk.END)
            self.dim_w_entry.insert(0, str(width))
            self.dim_h_entry.configure(state="normal")
            self.dim_h_entry.delete(0, tk.END)
            self.dim_h_entry.insert(0, str(height))
            self.dim_w_entry.configure(state="disabled")
            self.dim_h_entry.configure(state="disabled")

    def _on_codec_changed(self, value: str) -> None:
        """Adjust container dropdown selections for standard wrappers."""
        if value == "AV1":
            self.container_opt.set("WEBM")
        else:
            self.container_opt.set("MP4")

    def _on_browse_input_video(self) -> None:
        """Source video file selector."""
        filepath = filedialog.askopenfilename(
            title="Select Source Video File",
            filetypes=[("Video Files", "*.mp4;*.avi;*.mov;*.mkv")]
        )
        if filepath:
            self.input_file_entry.configure(state="normal")
            self.input_file_entry.delete(0, tk.END)
            self.input_file_entry.insert(0, filepath)

    def _on_browse_output(self) -> None:
        """Target output file selector."""
        filepath = filedialog.asksaveasfilename(
            title="Set Target Output Release File",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("MOV Video", "*.mov"), ("MKV Video", "*.mkv"), ("WebM Video", "*.webm")]
        )
        if filepath:
            self.out_file_entry.delete(0, tk.END)
            self.out_file_entry.insert(0, filepath)

    def _on_browse_watermark(self) -> None:
        """Watermark file selector."""
        filepath = filedialog.askopenfilename(
            title="Select Watermark Image Overlay",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")]
        )
        if filepath:
            self.watermark_entry.delete(0, tk.END)
            self.watermark_entry.insert(0, filepath)

    def _on_browse_intro(self) -> None:
        """Intro clip file selector."""
        filepath = filedialog.askopenfilename(
            title="Select Intro Clip File",
            filetypes=[("Video Files", "*.mp4;*.mov")]
        )
        if filepath:
            self.intro_entry.delete(0, tk.END)
            self.intro_entry.insert(0, filepath)

    def _on_browse_outro(self) -> None:
        """Outro clip file selector."""
        filepath = filedialog.askopenfilename(
            title="Select Outro Clip File",
            filetypes=[("Video Files", "*.mp4;*.mov")]
        )
        if filepath:
            self.outro_entry.delete(0, tk.END)
            self.outro_entry.insert(0, filepath)

    def _on_toggle_queue_pause(self) -> None:
        """Toggle enqueued process workers execution."""
        engine = self.main_window.export_engine
        if engine.queue.is_paused:
            engine.queue.resume_queue()
            self.pause_queue_btn.configure(text="⏸️ Pause")
            self.main_window.update_status("Export transcode queue resumed.")
        else:
            engine.queue.pause_queue()
            self.pause_queue_btn.configure(text="▶️ Resume")
            self.main_window.update_status("Export transcode queue paused.")

    def _on_clear_queue(self) -> None:
        """Clears finished tasks from indexing queues."""
        self.main_window.export_engine.queue.clear_queue()
        self._refresh_queue_list()

    def _on_cancel_job(self, job_id: str) -> None:
        """Cancel a single active/pending task."""
        self.main_window.export_engine.queue.cancel_job(job_id)
        self.main_window.update_status(f"Export Job {job_id[:8]} cancelled.")
        self._refresh_queue_list()

    def _on_export_clicked(self) -> None:
        """Orchestrate timeline compiling or transcode queuing."""
        source_mode = self.source_var.get()
        out_path_str = self.out_file_entry.get().strip()

        if not out_path_str:
            self.main_window.show_error("Validation Error", "Please specify a destination release path.")
            return

        out_path = Path(out_path_str)

        # Parse settings
        preset = self.preset_opt.get()
        fps = int(self.fps_opt.get())
        codec = self.codec_opt.get()
        container = self.container_opt.get()
        bitrate = self.bitrate_opt.get()
        gpu_mode = self.gpu_opt.get()
        burn_subtitles = self.subtitles_cb.get() == 1

        try:
            width = int(self.dim_w_entry.get().strip())
            height = int(self.dim_h_entry.get().strip())
        except ValueError:
            width, height = 1920, 1080

        watermark = self.watermark_entry.get().strip()
        opacity = self.opacity_slider.get()
        intro = self.intro_entry.get().strip()
        outro = self.outro_entry.get().strip()

        settings = ExportSettings(
            preset=preset,
            width=width,
            height=height,
            fps=fps,
            codec=codec,
            container=container,
            bitrate=bitrate,
            gpu_acceleration=gpu_mode,
            burn_subtitles=burn_subtitles,
            watermark_path=watermark,
            watermark_opacity=opacity,
            intro_path=intro,
            outro_path=outro
        )

        if source_mode == "timeline":
            # Must render project timeline first
            if not self.main_window.current_project:
                self.main_window.show_error("Project Error", "No active project context selected. Please select a project or choose custom video source.")
                return
            
            # Check timeline tracks
            tracks = self.main_window.timeline_engine.get_tracks()
            if not tracks:
                self.main_window.show_error("Timeline Error", "The timeline is empty. Add presenters or media before exporting.")
                return

            self.main_window.update_status("Compiling timeline draft. Please wait...")
            self.export_btn.configure(state="disabled", text="Compiling Draft...")

            # Render to temporary silent/preview file
            temp_master_name = f"draft_master_{int(time.time())}.mp4"
            temp_master_path = self.main_window.workspace_dir / "core" / "export" / "render_cache" / temp_master_name
            temp_master_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate subtitle SRT content directly from timeline Text track
            srt_content = self._make_srt_from_timeline()

            # Define inner thread to compile draft so GUI doesn't freeze
            def compile_draft_thread():
                try:
                    # Sync compiler call
                    # We can use the timeline controller renderer to compile draft
                    success = self.main_window.timeline_engine.controller.renderer.render_timeline_video(
                        tracks=self.main_window.timeline_engine.get_tracks(),
                        scenes=self.main_window.timeline_engine.get_scenes(),
                        output_mp4_path=temp_master_path,
                        total_duration=self.main_window.timeline_engine.get_total_duration(),
                        aspect_ratio="9:16" if "Shorts" in preset or "Reels" in preset or "TikTok" in preset else "16:9",
                        fps=fps,
                        low_res=False
                    )

                    if not success or not temp_master_path.exists():
                        raise RuntimeError("Timeline render builder compile failed.")

                    # Draft built! Now submit job to the transcode queue
                    self.main_window.after(0, lambda: self._submit_job_and_clear(temp_master_path, srt_content, out_path, settings))
                except Exception as ex:
                    self._logger.error(f"Failed compile draft: {ex}")
                    self.main_window.after(0, lambda: self.main_window.show_error("Timeline Compile Failed", f"Draft compilation failed: {ex}"))
                    self.main_window.after(0, lambda: self.export_btn.configure(state="normal", text="📤 Queue & Start Export Job"))

            threading.Thread(target=compile_draft_thread, daemon=True).start()

        else:
            # Custom input file source
            in_file_str = self.input_file_entry.get().strip()
            if not in_file_str or not Path(in_file_str).exists():
                self.main_window.show_error("Validation Error", "Please specify a valid source input video file.")
                return
            
            in_file = Path(in_file_str)
            # Check for SRT file matching the custom input video name
            srt_content = ""
            custom_srt_path = in_file.with_suffix(".srt")
            if custom_srt_path.exists():
                try:
                    with open(custom_srt_path, "r", encoding="utf-8") as sf:
                        srt_content = sf.read()
                except Exception:
                    pass

            self._submit_job_and_clear(in_file, srt_content, out_path, settings)

    def _submit_job_and_clear(self, input_video: Path, srt_content: str, output_video: Path, settings: ExportSettings) -> None:
        """Submit parsed job parameters to engine."""
        self.main_window.export_engine.submit_export_job(
            output_path=output_video,
            settings=settings,
            input_path=input_video,
            srt_content=srt_content
        )
        self.main_window.update_status(f"Export enqueued: {output_video.name}")
        self.export_btn.configure(state="normal", text="📤 Queue & Start Export Job")
        self._refresh_queue_list()

    def _make_srt_from_timeline(self) -> str:
        """Convert Text track clips into a standard subtitle SRT string."""
        tracks = self.main_window.timeline_engine.get_tracks()
        text_track = next((t for t in tracks if t.track_type == "Text"), None)
        if not text_track:
            return ""

        srt_lines = []
        idx = 1
        for clip in sorted(text_track.clips, key=lambda c: c.start_time):
            if not clip.name:
                continue
            start = clip.start_time
            end = start + clip.duration

            def format_time(t: float) -> str:
                h = int(t // 3600)
                m = int((t % 3600) // 60)
                s = int(t % 60)
                ms = int((t * 1000) % 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            srt_lines.append(f"{idx}")
            srt_lines.append(f"{format_time(start)} --> {format_time(end)}")
            srt_lines.append(clip.name)
            srt_lines.append("")
            idx += 1

        return "\n".join(srt_lines)

    def _poll_queue_progress(self) -> None:
        """Periodic loop to update the GUI status of active/pending jobs."""
        if not self._active_polling:
            return

        self._refresh_queue_list()

        # Check if there is an active running job and update its status
        active_w = self.main_window.export_engine.worker.active_job
        if active_w and active_w.status == "running":
            # Refresh history if the last run completed
            pass

        # Reschedule polling
        self.after(800, self._poll_queue_progress)

    def _refresh_queue_list(self) -> None:
        """Re-draw items inside the batch queue scroll wrapper."""
        # Avoid redrawing if user hasn't switched to this tab or queue is empty
        jobs = self.main_window.export_engine.queue.list_jobs()

        # Track which widgets are already drawn to prevent heavy flashing redraws
        # (For simplicity and stability, we destroy and redraw but we can keep it light)
        for w in self.queue_scroll.winfo_children():
            w.destroy()

        if not jobs:
            ctk.CTkLabel(
                self.queue_scroll,
                text="No jobs currently in batch queue.",
                font=Theme.get_font(11, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=20)
            return

        for job in jobs:
            row = ctk.CTkFrame(
                self.queue_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=4, ipady=4)
            row.columnconfigure(0, weight=1)

            # Details
            info_f = ctk.CTkFrame(row, fg_color="transparent")
            info_f.grid(row=0, column=0, sticky="ew", padx=10, pady=2)
            
            ctk.CTkLabel(
                info_f,
                text=job.output_path.name,
                font=Theme.get_font(11, "bold"),
                text_color=Theme.TEXT_PRIMARY
            ).pack(side="left")

            status_color = Theme.TEXT_MUTED
            if job.status == "running":
                status_color = Theme.ACCENT
            elif job.status == "completed":
                status_color = Theme.SUCCESS
            elif job.status == "failed":
                status_color = Theme.WARNING

            ctk.CTkLabel(
                info_f,
                text=f" ({job.status.upper()})",
                font=Theme.get_font(10, "bold"),
                text_color=status_color
            ).pack(side="left")

            # Progress Bar & metrics
            prog_row = ctk.CTkFrame(row, fg_color="transparent")
            prog_row.grid(row=1, column=0, sticky="ew", padx=10, pady=2)
            prog_row.columnconfigure(0, weight=1)

            pbar = ctk.CTkProgressBar(prog_row, progress_color=Theme.ACCENT, height=6)
            pbar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
            pbar.set(job.progress)

            ctk.CTkLabel(
                prog_row,
                text=f"{int(job.progress * 100)}%",
                font=Theme.get_font(10, "bold"),
                text_color=Theme.TEXT_PRIMARY
            ).grid(row=0, column=1)

            # Extra stats for running job
            if job.status == "running":
                stats_lbl = ctk.CTkLabel(
                    row,
                    text=f"Speed: {job.render_speed:.1f} fps  |  ETA: {int(job.time_remaining)}s  |  Frame: {job.frames_rendered}/{job.total_frames}",
                    font=Theme.get_font(10),
                    text_color=Theme.TEXT_SECONDARY
                )
                stats_lbl.grid(row=2, column=0, sticky="w", padx=10, pady=1)

            # Action button
            if job.status in ["pending", "running", "paused"]:
                ctk.CTkButton(
                    row,
                    text="❌ Cancel",
                    font=Theme.get_font(9, "bold"),
                    width=60,
                    height=20,
                    fg_color=Theme.BG_CARD,
                    text_color=Theme.WARNING,
                    hover_color=Theme.BG_CARD_HOVER,
                    corner_radius=Theme.CORNER_RADIUS - 4,
                    command=lambda jid=job.job_id: self._on_cancel_job(jid)
                ).grid(row=0, column=1, rowspan=2, padx=10, pady=2)

    def _refresh_history_list(self) -> None:
        """Scan entries from history file and populate list row views."""
        for w in self.history_scroll.winfo_children():
            w.destroy()

        entries = self.main_window.export_engine.history.list_entries()
        if not entries:
            ctk.CTkLabel(
                self.history_scroll,
                text="No export transcode history recorded.",
                font=Theme.get_font(11, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=20)
            return

        # Show top 8 history entries
        for entry in entries[:8]:
            row = ctk.CTkFrame(
                self.history_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=3, ipady=3)
            row.columnconfigure(0, weight=1)

            out_name = Path(entry.get("output_path", "")).name
            meta_str = f"{entry.get('resolution', '')} | {entry.get('codec', '')} | {entry.get('fps', '')}fps"
            size_mb = entry.get("file_size_bytes", 0) / (1024 * 1024)
            meta_str += f" | {size_mb:.1f} MB"

            # Info block
            lbl_f = ctk.CTkFrame(row, fg_color="transparent")
            lbl_f.grid(row=0, column=0, sticky="w", padx=10, pady=2)

            ctk.CTkLabel(
                lbl_f,
                text=out_name,
                font=Theme.get_font(11, "bold"),
                text_color=Theme.TEXT_PRIMARY
            ).pack(anchor="w")

            ctk.CTkLabel(
                lbl_f,
                text=meta_str,
                font=Theme.get_font(10),
                text_color=Theme.TEXT_SECONDARY
            ).pack(anchor="w")

            # Load Preview Button
            ctk.CTkButton(
                row,
                text="🎬 Preview",
                font=Theme.get_font(10, "bold"),
                width=80,
                height=24,
                fg_color=Theme.BG_CARD,
                text_color=Theme.TEXT_PRIMARY,
                hover_color=Theme.BG_CARD_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda path=Path(entry.get("output_path", "")): self._load_file_to_preview(path)
            ).grid(row=0, column=1, padx=5, pady=2)

    def _load_file_to_preview(self, file_path: Path) -> None:
        """Put completed path into active player slots."""
        file_path = self.main_window.workspace_dir / file_path
        if file_path.exists():
            self._playing_file_path = file_path
            self.preview_placeholder.grid_forget()
            
            # Show play button
            self.play_btn.grid(row=0, column=0, padx=15, pady=15)
            self.play_btn.configure(text=f"▶️ Play {file_path.name[:25]}")
            
            # Update background preview thumbnail card
            self.main_window.update_status(f"Loaded preview file: {file_path.name}")

    def _on_play_rendered(self) -> None:
        """Launch local platform media player."""
        if self._playing_file_path and self._playing_file_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self._playing_file_path))
                else:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.run([opener, str(self._playing_file_path)], check=True)
            except Exception as e:
                self.main_window.show_error("Playback Error", f"Failed starting player: {e}")

    def destroy(self) -> None:
        """Shutdown polling threads when widget is closed."""
        self._active_polling = False
        super().destroy()
