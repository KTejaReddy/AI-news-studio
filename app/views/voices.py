"""Voices View Dashboard for AI News Studio.

Provides an interactive studio to clone speakers voices via F5-TTS, manage reusable
voice profiles, transcribe reference clips, synthesize speech, play outputs natively,
and draw WAV waveforms on a canvas.
"""

import logging
from pathlib import Path
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import customtkinter as ctk
import numpy as np

from app.theme import Theme
from core.voice.voice_job import VoiceJob
from core.voice.voice_profile import VoiceProfile

# Winsound is native to Windows OS
if sys.platform == "win32":
    import winsound
else:
    winsound = None

if TYPE_CHECKING:
    from app.gui import MainWindow


class VoiceProfileDialog(ctk.CTkToplevel):
    """Modal dialog for creating a new voice clone profile."""

    def __init__(self, parent: ctk.CTkFrame, on_save_callback: Callable[[str, str, Path], None]) -> None:
        """Initialize the dialog.

        Args:
            parent: Parent frame reference.
            on_save_callback: Callback triggered when profile is successfully compiled.
        """
        super().__init__(parent)
        self.on_save = on_save_callback

        self.title("Create Voice Clone Profile")
        self.geometry("500x340")
        self.resizable(False, False)
        
        # Center relative to parent
        self.transient(parent.winfo_toplevel())
        self.update_idletasks()
        px = parent.winfo_toplevel().winfo_x()
        py = parent.winfo_toplevel().winfo_y()
        pw = parent.winfo_toplevel().winfo_width()
        ph = parent.winfo_toplevel().winfo_height()
        self.geometry(f"+{px + (pw - 500) // 2}+{py + (ph - 340) // 2}")

        self.configure(fg_color=Theme.BG_CARD)
        self.columnconfigure(0, weight=1)

        # Content
        ctk.CTkLabel(
            self,
            text="🎙️ Train Voice Clone Profile",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=20, pady=(20, 10))

        # Profile Name
        ctk.CTkLabel(
            self,
            text="Speaker Profile Name:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=20, pady=(5, 2))

        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="e.g. Rachel - Cloned Voice",
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30
        )
        self.name_entry.pack(fill="x", padx=20, pady=(0, 10))

        # Audio file selector
        ctk.CTkLabel(
            self,
            text="Reference Audio Recording (WAV/MP3, 10-15s recommended):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=20, pady=(5, 2))

        aud_pick_f = ctk.CTkFrame(self, fg_color="transparent")
        aud_pick_f.pack(fill="x", padx=20, pady=(0, 10))
        aud_pick_f.columnconfigure(0, weight=1)

        self.aud_entry = ctk.CTkEntry(
            aud_pick_f,
            placeholder_text="Choose WAV or MP3 recording...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30
        )
        self.aud_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            aud_pick_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=30,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse
        ).grid(row=0, column=1)

        # Audio Transcript
        ctk.CTkLabel(
            self,
            text="Exact Audio Transcript Text:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=20, pady=(5, 2))

        self.trans_entry = ctk.CTkEntry(
            self,
            placeholder_text="Type all spoken words in the reference audio clip...",
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30
        )
        self.trans_entry.pack(fill="x", padx=20, pady=(0, 20))

        # Bottom row buttons
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_f,
            text="Cancel",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            width=90,
            command=self.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_f,
            text="💾 Save Profile",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            width=110,
            command=self._on_save_clicked
        ).pack(side="right")

    def _on_browse(self) -> None:
        """File dialog picker."""
        filepath = filedialog.askopenfilename(
            title="Select Speaker Audio Sample",
            filetypes=[("Audio Files", "*.wav;*.mp3")]
        )
        if filepath:
            self.aud_entry.delete(0, tk.END)
            self.aud_entry.insert(0, filepath)

    def _on_save_clicked(self) -> None:
        """Validate and trigger callback."""
        name = self.name_entry.get().strip()
        aud = self.aud_entry.get().strip()
        trans = self.trans_entry.get().strip()

        if not name or not aud or not trans:
            messagebox.showerror("Validation Error", "All fields are required to clone a voice.")
            return

        aud_p = Path(aud)
        if not aud_p.exists():
            messagebox.showerror("Validation Error", "Selected sample path does not exist on disk.")
            return

        self.on_save(name, trans, aud_p)
        self.destroy()


class VoicesView(ctk.CTkFrame):
    """Workspace providing profiles management, speech synthesis inputs, and waveforms."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize VoicesView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_profile: Optional[VoiceProfile] = None
        self._active_job: Optional[VoiceJob] = None
        self._monitor_active = False

        self._is_playing = False
        self._playing_file_path: Optional[Path] = None

        # Configuration grids
        self.grid_columnconfigure(0, weight=2)  # Profiles Manager
        self.grid_columnconfigure(1, weight=3)  # Synthesis workshop
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_left_profiles()
        self._create_right_workshop()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew")
        
        ctk.CTkLabel(
            header_f,
            text="F5-TTS Voice Cloning Workshop",
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

    def _create_left_profiles(self) -> None:
        """Construct the voice profiles list manager (left side)."""
        left_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        left_frame.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")
        
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)  # profiles scroll expands

        ctk.CTkLabel(
            left_frame,
            text="Voice Profiles Registry",
            font=Theme.get_font(15, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

        # Scroll list
        self.profiles_scroll = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
        self.profiles_scroll.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # Add profile button
        ctk.CTkButton(
            left_frame,
            text="🎙️ Train Voice Profile",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=36,
            command=self._on_create_profile_clicked
        ).grid(row=2, column=0, padx=15, pady=15, sticky="ew")

    def _create_right_workshop(self) -> None:
        """Construct speech text editor, progress tracker, and audio preview player (right side)."""
        self.right_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.right_scroll.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")

        # --- Sub-section 1: Active profile ---
        self.active_profile_lbl = ctk.CTkLabel(
            self.right_scroll,
            text="Selected Speaker: [None - Select from Left]",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.ACCENT
        )
        self.active_profile_lbl.pack(anchor="w", padx=15, pady=(15, 10))

        # --- Sub-section 2: Script Text Input ---
        ctk.CTkLabel(
            self.right_scroll,
            text="Generate Speech Script:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.script_text = ctk.CTkTextbox(
            self.right_scroll,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 2,
            height=120
        )
        self.script_text.pack(fill="x", padx=15, pady=(0, 12))
        self.script_text.insert("1.0", "Type your voice broadcast script here. F5-TTS will generate speech using the cloned speaker profile details.")

        # Controls row
        ctrl_f = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        ctrl_f.pack(fill="x", padx=15, pady=(0, 15))
        ctrl_f.columnconfigure(0, weight=1)

        # Compute device
        self.device_opt = ctk.CTkOptionMenu(
            ctrl_f,
            values=["Auto-Detect (CUDA Preferred)", "Force CPU Mode"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=30
        )
        self.device_opt.grid(row=0, column=0, sticky="w")

        # Generate Button
        self.gen_btn = ctk.CTkButton(
            ctrl_f,
            text="🔊 Generate Speech",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30,
            command=self._on_generate_clicked
        )
        self.gen_btn.grid(row=0, column=1, sticky="e")

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(
            self.right_scroll,
            progress_color=Theme.ACCENT,
            height=8
        )
        self.prog_bar.pack(fill="x", padx=15, pady=(0, 15))
        self.prog_bar.set(0.0)

        # --- Sub-section 3: Audio Preview Player & Waveform ---
        player_card = ctk.CTkFrame(
            self.right_scroll,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        player_card.pack(fill="x", padx=15, pady=(0, 15))
        player_card.columnconfigure(1, weight=1)

        # Play/Pause button
        self.play_btn = ctk.CTkButton(
            player_card,
            text="▶️ Play",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=40,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            state="disabled",
            command=self._on_play_clicked
        )
        self.play_btn.grid(row=0, column=0, padx=15, pady=15)

        # Waveform Display Canvas
        self.waveform_canvas = ctk.CTkCanvas(
            player_card,
            bg=Theme.BG_MAIN[1],
            highlightthickness=0,
            height=60
        )
        self.waveform_canvas.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="ew")

        # Details
        self.audio_filename_lbl = ctk.CTkLabel(
            player_card,
            text="No audio compiled.",
            font=Theme.get_font(10),
            text_color=Theme.TEXT_MUTED
        )
        self.audio_filename_lbl.grid(row=1, column=1, padx=(0, 15), pady=(0, 10), sticky="w")

        # --- Sub-section 4: History list ---
        ctk.CTkLabel(
            self.right_scroll,
            text="Speech Generation History:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        self.history_f = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        self.history_f.pack(fill="x", padx=15, pady=(0, 15))

    def on_show(self) -> None:
        """Triggered automatically when pageFocused."""
        self._refresh_profiles_list()
        self._refresh_history_list()

    def _refresh_profiles_list(self) -> None:
        """Fetch profiles data files and compile left list rows."""
        for widget in self.profiles_scroll.winfo_children():
            widget.destroy()

        engine = getattr(self.main_window, "voice_engine", None)
        if not engine:
            return

        profiles = engine.list_profiles()
        
        if not profiles:
            ctk.CTkLabel(
                self.profiles_scroll,
                text="No voice profiles trained.\nClick Train Voice Profile below.",
                font=Theme.get_font(11, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=40)
            return

        for p in profiles:
            row = ctk.CTkFrame(
                self.profiles_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=4, ipady=4)
            row.columnconfigure(0, weight=1)

            # Details
            details_f = ctk.CTkFrame(row, fg_color="transparent")
            details_f.grid(row=0, column=0, padx=12, pady=5, sticky="w")

            is_active = self._active_profile and self._active_profile.profile_id == p.profile_id
            name_color = Theme.ACCENT if is_active else Theme.TEXT_PRIMARY
            name_suffix = " (Active)" if is_active else ""

            ctk.CTkLabel(
                details_f,
                text=f"{p.name}{name_suffix}",
                font=Theme.get_font(12, "bold"),
                text_color=name_color
            ).pack(anchor="w")

            # Reference audio snippet
            snippet = f"Sample text: \"{p.ref_text[:30]}...\"" if len(p.ref_text) > 30 else f"Sample: \"{p.ref_text}\""
            ctk.CTkLabel(
                details_f,
                text=snippet,
                font=Theme.get_font(10),
                text_color=Theme.TEXT_MUTED
            ).pack(anchor="w")

            # Action Buttons Row
            actions_f = ctk.CTkFrame(row, fg_color="transparent")
            actions_f.grid(row=0, column=1, padx=10, pady=5, sticky="e")

            # Select
            ctk.CTkButton(
                actions_f,
                text="✓ Select" if is_active else "Select",
                font=Theme.get_font(10, "bold"),
                width=65,
                height=24,
                state="disabled" if is_active else "normal",
                fg_color=Theme.SUCCESS if is_active else Theme.ACCENT,
                hover_color=Theme.ACCENT_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda prof=p: self._on_select_profile(prof)
            ).pack(side="left", padx=2)

            # Delete
            ctk.CTkButton(
                actions_f,
                text="🗑️",
                font=Theme.get_font(10),
                width=24,
                height=24,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda p_id=p.profile_id: self._on_delete_profile(p_id)
            ).pack(side="left", padx=2)

    def _on_select_profile(self, profile: VoiceProfile) -> None:
        """Update active profile state context."""
        self._active_profile = profile
        self.active_profile_lbl.configure(text=f"Selected Speaker: {profile.name}")
        self._refresh_profiles_list()

    def _on_delete_profile(self, profile_id: str) -> None:
        """Remove voice profile from disk folder."""
        if self._active_profile and self._active_profile.profile_id == profile_id:
            self._active_profile = None
            self.active_profile_lbl.configure(text="Selected Speaker: [None - Select from Left]")

        engine = getattr(self.main_window, "voice_engine", None)
        if engine and engine.delete_profile(profile_id):
            self._refresh_profiles_list()
            self.main_window.update_status("Voice profile removed.")

    def _on_create_profile_clicked(self) -> None:
        """Pops up the trainer sample upload dialog box."""
        dialog = VoiceProfileDialog(self, on_save_callback=self._on_save_profile)
        dialog.grab_set()

    def _on_save_profile(self, name: str, ref_text: str, audio_path: Path) -> None:
        """Callback from dialog: save profile to folder."""
        engine = getattr(self.main_window, "voice_engine", None)
        if engine:
            try:
                # Engine create profile handles copying/folder creation
                engine.create_profile(name=name, ref_text=ref_text, ref_audio_path=audio_path)
                self._refresh_profiles_list()
                self.main_window.update_status(f"Voice Profile '{name}' trained successfully.")
            except Exception as e:
                self._logger.error(f"Failed creating profile: {e}")
                self.main_window.show_error("Training Failure", f"Failed to register voice profile: {e}")

    def _on_generate_clicked(self) -> None:
        """Queues speech synthesis task in VoiceEngine."""
        if self._active_job and self._active_job.status in ["pending", "downloading_weights", "running"]:
            self.main_window.show_error("Execution Active", "A voice generation task is already running.")
            return

        if not self._active_profile:
            self.main_window.show_error("Validation Error", "Please select a cloned voice profile from the left list.")
            return

        script = self.script_text.get("1.0", tk.END).strip()
        if not script:
            self.main_window.show_error("Validation Error", "Script text box cannot be empty.")
            return

        # Resolve output path
        timestamp = int(time.time())
        filename = f"speech_{self._active_profile.profile_id[:8]}_{timestamp}.wav"
        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.config_mgr.workspace_dir / output_folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        out_p = output_dir / filename

        # Compute device selection
        device_selection = self.device_opt.get()
        import torch
        device = "cuda" if "CUDA" in device_selection and torch.cuda.is_available() else "cpu"

        self._logger.info(f"Triggering Speech Synthesis: Speaker={self._active_profile.name}, device={device}")
        
        # Disable buttons
        self.gen_btn.configure(state="disabled", text="Synthesizing...")

        engine = getattr(self.main_window, "voice_engine", None)
        if not engine:
            self.main_window.show_error("Engine Error", "VoiceEngine component is not registered on bootstrap.")
            self.gen_btn.configure(state="normal", text="🔊 Generate Speech")
            return

        # Submit background worker job
        self._active_job = engine.generate_cloned_speech(
            profile=self._active_profile,
            script_text=script,
            output_audio_path=out_p,
            device=device,
            auto_download=True
        )

        self._monitor_active = True
        self._poll_progress()

    def _poll_progress(self) -> None:
        """Poll the active job status and update the progress bar and logs."""
        if not self._active_job or not self._monitor_active:
            return

        status = self._active_job.status
        progress = self._active_job.progress

        self.prog_bar.set(progress)

        if status == "downloading_weights":
            msg = f"Downloading F5-TTS / Vocoder models checkpoints... ({int(progress * 100)}%)"
        elif status == "running":
            msg = f"Running Flow Matching Speech Synthesis segments... ({int(progress * 100)}%)"
        elif status == "completed":
            msg = "Speech compilation complete! Final audio exported as WAV."
        elif status == "failed":
            msg = f"Synthesis crashed. Traceback details:\n{self._active_job.error_message}"
        else:
            msg = "Waiting in queue..."

        self.main_window.update_status(f"VoiceEngine: {msg}")

        if status in ["completed", "failed"]:
            self._monitor_active = False
            self.gen_btn.configure(state="normal", text="🔊 Generate Speech")
            
            if status == "completed":
                # Enable playback and draw waveform
                self.play_btn.configure(state="normal", text="▶️ Play")
                self._playing_file_path = self._active_job.output_path
                self.audio_filename_lbl.configure(
                    text=f"WAV Exported: {self._playing_file_path.name} ({round(self._playing_file_path.stat().st_size / (1024*1024), 2)} MB)",
                    text_color=Theme.SUCCESS
                )
                self._draw_waveform_canvas(self._playing_file_path)
                
                # Register in history
                self._refresh_history_list()
                
                self.main_window.history_mgr.add_entry(
                    project_id=self.main_window.current_project.id if self.main_window.current_project else "N/A",
                    project_name=self.main_window.current_project.name if self.main_window.current_project else "Stand-alone",
                    status="Success",
                    details=f"Speech audio compiled: {self._playing_file_path.name}"
                )
            else:
                self.play_btn.configure(state="disabled", text="▶️ Play")
                self.audio_filename_lbl.configure(text="Generation failed.", text_color=Theme.DANGER)
                self.main_window.show_error("Generation Failure", self._active_job.error_message or "Unknown model error.")
        else:
            self.after(200, self._poll_progress)

    def _on_play_clicked(self) -> None:
        """Trigger winsound async background playback of compiled audio."""
        if not self._playing_file_path or not self._playing_file_path.exists():
            return

        if winsound is None:
            self.main_window.show_error("Platform Error", "Audio playback utilizes winsound, which is only supported on Windows.")
            return

        if self._is_playing:
            # Stop
            winsound.PlaySound(None, winsound.SND_PURGE)
            self._is_playing = False
            self.play_btn.configure(text="▶️ Play")
        else:
            # Play in background
            try:
                winsound.PlaySound(str(self._playing_file_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                self._is_playing = True
                self.play_btn.configure(text="⏹️ Stop")
                
                # Stop toggle thread based on length
                # winsound does not offer a direct playing status. We can schedule stopping back to play state
                # by measuring file length or approximate time.
                # A simple approximation: check wav duration and schedule stop trigger
                duration_ms = self._get_wav_duration_ms(self._playing_file_path)
                self.after(duration_ms, self._reset_play_state)
            except Exception as e:
                self._logger.error(f"Error playing audio: {e}")
                self.main_window.show_error("Playback Error", f"Failed playing file: {e}")

    def _reset_play_state(self) -> None:
        """Timer callback when audio completes playing."""
        if self._is_playing:
            self._is_playing = False
            self.play_btn.configure(text="▶️ Play")

    def _get_wav_duration_ms(self, wav_path: Path) -> int:
        """Calculate WAV audio file duration in milliseconds.

        Args:
            wav_path: Audio file path.

        Returns:
            Duration in milliseconds.
        """
        import wave
        try:
            with wave.open(str(wav_path), "rb") as f:
                frames = f.getnframes()
                rate = f.getframerate()
                duration = frames / float(rate)
                return int(duration * 1000)
        except Exception:
            return 8000  # fallback 8 seconds

    def _draw_waveform_canvas(self, wav_path: Path) -> None:
        """Parse WAV frames and draw amplitude visual bars on the canvas.

        Args:
            wav_path: WAV audio file path.
        """
        import wave
        try:
            with wave.open(str(wav_path), "rb") as f:
                params = f.getparams()
                nchannels, sampwidth, framerate, nframes = params[:4]
                str_data = f.readframes(nframes)
                
            # Convert to numpy int16 array
            if sampwidth == 2:
                data = np.frombuffer(str_data, dtype=np.int16)
            elif sampwidth == 1:
                data = np.frombuffer(str_data, dtype=np.uint8) - 128
            else:
                return

            canvas_w = 320
            canvas_h = 60
            self.waveform_canvas.delete("all")

            # Calculate amplitude peaks subsampled to fit width
            chunk_size = len(data) // canvas_w
            if chunk_size < 1:
                chunk_size = 1

            accent_color = Theme.ACCENT[1]
            cy = canvas_h // 2

            for i in range(canvas_w):
                chunk = data[i * chunk_size : (i + 1) * chunk_size]
                if len(chunk) == 0:
                    break
                peak = np.max(np.abs(chunk))
                # Scale peak relative to canvas height
                h = int((peak / 32768.0) * (canvas_h / 2) * 1.5)
                h = min(h, canvas_h // 2)

                self.waveform_canvas.create_line(i, cy - h, i, cy + h, fill=accent_color, width=1)
        except Exception as e:
            self._logger.error(f"Error drawing waveform: {e}")

    def _refresh_history_list(self) -> None:
        """Scan outputs folder for recently compiled WAVs and draw list cards."""
        for widget in self.history_f.winfo_children():
            widget.destroy()

        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.config_mgr.workspace_dir / output_folder_name

        if not output_dir.exists():
            return

        wav_files = list(output_dir.glob("speech_*.wav"))
        # Sort newest first
        wav_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        if not wav_files:
            ctk.CTkLabel(
                self.history_f,
                text="No exported audios found.",
                font=Theme.get_font(11, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=10)
            return

        # Show top 4 history entries
        for w_path in wav_files[:4]:
            row = ctk.CTkFrame(
                self.history_f,
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
                text=w_path.name,
                font=Theme.get_font(11),
                text_color=Theme.TEXT_PRIMARY
            )
            details_lbl.grid(row=0, column=0, padx=12, pady=4, sticky="w")

            # Load to player button
            ctk.CTkButton(
                row,
                text="🎵 Load to Player",
                font=Theme.get_font(10, "bold"),
                width=100,
                height=24,
                fg_color=Theme.BG_CARD,
                text_color=Theme.TEXT_PRIMARY,
                hover_color=Theme.BG_CARD_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda path=w_path: self._load_file_to_player(path)
            ).grid(row=0, column=1, padx=10, pady=4)

    def _load_file_to_player(self, file_path: Path) -> None:
        """Load a historic WAV file directly into active player."""
        if file_path.exists():
            self._playing_file_path = file_path
            self.play_btn.configure(state="normal", text="▶️ Play")
            self.audio_filename_lbl.configure(
                text=f"Loaded from history: {file_path.name} ({round(file_path.stat().st_size / (1024*1024), 2)} MB)",
                text_color=Theme.TEXT_SECONDARY
            )
            self._draw_waveform_canvas(file_path)
            self.main_window.update_status(f"Loaded audio: {file_path.name}")
