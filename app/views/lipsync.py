"""Lip Sync View Dashboard for AI News Studio.

Provides an interactive studio to align speaker mouth movements to voice tracks
using LatentSync model weights, preview clips, and review generation history.
"""

import logging
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from app.theme import Theme
from core.lipsync.lipsync_job import LipSyncJob

if TYPE_CHECKING:
    from app.gui import MainWindow


class LipSyncView(ctk.CTkFrame):
    """Viewport dashboard providing file selectors, quality controls, and history for Lip Syncing."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize LipSyncView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_job: Optional[LipSyncJob] = None
        self._monitor_active = False

        # Grid configuration: 2 columns
        self.grid_columnconfigure(0, weight=3)  # Setup Workshop
        self.grid_columnconfigure(1, weight=2)  # Previews & History
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_left_workshop()
        self._create_right_sidebar()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(
            header_f,
            text="LatentSync Lip Synchronization Studio",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # Hardware display indicator
        device = "GPU Acceleration Active" if self.main_window.settings_mgr.device_mode == "GPU" else "CPU Mode"
        ctk.CTkLabel(
            header_f,
            text=f" ({device})",
            font=Theme.get_font(12, "italic"),
            text_color=Theme.SUCCESS if "GPU" in device else Theme.WARNING
        ).pack(side="left", padx=5, pady=(8, 0))

    def _create_left_workshop(self) -> None:
        """Construct the left workspace containing input selectors and settings."""
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
            text="Configuration & Inputs",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # --- Section 1: Presenter Video Input ---
        ctk.CTkLabel(
            left_frame,
            text="1. Presenter Base Video (MP4):",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        vid_f = ctk.CTkFrame(left_frame, fg_color="transparent")
        vid_f.pack(fill="x", padx=15, pady=(0, 10))
        vid_f.columnconfigure(0, weight=1)

        self.vid_entry = ctk.CTkEntry(
            vid_f,
            placeholder_text="Browse and select presenter video clip...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.vid_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            vid_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_video
        ).grid(row=0, column=1)

        # --- Section 2: Generated Audio Input ---
        ctk.CTkLabel(
            left_frame,
            text="2. Speech Voice Track (WAV/MP3):",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        aud_f = ctk.CTkFrame(left_frame, fg_color="transparent")
        aud_f.pack(fill="x", padx=15, pady=(0, 15))
        aud_f.columnconfigure(0, weight=1)

        self.aud_entry = ctk.CTkEntry(
            aud_f,
            placeholder_text="Browse and select script voice WAV file...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.aud_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            aud_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_audio
        ).grid(row=0, column=1)

        # --- Section 3: Parameters Card ---
        params_card = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        params_card.pack(fill="x", padx=15, pady=10, ipady=10)

        ctk.CTkLabel(
            params_card,
            text="Quality & Render Settings",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(10, 8))

        # Quality Preset Row
        q_f = ctk.CTkFrame(params_card, fg_color="transparent")
        q_f.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(
            q_f,
            text="Quality Preset:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.quality_opt = ctk.CTkOptionMenu(
            q_f,
            values=["High (30 steps)", "Fast (15 steps)"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.quality_opt.pack(side="right")

        # Hardware Device Selector Row
        dev_f = ctk.CTkFrame(params_card, fg_color="transparent")
        dev_f.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(
            dev_f,
            text="Execution Device:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        self.device_opt = ctk.CTkOptionMenu(
            dev_f,
            values=["Auto-Detect (CUDA Preferred)", "Force CPU Mode"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_CARD,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=28
        )
        self.device_opt.pack(side="right")

        # --- Section 4: Render progress tracking ---
        ctk.CTkLabel(
            left_frame,
            text="Generation Tracking & Progress:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(15, 2))

        self.prog_bar = ctk.CTkProgressBar(
            left_frame,
            progress_color=Theme.ACCENT,
            height=8
        )
        self.prog_bar.pack(fill="x", padx=15, pady=5)
        self.prog_bar.set(0.0)

        # Status text
        self.status_lbl = ctk.CTkLabel(
            left_frame,
            text="Status: Standing by.",
            font=Theme.get_font(11, "italic"),
            text_color=Theme.TEXT_MUTED
        )
        self.status_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Log output console area
        self.console_text = ctk.CTkTextbox(
            left_frame,
            font=Theme.get_font(10, "normal"),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_SECONDARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=100,
            state="disabled"
        )
        self.console_text.pack(fill="x", padx=15, pady=(0, 15))

        # Bottom buttons row
        btn_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(10, 15))

        self.cancel_btn = ctk.CTkButton(
            btn_row,
            text="❌ Cancel",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=36,
            width=90,
            state="disabled",
            command=self._on_cancel_clicked
        )
        self.cancel_btn.pack(side="left")

        self.sync_btn = ctk.CTkButton(
            btn_row,
            text="👄 Synchronize Lips",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=36,
            command=self._on_sync_clicked
        )
        self.sync_btn.pack(side="right")

    def _create_right_sidebar(self) -> None:
        """Construct preview windows and execution history (right side)."""
        right_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        right_frame.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(3, weight=1)  # History list expands

        # --- Section 1: Preview Clip Card ---
        ctk.CTkLabel(
            right_frame,
            text="Media Preview",
            font=Theme.get_font(15, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

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

        # Video preview play button
        self.preview_placeholder = ctk.CTkLabel(
            self.preview_card,
            text="No synced video loaded.\nRun synchronization to export MP4.",
            font=Theme.get_font(11, "italic"),
            text_color=Theme.TEXT_MUTED
        )
        self.preview_placeholder.grid(row=0, column=0)

        self.play_btn = ctk.CTkButton(
            self.preview_card,
            text="▶️ Play Sync Output",
            font=Theme.get_font(11, "bold"),
            width=140,
            height=32,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_play_preview
        )

        # --- Section 2: Output History List ---
        ctk.CTkLabel(
            right_frame,
            text="Synchronization Output History",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=2, column=0, padx=15, pady=(10, 5), sticky="w")

        self.history_scroll = ctk.CTkScrollableFrame(right_frame, fg_color="transparent")
        self.history_scroll.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="nsew")

        self._playing_file_path: Optional[Path] = None

    def on_show(self) -> None:
        """Triggered automatically when pageFocused."""
        self._refresh_history_list()

    def _on_browse_video(self) -> None:
        """Video path browser dialogue."""
        filepath = filedialog.askopenfilename(
            title="Select Presenter Video Clip",
            filetypes=[("Video Files", "*.mp4;*.avi")]
        )
        if filepath:
            self.vid_entry.delete(0, tk.END)
            self.vid_entry.insert(0, filepath)

    def _on_browse_audio(self) -> None:
        """Audio path browser dialogue."""
        filepath = filedialog.askopenfilename(
            title="Select Script Audio Clip",
            filetypes=[("Audio Files", "*.wav;*.mp3")]
        )
        if filepath:
            self.aud_entry.delete(0, tk.END)
            self.aud_entry.insert(0, filepath)

    def _on_sync_clicked(self) -> None:
        """Validates inputs and starts background LatentSync execution."""
        if self._active_job and self._active_job.status in ["pending", "downloading_code", "downloading_weights", "running"]:
            self.main_window.show_error("Execution Active", "A lip synchronization render job is currently running.")
            return

        vid_path = self.vid_entry.get().strip()
        aud_path = self.aud_entry.get().strip()

        if not vid_path or not aud_path:
            self.main_window.show_error("Validation Error", "Please specify both the presenter video and speech audio file paths.")
            return

        vid_p = Path(vid_path)
        aud_p = Path(aud_path)

        if not vid_p.exists():
            self.main_window.show_error("Validation Error", f"Base video file does not exist:\n{vid_path}")
            return
        if not aud_p.exists():
            self.main_window.show_error("Validation Error", f"Voice audio file does not exist:\n{aud_path}")
            return

        # Resolve output name
        timestamp = int(time.time())
        filename = f"lipsync_{timestamp}.mp4"
        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.workspace_dir / output_folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        out_p = output_dir / filename

        # Read configurations
        quality_selection = self.quality_opt.get()
        quality = "Fast" if "Fast" in quality_selection else "High"

        device_selection = self.device_opt.get()
        import torch
        device = "cuda" if "CUDA" in device_selection and torch.cuda.is_available() else "cpu"

        # Update log textbox
        self._write_console_log(f"--- Triggering Lip Sync ---\nQuality: {quality}\nDevice: {device}\nOutput: {filename}\n")

        # Disable buttons
        self.sync_btn.configure(state="disabled", text="Rendering...")
        self.cancel_btn.configure(state="normal")

        engine = getattr(self.main_window, "lipsync_engine", None)
        if not engine:
            self.main_window.show_error("Engine Error", "LipSyncEngine component is not registered on bootstrap.")
            self.sync_btn.configure(state="normal", text="👄 Synchronize Lips")
            self.cancel_btn.configure(state="disabled")
            return

        # Submit background worker job
        self._active_job = engine.generate_lipsync(
            presenter_video_path=vid_p,
            audio_path=aud_p,
            output_video_path=out_p,
            quality=quality,
            device=device,
            auto_download=True
        )

        self._monitor_active = True
        self._poll_progress()

    def _on_cancel_clicked(self) -> None:
        """Aborts active execution subprocess."""
        if self._active_job:
            self._write_console_log("\n[!] User triggered abort cancellation request...\n")
            engine = getattr(self.main_window, "lipsync_engine", None)
            if engine:
                engine.controller.cancel_job(self._active_job.job_id)

    def _poll_progress(self) -> None:
        """Poll job registry state, updating progress sliders, bars, and lists."""
        if not self._active_job or not self._monitor_active:
            return

        status = self._active_job.status
        progress = self._active_job.progress

        self.prog_bar.set(progress)

        # Status text mappings
        if status == "downloading_code":
            msg = f"Cloning LatentSync codebase repository... ({int(progress * 100)}%)"
        elif status == "downloading_weights":
            msg = f"Downloading U-Net & Whisper models weights checkpoints... ({int(progress * 100)}%)"
        elif status == "running":
            msg = f"Running LatentSync lip alignment frames generation... ({int(progress * 100)}%)"
        elif status == "completed":
            msg = "Mouth synchronization finished successfully! Video exported."
        elif status == "failed":
            msg = f"Process terminated. Error details:\n{self._active_job.error_message}"
        else:
            msg = "Waiting in queue..."

        self.status_lbl.configure(text=f"Status: {msg}", text_color=Theme.TEXT_PRIMARY)

        # Append messages to logs console box
        self._write_console_log(f"[{status.upper()}] Progress: {int(progress * 100)}% - {msg[:60]}...")

        if status in ["completed", "failed"]:
            self._monitor_active = False
            self.sync_btn.configure(state="normal", text="👄 Synchronize Lips")
            self.cancel_btn.configure(state="disabled")

            if status == "completed":
                self._playing_file_path = self._active_job.output_path
                self.main_window.update_status("Lip Sync output compiled successfully.")
                self._load_file_to_preview(self._playing_file_path)

                # History list update
                self._refresh_history_list()

                # Add to history manager
                self.main_window.history_mgr.add_entry(
                    project_id=self.main_window.current_project.id if self.main_window.current_project else "N/A",
                    project_name=self.main_window.current_project.name if self.main_window.current_project else "Stand-alone",
                    status="Success",
                    details=f"Lip Sync video compiled: {self._playing_file_path.name}"
                )
            else:
                self.main_window.update_status("Lip Sync rendering process failed.")
                self.main_window.show_error("Generation Failure", self._active_job.error_message or "Unknown model error.")
        else:
            self.after(300, self._poll_progress)

    def _write_console_log(self, text: str) -> None:
        """Append log trace statements to console textbox widget."""
        self.console_text.configure(state="normal")
        self.console_text.insert(tk.END, text + "\n")
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")

    def _load_file_to_preview(self, file_path: Path) -> None:
        """Configure card layout to display play buttons and names."""
        if file_path.exists():
            self._playing_file_path = file_path
            self.preview_placeholder.grid_forget()

            # Layout UI components
            self.play_btn.grid(row=0, column=0, padx=15, pady=15)
            self.play_btn.configure(text=f"▶️ Play {file_path.name[:25]}")

    def _on_play_preview(self) -> None:
        """Launches default system video media player overlay."""
        if self._playing_file_path and self._playing_file_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self._playing_file_path))
                else:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.run([opener, str(self._playing_file_path)], check=True)
            except Exception as e:
                self.main_window.show_error("Playback Error", f"Failed opening system media player: {e}")

    def _refresh_history_list(self) -> None:
        """Scan outputs folder for recently compiled synced MP4s and draw list cards."""
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.workspace_dir / output_folder_name

        if not output_dir.exists():
            return

        video_files = list(output_dir.glob("lipsync_*.mp4"))
        video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        if not video_files:
            ctk.CTkLabel(
                self.history_scroll,
                text="No exported videos found.",
                font=Theme.get_font(11, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=20)
            return

        # Show top 5 history entries
        for v_path in video_files[:5]:
            row = ctk.CTkFrame(
                self.history_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=3, ipady=3)
            row.columnconfigure(0, weight=1)

            # Details
            details_lbl = ctk.CTkLabel(
                row,
                text=v_path.name,
                font=Theme.get_font(11),
                text_color=Theme.TEXT_PRIMARY
            )
            details_lbl.grid(row=0, column=0, padx=12, pady=4, sticky="w")

            # Load to player button
            ctk.CTkButton(
                row,
                text="🎬 Load Preview",
                font=Theme.get_font(10, "bold"),
                width=100,
                height=24,
                fg_color=Theme.BG_CARD,
                text_color=Theme.TEXT_PRIMARY,
                hover_color=Theme.BG_CARD_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda path=v_path: self._load_file_to_preview(path)
            ).grid(row=0, column=1, padx=10, pady=4)
