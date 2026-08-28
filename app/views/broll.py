"""B-roll Library View for AI News Studio.

Provides an interactive studio to generate B-roll media from scenes narration,
select diffusion providers, search and filter the local Asset Library registry,
import local files, and monitor background render queues.
"""

import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING, List, Optional
import os

import customtkinter as ctk
from PIL import Image

from app.theme import Theme
from core.director.scene_plan import ScenePlan
from core.broll.scene_asset import SceneAsset
from core.broll.broll_config import BrollConfig
from core.broll.broll_job import BrollJob
from core.broll.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from app.gui import MainWindow


class BrollView(ctk.CTkFrame):
    """Visual workshop viewport managing B-roll generation workflows and asset library catalogs."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize BrollView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self.selected_scene: Optional[ScenePlan] = None
        self.selected_asset: Optional[SceneAsset] = None
        
        # State tracking for polling progress
        self._poll_active = False

        # Grid configuration: 3 columns: Scene list, Generator/Preview, Library/Queue
        self.grid_columnconfigure(0, weight=1, minsize=260)  # Sidebar Scene list
        self.grid_columnconfigure(1, weight=2, minsize=420)  # Core generator & Preview
        self.grid_columnconfigure(2, weight=1, minsize=300)  # Library index & Queue
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_left_scenes_sidebar()
        self._create_center_generator()
        self._create_right_library_panel()

        # Start job queue poller loop
        self._start_queue_monitoring()

    def _create_header(self) -> None:
        """Create view title banner."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(
            header_f,
            text="Cinematic B-Roll Workshop & Asset Library",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # Status badge
        ctk.CTkLabel(
            header_f,
            text=" (Media Diffusers Connected)",
            font=Theme.get_font(12, "italic"),
            text_color=Theme.SUCCESS
        ).pack(side="left", padx=5, pady=(8, 0))

    def _create_left_scenes_sidebar(self) -> None:
        """Construct the storyboard scenes selector panel (column 0)."""
        sidebar = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        sidebar.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="🎬 Project Storyboard Scenes",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

        # Scrollable container for scene cards
        self.scenes_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.scenes_scroll.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="nsew")
        
        self.scene_card_widgets: List[ctk.CTkFrame] = []

    def _create_center_generator(self) -> None:
        """Construct the prompt editor, previewer, and generation triggers (column 1)."""
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=1, column=1, padx=10, pady=(0, 20), sticky="nsew")
        center_frame.grid_columnconfigure(0, weight=1)
        center_frame.grid_rowconfigure(0, weight=3) # Preview area
        center_frame.grid_rowconfigure(1, weight=4) # Form editors

        # 1. Preview screen
        self.preview_card = ctk.CTkFrame(
            center_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.preview_card.grid(row=0, column=0, pady=(0, 10), sticky="nsew")
        self.preview_card.grid_columnconfigure(0, weight=1)
        self.preview_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.preview_card,
            text="🖥️ Visual Asset Preview",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

        self.preview_area = ctk.CTkFrame(
            self.preview_card,
            fg_color=Theme.BG_MAIN,
            corner_radius=Theme.CORNER_RADIUS - 4,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.preview_area.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.preview_area.grid_columnconfigure(0, weight=1)
        self.preview_area.grid_rowconfigure(0, weight=1)

        self.preview_placeholder_lbl = ctk.CTkLabel(
            self.preview_area,
            text="🎞️ No Scene Selected\nSelect a scene from the left to view or generate its B-roll background asset.",
            font=Theme.get_font(12),
            text_color=Theme.TEXT_MUTED,
            justify="center"
        )
        self.preview_placeholder_lbl.grid(row=0, column=0, sticky="")

        # 2. Settings form
        self.form_card = ctk.CTkFrame(
            center_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.form_card.grid(row=1, column=0, pady=(10, 0), sticky="nsew")
        self.form_card.grid_columnconfigure(0, weight=1)
        self.form_card.grid_rowconfigure(2, weight=1) # prompt text expands

        ctk.CTkLabel(
            self.form_card,
            text="⚙️ Visual Prompt Configuration",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

        # Config grid row
        self.form_grid = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.form_grid.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        self.form_grid.columnconfigure(0, weight=1)
        self.form_grid.columnconfigure(1, weight=1)
        self.form_grid.columnconfigure(2, weight=1)

        # Provider selector
        ctk.CTkLabel(self.form_grid, text="Provider Driver:", font=Theme.get_font(10, "bold"), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=2)
        self.provider_opt = ctk.CTkOptionMenu(
            self.form_grid,
            values=["Gemini Flow", "Veo", "Runway", "Pika", "Luma", "Kling", "Hailuo", "Local ComfyUI", "Stable Diffusion", "Flux", "Fu"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=26,
            command=self._on_provider_changed
        )
        self.provider_opt.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 8))

        # Asset Type selector
        ctk.CTkLabel(self.form_grid, text="Asset Format:", font=Theme.get_font(10, "bold"), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=1, sticky="w", padx=2)
        self.type_opt = ctk.CTkOptionMenu(
            self.form_grid,
            values=["Video", "Image", "Motion Graphic", "Animation", "Stock Footage"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=26
        )
        self.type_opt.grid(row=1, column=1, sticky="ew", padx=2, pady=(0, 8))

        # Aspect Ratio Selector
        ctk.CTkLabel(self.form_grid, text="Aspect Shape:", font=Theme.get_font(10, "bold"), text_color=Theme.TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=2)
        self.aspect_opt = ctk.CTkOptionMenu(
            self.form_grid,
            values=["16:9", "9:16", "1:1"],
            font=Theme.get_font(11),
            dropdown_font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD,
            height=26
        )
        self.aspect_opt.grid(row=1, column=2, sticky="ew", padx=2, pady=(0, 8))

        # Visual Prompt Text Box
        ctk.CTkLabel(
            self.form_card,
            text="Cinematic Prompt Text Description:",
            font=Theme.get_font(10, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).grid(row=2, column=0, padx=15, pady=(5, 2), sticky="w")

        self.prompt_text = ctk.CTkTextbox(
            self.form_card,
            font=Theme.get_font(11),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        self.prompt_text.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # Action Buttons frame
        act_f = ctk.CTkFrame(self.form_card, fg_color="transparent")
        act_f.grid(row=4, column=0, padx=15, pady=(0, 15), sticky="ew")
        act_f.columnconfigure(0, weight=1)
        act_f.columnconfigure(1, weight=1)
        act_f.columnconfigure(2, weight=1)

        self.generate_btn = ctk.CTkButton(
            act_f,
            text="🎞️ Generate B-Roll",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            height=30,
            command=self._on_generate_broll_clicked
        )
        self.generate_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.import_btn = ctk.CTkButton(
            act_f,
            text="📁 Import Local",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            height=30,
            command=self._on_import_clicked
        )
        self.import_btn.grid(row=0, column=1, padx=4, sticky="ew")

        self.delete_btn = ctk.CTkButton(
            act_f,
            text="🗑️ Delete Asset",
            font=Theme.get_font(11, "bold"),
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER,
            height=30,
            command=self._on_delete_clicked
        )
        self.delete_btn.grid(row=0, column=2, padx=(4, 0), sticky="ew")

        # Disable fields initially
        self._set_editor_state(False)

    def _create_right_library_panel(self) -> None:
        """Construct the library visual catalog grid and progress queue console (column 2)."""
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=2, padx=(10, 20), pady=(0, 20), sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=3) # Library catalog card
        right_frame.grid_rowconfigure(1, weight=2) # Progress Queue card

        # 1. Global Library Catalog Card
        self.catalog_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.catalog_card.grid(row=0, column=0, pady=(0, 10), sticky="nsew")
        self.catalog_card.grid_columnconfigure(0, weight=1)
        self.catalog_card.grid_rowconfigure(2, weight=1) # grid catalog expands

        ctk.CTkLabel(
            self.catalog_card,
            text="🎞️ Global Asset Library Index",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(12, 4), sticky="w")

        # Search Bar
        search_f = ctk.CTkFrame(self.catalog_card, fg_color="transparent")
        search_f.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="ew")
        search_f.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_f,
            placeholder_text="Search prompt keywords...",
            font=Theme.get_font(10),
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            height=24
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_library_grid())

        # Category Filter dropdown
        self.cat_filter_opt = ctk.CTkOptionMenu(
            search_f,
            values=["All Assets", "Video", "Image", "Motion Graphic", "Animation", "Stock Footage"],
            font=Theme.get_font(10),
            width=90,
            height=24,
            command=lambda val: self._refresh_library_grid()
        )
        self.cat_filter_opt.grid(row=0, column=1, sticky="e")

        # Scrollable Grid of assets
        self.library_scroll = ctk.CTkScrollableFrame(self.catalog_card, fg_color="transparent")
        self.library_scroll.grid(row=2, column=0, padx=10, pady=(0, 15), sticky="nsew")

        # 2. Progress Queue Monitor Card
        self.queue_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.queue_card.grid(row=1, column=0, pady=(10, 0), sticky="nsew")
        self.queue_card.grid_columnconfigure(0, weight=1)
        self.queue_card.grid_rowconfigure(1, weight=1) # Queue list expands

        ctk.CTkLabel(
            self.queue_card,
            text="⏳ Background Render Queues",
            font=Theme.get_font(13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(12, 4), sticky="w")

        self.queue_scroll = ctk.CTkScrollableFrame(self.queue_card, fg_color="transparent")
        self.queue_scroll.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="nsew")

    def on_show(self) -> None:
        """Triggered automatically when the view page focused."""
        self._refresh_scenes_list()
        self._refresh_library_grid()
        self._refresh_preview_and_controls()
        # Restart the queue monitor loop if it was stopped while the view was hidden
        if not self._poll_active:
            self._start_queue_monitoring()

    def _set_editor_state(self, enabled: bool) -> None:
        """Helper to toggle interactive fields edit status."""
        state = "normal" if enabled else "disabled"
        self.prompt_text.configure(state=state)
        self.provider_opt.configure(state=state)
        self.type_opt.configure(state=state)
        self.aspect_opt.configure(state=state)
        self.generate_btn.configure(state=state)
        self.import_btn.configure(state=state)
        self.delete_btn.configure(state=state)

    def _refresh_scenes_list(self) -> None:
        """Query Director View for storyboard timeline plans and redraw the sidebar."""
        for widget in self.scenes_scroll.winfo_children():
            widget.destroy()
        self.scene_card_widgets.clear()

        director_view = getattr(self.main_window.views.get("director"), "_active_timeline", None)
        scenes = director_view.scenes if director_view else []

        if not scenes:
            lbl = ctk.CTkLabel(
                self.scenes_scroll,
                text="⚠️ No storyboard scenes.\nGo to AI Director page\nand analyze script narration first.",
                font=Theme.get_font(11),
                text_color=Theme.TEXT_MUTED,
                justify="center"
            )
            lbl.pack(fill="x", pady=20)
            return

        engine = getattr(self.main_window, "broll_engine", None)

        for idx, scene in enumerate(scenes):
            card = ctk.CTkFrame(
                self.scenes_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR,
                cursor="hand2"
            )
            card.pack(fill="x", pady=4, ipady=4)
            card.grid_columnconfigure(0, weight=1)

            # Details
            lbl_title = ctk.CTkLabel(
                card,
                text=f"Scene {scene.scene_number} - {scene.scene_type}",
                font=Theme.get_font(11, "bold"),
                text_color=Theme.ACCENT
            )
            lbl_title.grid(row=0, column=0, padx=10, pady=(4, 1), sticky="w")

            # Mini Narration snippet
            narr_snip = scene.narration[:45] + "..." if len(scene.narration) > 45 else scene.narration
            lbl_narr = ctk.CTkLabel(
                card,
                text=narr_snip,
                font=Theme.get_font(10),
                text_color=Theme.TEXT_SECONDARY,
                wraplength=200,
                justify="left"
            )
            lbl_narr.grid(row=1, column=0, padx=10, pady=(1, 4), sticky="w")

            # Check status badge
            badge_text = "No Asset"
            badge_color = Theme.TEXT_MUTED
            if engine:
                # Find if library contains asset with scene_id matching scene.scene_number
                assets = engine.library.list_assets()
                scene_assets = [a for a in assets if str(a.scene_id) == str(scene.scene_number)]
                if scene_assets:
                    completed_assets = [a for a in scene_assets if a.status == "completed"]
                    failed_assets = [a for a in scene_assets if a.status == "failed"]
                    if completed_assets:
                        badge_text = f"Ready ({completed_assets[0].asset_type})"
                        badge_color = Theme.SUCCESS
                    elif failed_assets:
                        badge_text = "Failed"
                        badge_color = Theme.DANGER
                
                # Check active jobs matching scene number
                active_jobs = [j for j in engine.controller.list_jobs() if str(j.scene_plan.scene_number) == str(scene.scene_number)]
                if active_jobs and active_jobs[0].status in ["pending", "running"]:
                    badge_text = "Generating"
                    badge_color = Theme.WARNING

            # Status Indicator Label
            lbl_badge = ctk.CTkLabel(
                card,
                text=badge_text,
                font=Theme.get_font(9, "bold"),
                text_color=badge_color
            )
            lbl_badge.grid(row=2, column=0, padx=10, pady=(2, 4), sticky="e")

            # Bind selection click event
            for w in [card, lbl_title, lbl_narr, lbl_badge]:
                w.bind("<Button-1>", lambda event, s=scene: self._on_scene_selected(s))

            self.scene_card_widgets.append(card)

            # Highlight if selected
            if self.selected_scene and self.selected_scene.scene_number == scene.scene_number:
                card.configure(border_color=Theme.ACCENT[1], fg_color=Theme.BG_CARD_HOVER)

    def _on_scene_selected(self, scene: ScenePlan) -> None:
        """Save selection and refresh dashboard content panels."""
        self.selected_scene = scene
        self._refresh_scenes_list()
        
        # Load preset prompt if asset doesn't exist
        engine = getattr(self.main_window, "broll_engine", None)
        if engine:
            assets = engine.library.list_assets()
            scene_assets = [a for a in assets if str(a.scene_id) == str(scene.scene_number) and a.status == "completed"]
            if scene_assets:
                self.selected_asset = scene_assets[0]
            else:
                self.selected_asset = None

        self._refresh_preview_and_controls()

    def _refresh_preview_and_controls(self) -> None:
        """Redraw Center panel depending on current selected scene/asset."""
        # Clean current preview frame
        for widget in self.preview_area.winfo_children():
            widget.destroy()

        if not self.selected_scene:
            # Enable placeholder
            self.preview_placeholder_lbl = ctk.CTkLabel(
                self.preview_area,
                text="🎞5 Scene Selected\nSelect a scene from the left to view or generate its B-roll background asset.",
                font=Theme.get_font(12),
                text_color=Theme.TEXT_MUTED
            )
            self.preview_placeholder_lbl.grid(row=0, column=0, sticky="")
            self._set_editor_state(False)
            return

        self._set_editor_state(True)
        scene = self.selected_scene

        # Populate controls based on asset or scene parameters
        if self.selected_asset:
            asset = self.selected_asset
            self.prompt_text.delete("1.0", ctk.END)
            self.prompt_text.insert("1.0", asset.prompt)
            self.provider_opt.set(asset.provider)
            self.type_opt.set(asset.asset_type)
            self.aspect_opt.set(asset.aspect_ratio)

            # Render Thumbnail Preview Image
            engine = getattr(self.main_window, "broll_engine", None)
            abs_thumb_path = None
            if engine and asset.thumbnail_path:
                abs_thumb_path = engine.workspace_dir / asset.thumbnail_path
            
            if abs_thumb_path and abs_thumb_path.exists():
                try:
                    # Render PIL Preview thumbnail
                    img_pil = Image.open(abs_thumb_path)
                    # Resize to fit area beautifully
                    w, h = 380, 210
                    ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(w, h))
                    
                    lbl_preview = ctk.CTkLabel(self.preview_area, image=ctk_img, text="")
                    lbl_preview.image = ctk_img  # Keep reference
                    lbl_preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
                except Exception as e:
                    self._logger.error(f"Failed to display thumbnail: {e}")
                    self._draw_text_preview(f"Asset Generated\nFormat: {asset.asset_type}\nLocation:\n{asset.file_path}")
            else:
                self._draw_text_preview(f"Asset Generated\nFormat: {asset.asset_type}\nLocation:\n{asset.file_path}")

            # Buttons settings
            self.generate_btn.configure(text="🔄 Regenerate", fg_color=Theme.ACCENT)
            self.delete_btn.configure(state="normal")
        else:
            # Generate default prompt using PromptBuilder
            prompt, asset_type = PromptBuilder.build_prompt_and_type(scene)
            self.prompt_text.delete("1.0", ctk.END)
            self.prompt_text.insert("1.0", prompt)
            
            engine = getattr(self.main_window, "broll_engine", None)
            active_prov = engine.provider_manager.active_provider_name if engine else "Gemini Flow"
            self.provider_opt.set(active_prov)
            self.type_opt.set(asset_type)
            
            aspect = "16:9"
            if self.main_window.current_project:
                aspect = self.main_window.current_project.aspect_ratio
            self.aspect_opt.set(aspect)

            # Check if there is an active job running for this scene
            is_running = False
            job_progress = 0.0
            job_status = ""
            if engine:
                active_jobs = [j for j in engine.controller.list_jobs() if str(j.scene_plan.scene_number) == str(scene.scene_number)]
                if active_jobs and active_jobs[0].status in ["pending", "running"]:
                    is_running = True
                    job_progress = active_jobs[0].progress
                    job_status = active_jobs[0].status

            if is_running:
                # Show generating loading status inside the preview panel
                box = ctk.CTkFrame(self.preview_area, fg_color="transparent")
                box.grid(row=0, column=0, sticky="")
                
                ctk.CTkLabel(
                    box,
                    text=f"Generating B-Roll Media... ({int(job_progress * 100)}%)",
                    font=Theme.get_font(12, "bold"),
                    text_color=Theme.ACCENT
                ).pack(pady=5)
                
                pbar = ctk.CTkProgressBar(box, width=200, progress_color=Theme.ACCENT)
                pbar.pack(pady=5)
                pbar.set(job_progress)
                
                ctk.CTkLabel(
                    box,
                    text=f"Status: {job_status.upper()}",
                    font=Theme.get_font(10),
                    text_color=Theme.TEXT_MUTED
                ).pack(pady=2)

                self.generate_btn.configure(text="🎞️ Generating...", state="disabled")
                self.delete_btn.configure(state="disabled")
            else:
                self._draw_text_preview("🎞️ No visual generated yet.\nConfigure options and click 'Generate B-Roll'.")
                self.generate_btn.configure(text="🎞️ Generate B-Roll", fg_color=Theme.SUCCESS, state="normal")
                self.delete_btn.configure(state="disabled")

    def _draw_text_preview(self, text: str) -> None:
        """Helper to draw text block in preview area."""
        lbl = ctk.CTkLabel(
            self.preview_area,
            text=text,
            font=Theme.get_font(11),
            text_color=Theme.TEXT_SECONDARY,
            justify="center"
        )
        lbl.grid(row=0, column=0, sticky="")

    def _on_provider_changed(self, val: str) -> None:
        """Update active engine provider setting."""
        engine = getattr(self.main_window, "broll_engine", None)
        if engine:
            engine.provider_manager.set_active_provider(val)

    def _on_generate_broll_clicked(self) -> None:
        """Submits a single scene B-roll generation job to the queue controller."""
        if not self.selected_scene:
            return

        engine = getattr(self.main_window, "broll_engine", None)
        if not engine:
            self.main_window.show_error("Engine Error", "BrollEngine is not initialized.")
            return

        prompt = self.prompt_text.get("1.0", ctk.END).strip()
        if not prompt:
            self.main_window.show_error("Validation Error", "Prompt text cannot be empty.")
            return

        # Override scene narration and broll keywords with current textbox prompts
        # to ensure generation uses edited descriptions
        scene = self.selected_scene
        scene.broll_keywords = prompt
        
        # Build Config
        config = BrollConfig(
            provider=self.provider_opt.get(),
            aspect_ratio=self.aspect_opt.get(),
            fps=30,
            quality="High",
            use_cache=True
        )

        # Submit background task
        job = engine.controller.submit_job(scene, config)
        self._logger.info(f"Triggered background B-roll generation job: {job.job_id}")
        self.main_window.update_status(f"B-roll: Generation job {job.job_id[:8]} started.")

        self._refresh_scenes_list()
        self._refresh_preview_and_controls()
        self._refresh_library_grid()

    def _on_import_clicked(self) -> None:
        """Opens file picker to import custom local images or videos."""
        if not self.selected_scene:
            return

        engine = getattr(self.main_window, "broll_engine", None)
        if not engine:
            return

        filepath = filedialog.askopenfilename(
            title="Select Custom B-Roll Media File",
            filetypes=[("Media Files", "*.mp4;*.mov;*.avi;*.png;*.jpg;*.jpeg;*.webp")]
        )
        if not filepath:
            return

        src_path = Path(filepath)
        ext = src_path.suffix.lower()
        
        # Guess type based on suffix
        asset_type = "Image" if ext in [".png", ".jpg", ".jpeg", ".webp"] else "Video"

        try:
            prompt = self.prompt_text.get("1.0", ctk.END).strip() or "Imported B-Roll Media"
            
            # Import file
            asset = engine.library.import_local_asset(
                source_path=src_path,
                scene_id=str(self.selected_scene.scene_number),
                prompt=prompt,
                provider="Local Import",
                asset_type=asset_type,
                aspect_ratio=self.aspect_opt.get()
            )

            self.selected_asset = asset
            self.main_window.update_status(f"Imported custom media for Scene {self.selected_scene.scene_number}.")
            
            self._refresh_scenes_list()
            self._refresh_preview_and_controls()
            self._refresh_library_grid()
        except Exception as e:
            self._logger.error(f"Media import failure: {e}")
            self.main_window.show_error("Import Failure", f"Could not import B-roll media file:\n{e}")

    def _on_delete_clicked(self) -> None:
        """Remove active scene asset reference."""
        if not self.selected_scene or not self.selected_asset:
            return

        engine = getattr(self.main_window, "broll_engine", None)
        if not engine:
            return

        try:
            success = engine.library.remove_asset(self.selected_asset.asset_id)
            if success:
                self.selected_asset = None
                self.main_window.update_status(f"B-roll asset deleted successfully.")
                self._refresh_scenes_list()
                self._refresh_preview_and_controls()
                self._refresh_library_grid()
        except Exception as e:
            self._logger.error(f"Asset deletion failed: {e}")
            self.main_window.show_error("Deletion Failure", f"Could not delete asset:\n{e}")

    def _refresh_library_grid(self) -> None:
        """Query and draw index registry search listings."""
        for widget in self.library_scroll.winfo_children():
            widget.destroy()

        engine = getattr(self.main_window, "broll_engine", None)
        if not engine:
            return

        assets = engine.library.list_assets()
        query = self.search_entry.get().strip().lower()
        cat_filter = self.cat_filter_opt.get()

        # Filters
        filtered_assets = []
        for asset in assets:
            # 1. Search Query
            if query and query not in asset.prompt.lower():
                continue
            # 2. Format Category Filter
            if cat_filter != "All Assets" and asset.asset_type != cat_filter:
                continue
            filtered_assets.append(asset)

        if not filtered_assets:
            lbl = ctk.CTkLabel(
                self.library_scroll,
                text="No assets matched.",
                font=Theme.get_font(10),
                text_color=Theme.TEXT_MUTED
            )
            lbl.pack(pady=20)
            return

        # Render list row items
        for asset in filtered_assets:
            row = ctk.CTkFrame(
                self.library_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=2, ipady=2)
            row.grid_columnconfigure(1, weight=1)

            # Mini square image preview
            abs_thumb = engine.workspace_dir / asset.thumbnail_path
            if abs_thumb.exists():
                try:
                    img_pil = Image.open(abs_thumb)
                    ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(40, 40))
                    lbl_thumb = ctk.CTkLabel(row, image=ctk_img, text="")
                    lbl_thumb.image = ctk_img
                    lbl_thumb.grid(row=0, column=0, padx=5, pady=2, rowspan=2)
                except Exception:
                    # fallback block
                    self._draw_mini_fallback(row)
            else:
                self._draw_mini_fallback(row)

            # Details
            lbl_desc = ctk.CTkLabel(
                row,
                text=asset.prompt[:30] + "..." if len(asset.prompt) > 30 else asset.prompt,
                font=Theme.get_font(10),
                text_color=Theme.TEXT_PRIMARY,
                anchor="w",
                justify="left"
            )
            lbl_desc.grid(row=0, column=1, padx=5, pady=(2, 0), sticky="w")

            meta = f"Scene {asset.scene_id} | {asset.asset_type} | {asset.provider}"
            lbl_meta = ctk.CTkLabel(
                row,
                text=meta,
                font=Theme.get_font(9),
                text_color=Theme.TEXT_MUTED,
                anchor="w"
            )
            lbl_meta.grid(row=1, column=1, padx=5, pady=(0, 2), sticky="w")

            # Quick inspect button
            btn = ctk.CTkButton(
                row,
                text="👁️",
                font=Theme.get_font(10),
                width=24,
                height=24,
                fg_color=Theme.BG_CARD,
                hover_color=Theme.BG_CARD_HOVER,
                text_color=Theme.TEXT_PRIMARY,
                command=lambda a=asset: self._inspect_library_asset(a)
            )
            btn.grid(row=0, column=2, padx=5, rowspan=2, sticky="e")

    def _draw_mini_fallback(self, parent: ctk.CTkFrame) -> None:
        """Render small block if thumbnail is missing."""
        lbl = ctk.CTkLabel(
            parent,
            text="🎞️",
            font=Theme.get_font(12),
            fg_color=Theme.BG_CARD,
            corner_radius=2,
            width=40,
            height=40
        )
        lbl.grid(row=0, column=0, padx=5, pady=2, rowspan=2)

    def _inspect_library_asset(self, asset: SceneAsset) -> None:
        """Inspect catalog metadata details and auto-navigate selector if possible."""
        # Find matching scene plan in director
        director_view = getattr(self.main_window.views.get("director"), "_active_timeline", None)
        if director_view:
            scenes = [s for s in director_view.scenes if str(s.scene_number) == str(asset.scene_id)]
            if scenes:
                self._on_scene_selected(scenes[0])
                self.main_window.update_status(f"Inspecting Scene {asset.scene_id} visual asset.")
                return

        # Fallback details pop-up dialog
        self.main_window.show_error(
            "Asset Information",
            f"Prompt: {asset.prompt}\n"
            f"Scene Association: Scene {asset.scene_id}\n"
            f"Provider: {asset.provider}\n"
            f"Format Type: {asset.asset_type}\n"
            f"Aspect Shape: {asset.aspect_ratio}\n"
            f"Local File Path:\n{asset.file_path}"
        )

    def _start_queue_monitoring(self) -> None:
        """Kick off repeating UI status monitors."""
        self._poll_active = True
        self._poll_jobs_loop()

    def _poll_jobs_loop(self) -> None:
        """Poll B-roll controller jobs list and update progress bar displays."""
        if not self._poll_active:
            return

        # Skip UI redraws when the view is hidden (tab switched away)
        try:
            is_visible = self.winfo_viewable()
        except Exception:
            is_visible = True

        if not is_visible:
            # Reschedule but don't redraw
            self.after(500, self._poll_jobs_loop)
            return

        engine = getattr(self.main_window, "broll_engine", None)
        if not engine:
            self.after(1000, self._poll_jobs_loop)
            return

        # 1. Update active view if current selected scene is generating
        if self.selected_scene:
            active_jobs = [j for j in engine.controller.list_jobs() if str(j.scene_plan.scene_number) == str(self.selected_scene.scene_number)]
            if active_jobs and active_jobs[0].status in ["completed", "failed"]:
                # Job just finished, force refresh
                engine.controller.clear_completed_jobs()
                self._on_scene_selected(self.selected_scene)

        # 2. Re-draw background queue monitors list
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()

        jobs = engine.controller.list_jobs()
        active_jobs = [j for j in jobs if j.status in ["pending", "running"]]

        if not active_jobs:
            lbl = ctk.CTkLabel(
                self.queue_scroll,
                text="No active rendering tasks.",
                font=Theme.get_font(10),
                text_color=Theme.TEXT_MUTED
            )
            lbl.pack(pady=10)
        else:
            # Render each active job
            for job in active_jobs:
                job_box = ctk.CTkFrame(
                    self.queue_scroll,
                    fg_color=Theme.BG_MAIN,
                    corner_radius=Theme.CORNER_RADIUS - 4,
                    border_width=Theme.BORDER_WIDTH,
                    border_color=Theme.BORDER_COLOR
                )
                job_box.pack(fill="x", pady=2, ipady=2)
                job_box.grid_columnconfigure(0, weight=1)

                lbl_info = ctk.CTkLabel(
                    job_box,
                    text=f"Scene {job.scene_plan.scene_number} | {job.config.provider} ({job.status})",
                    font=Theme.get_font(10, "bold"),
                    text_color=Theme.TEXT_PRIMARY
                )
                lbl_info.grid(row=0, column=0, sticky="w", padx=10, pady=(2, 0))

                pbar = ctk.CTkProgressBar(job_box, progress_color=Theme.ACCENT, height=5)
                pbar.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
                pbar.set(job.progress)

                # Cancel button
                btn_cancel = ctk.CTkButton(
                    job_box,
                    text="Cancel",
                    font=Theme.get_font(9, "bold"),
                    width=45,
                    height=18,
                    fg_color=Theme.DANGER,
                    hover_color=Theme.DANGER,
                    command=lambda jid=job.job_id: self._on_cancel_job_clicked(jid)
                )
                btn_cancel.grid(row=0, column=1, rowspan=2, padx=5, sticky="e")

        # Re-run after 400ms
        self.after(400, self._poll_jobs_loop)

    def _on_cancel_job_clicked(self, job_id: str) -> None:
        """Cancel a running B-roll queue task."""
        engine = getattr(self.main_window, "broll_engine", None)
        if engine:
            success = engine.controller.cancel_job(job_id)
            if success:
                self.main_window.update_status(f"Cancelled B-roll job {job_id[:8]}.")
                self._refresh_scenes_list()
                self._refresh_preview_and_controls()

    def destroy(self) -> None:
        """Stop threads and hooks on cleanup."""
        self._poll_active = False
        super().destroy()
