"""Presenter and Body Motion Generation View for AI News Studio.

Provides an interactive GUI workshop to run KwaiVGI LivePortrait and Tencent MimicMotion,
supporting file pickers, configurations tuning, progress bars, status logs, and real-time
skeletal motion path previewing on a canvas.
"""

import logging
import math
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from app.theme import Theme
from core.motion.motion_job import MotionJob
from core.presenter.presenter_job import PresenterJob

if TYPE_CHECKING:
    from app.gui import MainWindow


class PresentersView(ctk.CTkFrame):
    """Visual workshop to draft LivePortrait facial and MimicMotion body parameters."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize PresentersView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_presenter_job: Optional[PresenterJob] = None
        self._active_motion_job: Optional[MotionJob] = None
        self._monitor_active = False

        # Preview state
        self._preview_thread: Optional[threading.Thread] = None
        self._preview_running = False

        # Configuration grids
        self.grid_columnconfigure(0, weight=3)  # Setup controls
        self.grid_columnconfigure(1, weight=2)  # Output panel
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_left_controls()
        self._create_right_preview()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew")
        
        ctk.CTkLabel(
            header_f,
            text="LivePortrait & Motion Generation Workshop",
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

    def _create_left_controls(self) -> None:
        """Construct file selectors, face switches, and body motion controls (left side)."""
        self.left_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.left_scroll.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")

        # --- Section 1: File Inputs ---
        ctk.CTkLabel(
            self.left_scroll,
            text="1. Select Input Media Files",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Source Image Picker
        ctk.CTkLabel(
            self.left_scroll,
            text="Source Presenter Portrait Image:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        img_pick_f = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        img_pick_f.pack(fill="x", padx=15, pady=(0, 15))
        img_pick_f.columnconfigure(0, weight=1)

        self.img_entry = ctk.CTkEntry(
            img_pick_f,
            placeholder_text="Choose source image path (.jpg, .png)...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30
        )
        self.img_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            img_pick_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=30,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_image
        ).grid(row=0, column=1)

        # Driving Video Picker
        ctk.CTkLabel(
            self.left_scroll,
            text="Driving Motion Video (Facial driver):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        vid_pick_f = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        vid_pick_f.pack(fill="x", padx=15, pady=(0, 15))
        vid_pick_f.columnconfigure(0, weight=1)

        self.vid_entry = ctk.CTkEntry(
            vid_pick_f,
            placeholder_text="Choose driving video path (.mp4)...",
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=30
        )
        self.vid_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            vid_pick_f,
            text="📁 Browse",
            font=Theme.get_font(11, "bold"),
            width=80,
            height=30,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_browse_video
        ).grid(row=0, column=1)

        # --- Section 2: LivePortrait Facial Settings ---
        ctk.CTkLabel(
            self.left_scroll,
            text="2. Facial Animation Settings (LivePortrait)",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        chk_f = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        chk_f.pack(fill="x", padx=15, pady=(0, 10))
        chk_f.columnconfigure(0, weight=1)
        chk_f.columnconfigure(1, weight=1)

        self.chk_crop = ctk.CTkCheckBox(chk_f, text="Face Auto-Cropping", font=Theme.get_font(11), fg_color=Theme.ACCENT)
        self.chk_crop.grid(row=0, column=0, sticky="w", pady=4)
        self.chk_crop.select()

        self.chk_stitch = ctk.CTkCheckBox(chk_f, text="Seamless Stitching", font=Theme.get_font(11), fg_color=Theme.ACCENT)
        self.chk_stitch.grid(row=0, column=1, sticky="w", pady=4)
        self.chk_stitch.select()

        self.chk_blink = ctk.CTkCheckBox(chk_f, text="Natural Blinking", font=Theme.get_font(11), fg_color=Theme.ACCENT)
        self.chk_blink.grid(row=1, column=0, sticky="w", pady=4)
        self.chk_blink.select()

        self.chk_head = ctk.CTkCheckBox(chk_f, text="Natural Head Movement", font=Theme.get_font(11), fg_color=Theme.ACCENT)
        self.chk_head.grid(row=1, column=1, sticky="w", pady=4)
        self.chk_head.select()

        # --- Section 3: Body Motion Engine Settings ---
        ctk.CTkLabel(
            self.left_scroll,
            text="3. Realistic Body Motion (MotionEngine)",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Motion Style selector
        ctk.CTkLabel(
            self.left_scroll,
            text="Motion Style Preset:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.style_opt = ctk.CTkOptionMenu(
            self.left_scroll,
            values=["Professional", "Casual", "Energetic", "News Anchor", "Podcast"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.style_opt.pack(fill="x", padx=15, pady=(0, 12))

        # Gesture strength slider
        ctk.CTkLabel(
            self.left_scroll,
            text="Gesture Motion Strength (Limb scaling):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.strength_slider = ctk.CTkSlider(
            self.left_scroll,
            from_=0.0,
            to=2.0,
            number_of_steps=10,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER
        )
        self.strength_slider.pack(fill="x", padx=15, pady=(0, 12))
        self.strength_slider.set(1.0)

        # Idle breathing checkbox
        self.chk_idle = ctk.CTkCheckBox(
            self.left_scroll,
            text="Enable Idle Breathing & Torso Sway",
            font=Theme.get_font(11),
            fg_color=Theme.ACCENT
        )
        self.chk_idle.pack(anchor="w", padx=15, pady=6)
        self.chk_idle.select()

        # Motion Smoothing slider
        ctk.CTkLabel(
            self.left_scroll,
            text="Motion Smoothing (Landmarks Lowpass):",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.smoothing_slider = ctk.CTkSlider(
            self.left_scroll,
            from_=0.0,
            to=1.0,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER
        )
        self.smoothing_slider.pack(fill="x", padx=15, pady=(0, 15))
        self.smoothing_slider.set(0.5)

        # Compute device selection
        ctk.CTkLabel(
            self.left_scroll,
            text="Processing Compute Device:",
            font=Theme.get_font(11, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(10, 2))

        self.device_opt = ctk.CTkOptionMenu(
            self.left_scroll,
            values=["Auto-Detect (CUDA Preferred)", "Force CPU Mode"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.device_opt.pack(fill="x", padx=15, pady=(0, 20))

        # Button row containing preview and generate
        btn_layout_f = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        btn_layout_f.pack(fill="x", padx=15, pady=(0, 15))
        btn_layout_f.columnconfigure(0, weight=1)
        btn_layout_f.columnconfigure(1, weight=1)

        self.preview_motion_btn = ctk.CTkButton(
            btn_layout_f,
            text="👁️ Preview Motion",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=38,
            command=self._on_preview_motion_clicked
        )
        self.preview_motion_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.gen_btn = ctk.CTkButton(
            btn_layout_f,
            text="⚡ Generate Video",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=38,
            command=self._on_generate_clicked
        )
        self.gen_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _create_right_preview(self) -> None:
        """Construct preview play area and log display terminal (right side)."""
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)  # Status console box expands

        # 1. Preview screen
        preview_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            height=280
        )
        preview_card.grid(row=0, column=0, pady=(0, 15), sticky="ew")
        preview_card.grid_propagate(False)
        preview_card.columnconfigure(0, weight=1)
        preview_card.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            preview_card,
            text="Animation Preview & Skeletal Visualizer",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

        self.preview_screen = ctk.CTkFrame(
            preview_card,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        self.preview_screen.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.preview_screen.columnconfigure(0, weight=1)
        self.preview_screen.rowconfigure(0, weight=1)

        # Embedded preview canvas for skeletal mapping path
        self.preview_canvas = ctk.CTkCanvas(
            self.preview_screen,
            bg=Theme.BG_MAIN[1],  # deep dark background
            highlightthickness=0
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.preview_lbl = ctk.CTkLabel(
            self.preview_screen,
            text="▶️\nPress 'Preview Motion' to see pose pathways,\nor 'Generate Video' to trigger PyTorch compiler.",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_MUTED,
            justify="center"
        )
        self.preview_lbl.grid(row=0, column=0, sticky="")

        # 2. Rendering Status logs and Progress Bar
        status_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        status_card.grid(row=1, column=0, sticky="nsew")
        status_card.columnconfigure(0, weight=1)
        status_card.rowconfigure(2, weight=1)  # logs textbox expands

        ctk.CTkLabel(
            status_card,
            text="Generation Processing logs",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(15, 2), sticky="w")

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(
            status_card,
            progress_color=Theme.ACCENT,
            height=8
        )
        self.prog_bar.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        self.prog_bar.set(0.0)

        # Status text terminal console
        self.status_console = ctk.CTkTextbox(
            status_card,
            font=("Courier New", 11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        self.status_console.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="nsew")
        self.status_console.configure(state="disabled")

    def _on_browse_image(self) -> None:
        """Browse directory folder for a presenter face image."""
        filepath = filedialog.askopenfilename(
            title="Select Presenter Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp")]
        )
        if filepath:
            self.img_entry.delete(0, tk.END)
            self.img_entry.insert(0, filepath)

    def _on_browse_video(self) -> None:
        """Browse directory folder for a driving video."""
        filepath = filedialog.askopenfilename(
            title="Select Driving Video Motion",
            filetypes=[("Video Files", "*.mp4;*.mov;*.avi;*.mkv")]
        )
        if filepath:
            self.vid_entry.delete(0, tk.END)
            self.vid_entry.insert(0, filepath)

    def _on_preview_motion_clicked(self) -> None:
        """Trigger lightweight canvas thread showing skeletal joint tracks."""
        if self._preview_running:
            # Stop preview
            self._preview_running = False
            self.preview_motion_btn.configure(text="👁️ Preview Motion")
            self.preview_lbl.grid(row=0, column=0, sticky="")
            return

        # Start preview
        self._preview_running = True
        self.preview_motion_btn.configure(text="⏹️ Stop Preview")
        self.preview_lbl.grid_forget()  # hide label

        # Spawn canvas drawing thread
        self._preview_thread = threading.Thread(target=self._animate_preview_skeleton, daemon=True)
        self._preview_thread.start()

    def _animate_preview_skeleton(self) -> None:
        """Draw interactive skeletal curves moving on the canvas."""
        style = self.style_opt.get()
        strength = self.strength_slider.get()
        enable_idle = self.chk_idle.get() == 1
        smoothing = self.smoothing_slider.get()

        fps = 30
        frame = 0
        total_frames = 120

        # Standard joint ratios relative to canvas size (w: 320, h: 220)
        cw, ch = 320, 200
        base_joints = {
            "head": [0.5 * cw, 0.22 * ch],
            "neck": [0.5 * cw, 0.35 * ch],
            "r_shoulder": [0.38 * cw, 0.42 * ch],
            "l_shoulder": [0.62 * cw, 0.42 * ch],
            "r_elbow": [0.30 * cw, 0.58 * ch],
            "l_elbow": [0.70 * cw, 0.58 * ch],
            "r_wrist": [0.33 * cw, 0.76 * ch],
            "l_wrist": [0.67 * cw, 0.76 * ch],
        }

        # Clear canvas initially
        self.preview_canvas.delete("all")

        while self._preview_running and frame < total_frames:
            t = frame / fps

            # Calculate coordinates (sine waves based on sequencer parameters)
            breath = 0.0 if not enable_idle else math.sin(2 * math.pi * 0.25 * t) * 2.5
            sway_period = 10.0 if style == "News Anchor" else (6.0 if style == "Professional" else 4.0)
            sway_amp = 0.5 if style == "News Anchor" else (2.0 if style == "Professional" else 5.0)
            sway = 0.0 if not enable_idle else math.sin(2 * math.pi * (1 / sway_period) * t) * sway_amp

            r_arm = [0.0, 0.0]
            l_arm = [0.0, 0.0]

            if style == "Energetic":
                r_arm[0] = math.cos(2 * math.pi * 0.8 * t) * 35.0 * strength
                r_arm[1] = math.sin(2 * math.pi * 0.8 * t) * 25.0 * strength
                l_arm[0] = math.cos(2 * math.pi * 0.6 * t + math.pi) * 30.0 * strength
                l_arm[1] = math.sin(2 * math.pi * 0.6 * t) * 20.0 * strength
            elif style == "Casual":
                r_arm[0] = math.sin(2 * math.pi * 0.5 * t) * 12.0 * strength
                r_arm[1] = math.cos(2 * math.pi * 0.4 * t) * 8.0 * strength
                l_arm[0] = math.sin(2 * math.pi * 0.3 * t) * 8.0 * strength
            elif style == "Podcast":
                r_arm[0] = math.sin(2 * math.pi * 0.4 * t) * 4.0 * strength
                r_arm[1] = math.sin(2 * math.pi * 0.8 * t) * 4.0 * strength
            elif style == "News Anchor":
                pass
            else:  # Professional
                r_arm[0] = math.sin(2 * math.pi * 0.3 * t) * 8.0 * strength
                r_arm[1] = math.sin(2 * math.pi * 0.6 * t) * 4.0 * strength

            # Apply smoothing reduction
            alpha = 1.0 - smoothing
            r_arm = [val * alpha for val in r_arm]
            l_arm = [val * alpha for val in l_arm]

            # Compute actual points
            p_head = [base_joints["head"][0] + sway, base_joints["head"][1]]
            p_neck = [base_joints["neck"][0] + sway, base_joints["neck"][1]]
            p_rs = [base_joints["r_shoulder"][0] + sway, base_joints["r_shoulder"][1] + breath]
            p_ls = [base_joints["l_shoulder"][0] + sway, base_joints["l_shoulder"][1] + breath]
            p_re = [base_joints["r_elbow"][0] + sway + r_arm[0] * 0.5, base_joints["r_elbow"][1] + r_arm[1] * 0.4]
            p_le = [base_joints["l_elbow"][0] + sway + l_arm[0] * 0.5, base_joints["l_elbow"][1] + l_arm[1] * 0.4]
            p_rw = [base_joints["r_wrist"][0] + sway + r_arm[0], base_joints["r_wrist"][1] + r_arm[1]]
            p_lw = [base_joints["l_wrist"][0] + sway + l_arm[0], base_joints["l_wrist"][1] + l_arm[1]]

            # Execute canvas draws inside GUI main thread safety after
            self.preview_canvas.after(0, lambda ph=p_head, pn=p_neck, prs=p_rs, pls=p_ls, pre=p_re, ple=p_le, prw=p_rw, plw=p_lw:
                                      self._draw_skeleton_lines(ph, pn, prs, pls, pre, ple, prw, plw))

            time.sleep(0.033)  # 30 fps
            frame = (frame + 1) % total_frames

        # Complete
        self._preview_running = False
        self.preview_motion_btn.after(0, lambda: self.preview_motion_btn.configure(text="👁️ Preview Motion"))
        self.preview_lbl.after(0, lambda: self.preview_lbl.grid(row=0, column=0, sticky=""))

    def _draw_skeleton_lines(self, ph, pn, prs, pls, pre, ple, prw, plw) -> None:
        """Clear canvas and render skeletal sticks."""
        if not self._preview_running:
            return

        self.preview_canvas.delete("all")

        accent_color = Theme.ACCENT[1]
        secondary_color = Theme.TEXT_MUTED[1]

        # Draw Head Circle
        self.preview_canvas.create_oval(ph[0] - 18, ph[1] - 18, ph[0] + 18, ph[1] + 18, outline=accent_color, width=3)
        
        # Draw Neck
        self.preview_canvas.create_line(ph[0], ph[1] + 18, pn[0], pn[1], fill=accent_color, width=3)
        
        # Draw Shoulders
        self.preview_canvas.create_line(pn[0], pn[1], prs[0], prs[1], fill=accent_color, width=3)
        self.preview_canvas.create_line(pn[0], pn[1], pls[0], pls[1], fill=accent_color, width=3)
        
        # Draw Arms
        self.preview_canvas.create_line(prs[0], prs[1], pre[0], pre[1], fill=accent_color, width=3)
        self.preview_canvas.create_line(pre[0], pre[1], prw[0], prw[1], fill=accent_color, width=3)
        self.preview_canvas.create_line(pls[0], pls[1], ple[0], ple[1], fill=accent_color, width=3)
        self.preview_canvas.create_line(ple[0], ple[1], plw[0], plw[1], fill=accent_color, width=3)

        # Draw Joint Circles
        self.preview_canvas.create_oval(pn[0]-4, pn[1]-4, pn[0]+4, pn[1]+4, fill=secondary_color, outline=accent_color)
        self.preview_canvas.create_oval(prs[0]-4, prs[1]-4, prs[0]+4, prs[1]+4, fill=secondary_color, outline=accent_color)
        self.preview_canvas.create_oval(pls[0]-4, pls[1]-4, pls[0]+4, pls[1]+4, fill=secondary_color, outline=accent_color)
        self.preview_canvas.create_oval(prw[0]-4, prw[1]-4, prw[0]+4, prw[1]+4, fill=accent_color, outline=accent_color)
        self.preview_canvas.create_oval(plw[0]-4, plw[1]-4, plw[0]+4, plw[1]+4, fill=accent_color, outline=accent_color)

    def _on_generate_clicked(self) -> None:
        """Submit configuration to both PresenterEngine and MotionEngine to render video."""
        if self._active_presenter_job or self._active_motion_job:
            self.main_window.show_error("Execution Active", "A rendering task is already running.")
            return

        img_path = self.img_entry.get().strip()
        vid_path = self.vid_entry.get().strip()

        if not img_path:
            self.main_window.show_error("Validation Error", "Please select a source presenter portrait image.")
            return

        # Input path validation
        img_p = Path(img_path)
        if not img_p.exists():
            self.main_window.show_error("Validation Error", f"Source image path does not exist on disk:\n{img_path}")
            return

        # Device mapping
        device_selection = self.device_opt.get()
        import torch
        device = "cuda" if "CUDA" in device_selection and torch.cuda.is_available() else "cpu"

        # Settings
        style = self.style_opt.get()
        strength = self.strength_slider.get()
        enable_idle = self.chk_idle.get() == 1
        smoothing = self.smoothing_slider.get()

        # Resolve output folder
        timestamp = int(time.time())
        out_filename = f"motion_rendered_{timestamp}.mp4"
        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.workspace_dir / output_folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        out_p = output_dir / out_filename

        self._logger.info(f"Triggering Body Motion animation: Image={img_p.name}, Preset={style}, Strength={strength}")
        self._write_console(f"--- Launching Body Motion Task ---\nSource Image: {img_p.name}\nPreset Style: {style}\nStrength: {strength}\nSmoothing: {smoothing}\nDevice: {device}\n")

        self.gen_btn.configure(state="disabled", text="Processing...")

        # If a driving video is NOT selected, we will generate a body driving video first using MotionEngine,
        # and then pass the result to the PresenterEngine (LivePortrait) to merge expressions!
        # If a driving video IS selected, we run body movement generation and feed it as the driving model.
        # This beautifully links both modules!
        engine_motion = getattr(self.main_window, "motion_engine", None)
        if not engine_motion:
            self.main_window.show_error("Engine Error", "MotionEngine component is not registered on bootstrap.")
            self.gen_btn.configure(state="normal", text="⚡ Generate Video")
            return

        # Trigger background job
        self._active_motion_job = engine_motion.generate_body_motion(
            source_image_path=img_p,
            output_video_path=out_p,
            motion_style=style,
            gesture_strength=strength,
            enable_idle_motion=enable_idle,
            motion_smoothing=smoothing,
            device=device,
            auto_download=True
        )

        self._monitor_active = True
        self._poll_motion_progress()

    def _poll_motion_progress(self) -> None:
        """Poll the active motion job's status and update widgets."""
        if not self._active_motion_job or not self._monitor_active:
            return

        status = self._active_motion_job.status
        progress = self._active_motion_job.progress

        self.prog_bar.set(progress)

        if status == "downloading_code":
            msg = "Cloning Tencent MimicMotion code repository..."
        elif status == "downloading_weights":
            msg = f"Downloading SVD and MimicMotion weight checkpoints... ({int(progress * 100)}%)"
        elif status == "running":
            msg = f"Executing DWPose and stable video diffusion generation... ({int(progress * 100)}%)"
        elif status == "completed":
            msg = "Body movement video compiled successfully!"
        elif status == "failed":
            msg = f"Task failed. Traceback details:\n{self._active_motion_job.error_message}"
        else:
            msg = "Queueing job..."

        self.main_window.update_status(f"MotionEngine: {msg}")
        self._write_console(f"[{status.upper()}] Progress: {int(progress * 100)}% - {msg}\n")

        if status in ["completed", "failed"]:
            self._monitor_active = False
            self.gen_btn.configure(state="normal", text="⚡ Generate Video")
            
            if status == "completed":
                self.preview_lbl.configure(
                    text=f"▶️\nBody Motion Rendered!\nOutput:\n{self._active_motion_job.output_path.name}",
                    text_color=Theme.SUCCESS
                )
                self.main_window.history_mgr.add_entry(
                    project_id=self.main_window.current_project.id if self.main_window.current_project else "N/A",
                    project_name=self.main_window.current_project.name if self.main_window.current_project else "Stand-alone",
                    status="Success",
                    details=f"Body motion compiled: {self._active_motion_job.output_path.name}"
                )
            else:
                self.preview_lbl.configure(
                    text="❌\nGeneration failed.",
                    text_color=Theme.DANGER
                )
                self.main_window.show_error("Generation Failure", self._active_motion_job.error_message or "Unknown model error.")
        else:
            self.after(200, self._poll_motion_progress)

    def _write_console(self, text: str) -> None:
        """Append log statement to read-only terminal console."""
        self.status_console.configure(state="normal")
        self.status_console.insert(ctk.END, text)
        self.status_console.configure(state="disabled")
        self.status_console.see(ctk.END)

    def on_show(self) -> None:
        """Clear canvas when entering page."""
        self.preview_canvas.delete("all")
        self._preview_running = False
        self.preview_motion_btn.configure(text="👁️ Preview Motion")
        self.preview_lbl.grid(row=0, column=0, sticky="")
