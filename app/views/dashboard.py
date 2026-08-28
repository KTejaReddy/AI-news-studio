"""Dashboard View for AI News Studio.

Main operational interface containing script input, generation configurations,
progress tracking, output preview, and recent project listings.
"""
import tkinter as tk
import logging
import threading
import time
from typing import TYPE_CHECKING, List

import customtkinter as ctk

from app.theme import Theme
from core.managers import Project

if TYPE_CHECKING:
    from app.gui import MainWindow


class DashboardView(ctk.CTkFrame):
    """The central workshop panel for drafting scripts and initiating video generation."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize the Dashboard view.

        Args:
            parent: Parent frame container.
            main_window: Root MainWindow application reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._is_generating = False

        # Grid setup: 2 columns (Left: inputs, Right: preview & recent)
        self.grid_columnconfigure(0, weight=3)  # Left panel
        self.grid_columnconfigure(1, weight=2)  # Right panel
        self.grid_rowconfigure(0, weight=1)

        self._create_left_panel()
        self._create_right_panel()

    def _create_left_panel(self) -> None:
        """Construct the script composing and configuration sidebar (left side)."""
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(2, weight=1)  # Script textbox expands

        # 1. Title Block
        title_label = ctk.CTkLabel(
            left_frame,
            text="AI News Studio",
            font=Theme.get_font(28, "bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        title_label.grid(row=0, column=0, pady=(0, 20), sticky="w")

        # 2. Dropdown selectors container
        selectors_frame = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        selectors_frame.grid(row=1, column=0, pady=(0, 15), sticky="ew")
        for col in range(3):
            selectors_frame.grid_columnconfigure(col, weight=1)

        # Presenter selector
        presenter_lbl_frame = ctk.CTkFrame(selectors_frame, fg_color="transparent")
        presenter_lbl_frame.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
        ctk.CTkLabel(
            presenter_lbl_frame,
            text="Presenter",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 5))
        
        self.presenter_selector = ctk.CTkOptionMenu(
            presenter_lbl_frame,
            values=["Loading..."],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.presenter_selector.pack(fill="x")

        # Voice selector
        voice_lbl_frame = ctk.CTkFrame(selectors_frame, fg_color="transparent")
        voice_lbl_frame.grid(row=0, column=1, padx=15, pady=10, sticky="ew")
        ctk.CTkLabel(
            voice_lbl_frame,
            text="Voice Profile",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 5))
        
        self.voice_selector = ctk.CTkOptionMenu(
            voice_lbl_frame,
            values=["Loading..."],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.voice_selector.pack(fill="x")

        # Aspect ratio selector
        ratio_lbl_frame = ctk.CTkFrame(selectors_frame, fg_color="transparent")
        ratio_lbl_frame.grid(row=0, column=2, padx=15, pady=10, sticky="ew")
        ctk.CTkLabel(
            ratio_lbl_frame,
            text="Aspect Ratio",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 5))
        
        self.ratio_selector = ctk.CTkOptionMenu(
            ratio_lbl_frame,
            values=["16:9 (Landscape)", "9:16 (Vertical)", "1:1 (Square)"],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.ratio_selector.pack(fill="x")

        # 3. Script Editor
        editor_card = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        editor_card.grid(row=2, column=0, pady=(0, 15), sticky="nsew")
        editor_card.grid_columnconfigure(0, weight=1)
        editor_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            editor_card,
            text="Video Script Editor",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.script_textbox = ctk.CTkTextbox(
            editor_card,
            font=Theme.get_font(13),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 2
        )
        self.script_textbox.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.script_textbox.insert(
            "1.0",
            "Welcome to AI News Studio! Type your news broadcast script here. "
            "Our automated director engine will segment your story, allocate scenic B-rolls, "
            "synthesize voice audio, generate presenter expressions, and automatically edit everything together."
        )

        # 4. Generate controls bar
        controls_frame = ctk.CTkFrame(
            left_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        controls_frame.grid(row=3, column=0, sticky="ew")
        controls_frame.grid_columnconfigure(1, weight=1)

        self.generate_btn = ctk.CTkButton(
            controls_frame,
            text="⚡ Generate Video",
            font=Theme.get_font(13, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS,
            height=40,
            command=self._on_generate_clicked
        )
        self.generate_btn.grid(row=0, column=0, padx=15, pady=15)

        self.progress_bar = ctk.CTkProgressBar(
            controls_frame,
            progress_color=Theme.ACCENT,
            height=10
        )
        self.progress_bar.grid(row=0, column=1, padx=(0, 20), pady=15, sticky="ew")
        self.progress_bar.set(0.0)

    def _create_right_panel(self) -> None:
        """Construct the output preview and recent projects panels (right side)."""
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)  # Projects list expands

        # 1. Output Preview Area
        preview_card = ctk.CTkFrame(
            right_frame,
            height=280,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        preview_card.grid(row=0, column=0, pady=(0, 20), sticky="ew")
        preview_card.grid_propagate(False)  # Retain explicit height
        preview_card.grid_columnconfigure(0, weight=1)
        preview_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            preview_card,
            text="Output Video Preview",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(15, 0), sticky="w")

        # Mock video screen
        self.screen_frame = ctk.CTkFrame(
            preview_card,
            fg_color=Theme.BG_MAIN,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 2
        )
        self.screen_frame.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        self.screen_frame.grid_columnconfigure(0, weight=1)
        self.screen_frame.grid_rowconfigure(0, weight=1)

        self.play_icon_label = ctk.CTkLabel(
            self.screen_frame,
            text="🎬\nNo video loaded",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_MUTED
        )
        self.play_icon_label.grid(row=0, column=0, sticky="")

        # 2. Recent Projects list
        projects_card = ctk.CTkFrame(
            right_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        projects_card.grid(row=1, column=0, sticky="nsew")
        projects_card.grid_columnconfigure(0, weight=1)
        projects_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            projects_card,
            text="Recent Projects",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.projects_scroll = ctk.CTkScrollableFrame(
            projects_card,
            fg_color="transparent"
        )
        self.projects_scroll.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def on_show(self) -> None:
        """Triggered automatically when the dashboard tab is activated."""
        self._refresh_presets()
        self._refresh_recent_projects()

        # Sync active project details if one exists
        if self.main_window.current_project:
            self.load_project_context(self.main_window.current_project)

    def _refresh_presets(self) -> None:
        """Query managers and fill presenter and voice menus."""
        # Presenters
        presenters = self.main_window.asset_mgr.get_presenters()
        pres_names = [p["name"] for p in presenters]
        if pres_names:
            self.presenter_selector.configure(values=pres_names)
            # Default to first if none currently selected
            if self.presenter_selector.get() == "Loading..." and pres_names:
                self.presenter_selector.set(pres_names[0])

        # Voices
        voices = self.main_window.asset_mgr.get_voices()
        voice_names = [v["name"] for v in voices]
        if voice_names:
            self.voice_selector.configure(values=voice_names)
            if self.voice_selector.get() == "Loading..." and voice_names:
                self.voice_selector.set(voice_names[0])

    def _refresh_recent_projects(self) -> None:
        """Load project lists from ProjectManager and build custom UI rows."""
        # Clear existing items
        for widget in self.projects_scroll.winfo_children():
            widget.destroy()

        recents: List[Project] = self.main_window.project_mgr.get_recent_projects(limit=5)
        if not recents:
            ctk.CTkLabel(
                self.projects_scroll,
                text="No projects found. Click Projects in the sidebar to create one.",
                font=Theme.get_font(12, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=20)
            return

        for proj in recents:
            row_frame = ctk.CTkFrame(
                self.projects_scroll,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row_frame.pack(fill="x", pady=4, ipady=3)
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=0)

            # Details
            lbls_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            lbls_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            
            ctk.CTkLabel(
                lbls_frame,
                text=proj.name,
                font=Theme.get_font(12, "bold"),
                text_color=Theme.TEXT_PRIMARY
            ).pack(anchor="w")

            modified_dt = proj.modified_at.split("T")[0]
            ctk.CTkLabel(
                lbls_frame,
                text=f"Modified: {modified_dt} | Status: {proj.status}",
                font=Theme.get_font(10),
                text_color=Theme.TEXT_MUTED
            ).pack(anchor="w")

            # Load project button
            ctk.CTkButton(
                row_frame,
                text="Open",
                font=Theme.get_font(11, "bold"),
                width=60,
                height=26,
                fg_color=Theme.ACCENT,
                hover_color=Theme.ACCENT_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda p=proj: self.main_window.set_active_project(p)
            ).grid(row=0, column=1, padx=10, pady=5)

    def load_project_context(self, project: Project) -> None:
        """Bind project attributes to dashboard widgets.

        Args:
            project: The project to display.
        """
        # Script
        self.script_textbox.delete("1.0", tk.END)
        self.script_textbox.insert("1.0", project.script)
        
        # selectors
        self.ratio_selector.set(project.aspect_ratio)

        # Sync selectors by seeking name match
        presenters = self.main_window.asset_mgr.get_presenters()
        voices = self.main_window.asset_mgr.get_voices()

        match_pres = next((p for p in presenters if p["id"] == project.presenter_id), None)
        if match_pres:
            self.presenter_selector.set(match_pres["name"])

        match_voice = next((v for v in voices if v["id"] == project.voice_id), None)
        if match_voice:
            self.voice_selector.set(match_voice["name"])

        # Preview status update
        if project.output_video_path:
            self.play_icon_label.configure(
                text=f"▶️\n{project.name}\nExported Video Ready",
                text_color=Theme.SUCCESS
            )
        else:
            self.play_icon_label.configure(
                text=f"🎬\n{project.name}\nDraft - Not yet generated",
                text_color=Theme.TEXT_MUTED
            )

        self.main_window.update_status(f"Loaded project: {project.name}")

    def _on_generate_clicked(self) -> None:
        """Handler for the Generate button. Spawns rendering threads."""
        if self._is_generating:
            return

        # Ensure active project exists or prompt to make/select one
        project = self.main_window.current_project
        if not project:
            # Automatically create a quick draft project to be helpful
            project = self.main_window.project_mgr.create_project(name="Auto Draft Project")
            self.main_window.set_active_project(project)

        # Save latest script and settings changes
        project.script = self.script_textbox.get("1.0", tk.END).strip()
        project.aspect_ratio = self.ratio_selector.get()

        # Save selected IDs
        presenters = self.main_window.asset_mgr.get_presenters()
        voices = self.main_window.asset_mgr.get_voices()
        
        selected_pres = next((p for p in presenters if p["name"] == self.presenter_selector.get()), None)
        if selected_pres:
            project.presenter_id = selected_pres["id"]
        
        selected_voice = next((v for v in voices if v["name"] == self.voice_selector.get()), None)
        if selected_voice:
            project.voice_id = selected_voice["id"]

        self.main_window.project_mgr.save_project(project)

        # Run process thread
        self._is_generating = True
        self.generate_btn.configure(state="disabled", fg_color=Theme.TEXT_MUTED, text="Processing...")
        
        thread = threading.Thread(target=self._simulate_generation, args=(project,), daemon=True)
        thread.start()

    def _simulate_generation(self, project: Project) -> None:
        """Simulate generation pipeline sequence with logging and progress updates.

        Args:
            project: The project context to render.
        """
        steps = [
            (0.1, "Initializing video assembly context...", "Started"),
            (0.3, "Executing Director AI script parser...", "Parsing Script"),
            (0.5, "Running speech synthesis voice cloner...", "Synthesizing Voice"),
            (0.75, "Rendering Talking Head Presenter frames...", "Generating Video"),
            (0.9, "Overlaying B-roll footage and captions...", "Compiling Timeline"),
            (1.0, "Muxing and exporting finished media file...", "Exporting Video")
        ]

        self.main_window.update_status(f"Generating video for: '{project.name}'")
        self.main_window.history_mgr.add_entry(
            project.id, project.name, "Running", "Video synthesis request received."
        )

        for ratio, msg, status_text in steps:
            self._logger.info(msg)
            self.main_window.update_status(f"Processing: {msg}")

            # Incremental updates to feel realistic
            current_progress = self.progress_bar.get()
            increment = (ratio - current_progress) / 10
            for step_i in range(10):
                time.sleep(0.08)  # delay
                new_val = current_progress + increment * (step_i + 1)
                self.progress_bar.after(0, lambda v=new_val: self.progress_bar.set(v))

            self.progress_bar.after(0, lambda r=ratio: self.progress_bar.set(r))

        # Write output mock file so OutputManager finds it
        timestamp = int(time.time())
        filename = f"video_{project.id}_{timestamp}.mp4"
        
        output_folder_name = self.main_window.settings_mgr.output_folder
        output_dir = self.main_window.workspace_dir / output_folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        mock_video_file = output_dir / filename
        try:
            with open(mock_video_file, "w", encoding="utf-8") as f:
                f.write(f"MOCK VIDEO PLAYLOAD\nProject: {project.name}\nPresenter: {project.presenter_id}\nVoice: {project.voice_id}\n")
            
            project.status = "Completed"
            project.output_video_path = str(mock_video_file)
            self.main_window.project_mgr.save_project(project)
            
            self.main_window.history_mgr.add_entry(
                project.id, project.name, "Success", f"Video export compiled successfully: {filename}"
            )
            
            self._logger.info(f"Rendering process finished. File created: {mock_video_file}")
            self.main_window.update_status("Generation complete!")
            
            # Update screen frame label inside GUI thread
            self.screen_frame.after(0, lambda: self.play_icon_label.configure(
                text=f"▶️\n{project.name}\nExported Video Ready\n({filename})",
                text_color=Theme.SUCCESS
            ))
        except Exception as e:
            self._logger.error(f"Error compiling mock video file: {e}")
            project.status = "Failed"
            self.main_window.project_mgr.save_project(project)
            self.main_window.history_mgr.add_entry(
                project.id, project.name, "Failed", f"Export compilation failed: {e}"
            )
            self.main_window.update_status("Generation failed.")

        # Re-enable generate buttons
        self._is_generating = False
        self.generate_btn.after(0, lambda: self.generate_btn.configure(
            state="normal", fg_color=Theme.SUCCESS, text="⚡ Generate Video"
        ))
        
        # Refresh lists
        self.projects_scroll.after(0, self._refresh_recent_projects)
