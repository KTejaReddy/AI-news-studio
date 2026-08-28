"""Main GUI Application window for AI News Studio.

Defines the core grid layout (Sidebar, Viewport, Status Bar) and view router.
"""

import logging
from pathlib import Path
import tkinter as tk
from typing import Dict, Optional

import customtkinter as ctk

from app.theme import Theme
# Views will be created in app/views
from app.views.dashboard import DashboardView
from app.views.projects import ProjectsView
from app.views.presenters import PresentersView
from app.views.voices import VoicesView
from app.views.lipsync import LipSyncView
from app.views.director import DirectorView
from app.views.broll import BrollView
from app.views.editor import EditorView
from app.views.settings import SettingsView
from app.views.models import ModelsView
from app.views.logs import LogsView
from app.views.production import ProductionView
from app.widgets.dialogs import ErrorDialog
from core.managers import (
    AssetManager,
    ConfigManager,
    HistoryManager,
    ModelManager,
    OutputManager,
    Project,
    ProjectManager,
    SettingsManager,
)
from core.presenter.presenter_engine import PresenterEngine
from core.motion.motion_engine import MotionEngine
from core.voice.voice_engine import VoiceEngine
from core.lipsync.lipsync_engine import LipSyncEngine
from core.director.director_engine import DirectorEngine
from core.broll.broll_engine import BrollEngine
from core.timeline.timeline_engine import TimelineEngine
from core.export.export_engine import ExportEngine
from core.production.orchestrator import ProductionOrchestrator


class MainWindow(ctk.CTk):
    """Primary application frame containing navigation sidebar and views."""

    def __init__(
        self,
        config_mgr: ConfigManager,
        settings_mgr: SettingsManager,
        project_mgr: ProjectManager,
        asset_mgr: AssetManager,
        model_mgr: ModelManager,
        output_mgr: OutputManager,
        history_mgr: HistoryManager,
    ) -> None:
        """Initialize the main application GUI.

        Args:
            config_mgr: ConfigManager instance.
            settings_mgr: SettingsManager instance.
            project_mgr: ProjectManager instance.
            asset_mgr: AssetManager instance.
            model_mgr: ModelManager instance.
            output_mgr: OutputManager instance.
            history_mgr: HistoryManager instance.
        """
        super().__init__()

        # Injected Managers
        self.config_mgr = config_mgr
        self.settings_mgr = settings_mgr
        self.project_mgr = project_mgr
        self.asset_mgr = asset_mgr
        self.model_mgr = model_mgr
        self.output_mgr = output_mgr
        self.history_mgr = history_mgr
        self.presenter_engine = PresenterEngine(self.config_mgr.workspace_dir)
        self.motion_engine = MotionEngine(self.config_mgr.workspace_dir)
        self.voice_engine = VoiceEngine(self.config_mgr.workspace_dir)
        self.lipsync_engine = LipSyncEngine(self.config_mgr.workspace_dir)
        self.director_engine = DirectorEngine(self.config_mgr.workspace_dir)
        self.broll_engine = BrollEngine(self.config_mgr.workspace_dir)
        self.timeline_engine = TimelineEngine(self.config_mgr.workspace_dir)
        self.export_engine = ExportEngine(self.config_mgr.workspace_dir)
        self.production_orchestrator = ProductionOrchestrator(
            workspace_dir=self.config_mgr.workspace_dir,
            director_engine=self.director_engine,
            broll_engine=self.broll_engine,
            voice_engine=self.voice_engine,
            motion_engine=self.motion_engine,
            lipsync_engine=self.lipsync_engine,
            presenter_engine=self.presenter_engine,
            timeline_engine=self.timeline_engine,
            export_engine=self.export_engine,
        )

        self._logger = logging.getLogger(self.__class__.__name__)
        
        # State tracking
        self.current_project: Optional[Project] = None

        # Configure window geometry
        self.title("AI News Studio")
        self.geometry("1280x720")
        self.minimum_width = 1000
        self.minimum_height = 600
        self.minsize(self.minimum_width, self.minimum_height)

        # Apply initial theme
        self._apply_theme_setting(self.settings_mgr.theme)
        self.settings_mgr.register_listener("theme", self._on_theme_changed)

        # Setup main grid layout (2 columns: Sidebar, Content; 2 rows: Main, Status Bar)
        self.grid_columnconfigure(0, weight=0)  # Sidebar width fixed
        self.grid_columnconfigure(1, weight=1)  # Content area expands
        self.grid_rowconfigure(0, weight=1)     # Viewport/Sidebar expands
        self.grid_rowconfigure(1, weight=0)     # Status bar fixed height

        # Build UI Components
        self._create_sidebar()
        self._create_viewport()
        self._create_status_bar()

        # Navigation Buttons mapping
        self.sidebar_buttons: Dict[str, ctk.CTkButton] = {}
        self._setup_navigation_mappings()

        # Show default dashboard view
        self.show_view("dashboard")
        
        self._logger.info("Application main window successfully initialized.")

    def _apply_theme_setting(self, theme_val: str) -> None:
        """Apply light/dark appearance mode.

        Args:
            theme_val: Appearance mode setting string.
        """
        if theme_val == "dark":
            ctk.set_appearance_mode("Dark")
        elif theme_val == "light":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("System")

    def _on_theme_changed(self, key: str, val: str) -> None:
        """Event listener for SettingsManager theme updates.

        Args:
            key: Config key changed.
            val: New theme value.
        """
        self._apply_theme_setting(val)

    def _create_sidebar(self) -> None:
        """Construct the sidebar panel and title logo."""
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=Theme.BG_SIDEBAR
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(11, weight=1)  # Spacer push to bottom

        # App Logo & Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="📺 AI NEWS STUDIO",
            font=Theme.get_font(18, "bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 20), sticky="w")

    def _create_viewport(self) -> None:
        """Create the central main display container frame where views are swapped."""
        self.viewport_container = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=Theme.BG_MAIN
        )
        self.viewport_container.grid(row=0, column=1, sticky="nsew")
        
        # Grid layout for content inside viewport container
        self.viewport_container.grid_rowconfigure(0, weight=1)
        self.viewport_container.grid_columnconfigure(0, weight=1)

        # Instantiate all sub-views inside the viewport container
        self.views: Dict[str, ctk.CTkFrame] = {
            "dashboard": DashboardView(self.viewport_container, self),
            "projects": ProjectsView(self.viewport_container, self),
            "presenters": PresentersView(self.viewport_container, self),
            "voices": VoicesView(self.viewport_container, self),
            "lipsync": LipSyncView(self.viewport_container, self),
            "director": DirectorView(self.viewport_container, self),
            "broll": BrollView(self.viewport_container, self),
            "editor": EditorView(self.viewport_container, self),
            "production": ProductionView(self.viewport_container, self),
            "models": ModelsView(self.viewport_container, self),
            "logs": LogsView(self.viewport_container, self),
            "settings": SettingsView(self.viewport_container, self),
        }

        # Hide all views initially
        for view in self.views.values():
            view.grid_forget()

    def _create_status_bar(self) -> None:
        """Construct the bottom status bar."""
        self.status_bar_frame = ctk.CTkFrame(
            self,
            height=25,
            corner_radius=0,
            fg_color=Theme.BG_SIDEBAR,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.status_bar_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        # Grid settings
        self.status_bar_frame.grid_columnconfigure(0, weight=1)
        self.status_bar_frame.grid_columnconfigure(1, weight=0)
        self.status_bar_frame.grid_columnconfigure(2, weight=0)

        # Status text
        self.status_label = ctk.CTkLabel(
            self.status_bar_frame,
            text="Ready",
            font=Theme.get_font(11, "normal"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.grid(row=0, column=0, padx=15, pady=2, sticky="w")

        # Project tag
        self.project_status_label = ctk.CTkLabel(
            self.status_bar_frame,
            text="Active Project: None",
            font=Theme.get_font(11, "normal"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.project_status_label.grid(row=0, column=1, padx=15, pady=2, sticky="e")

        # Device/Hardware info
        device = self.settings_mgr.device_mode
        self.device_status_label = ctk.CTkLabel(
            self.status_bar_frame,
            text=f"Device: {device}",
            font=Theme.get_font(11, "normal"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.device_status_label.grid(row=0, column=2, padx=15, pady=2, sticky="e")

        # Register hardware updates callback
        self.settings_mgr.register_listener("device_mode", self._on_device_mode_changed)

    def _on_device_mode_changed(self, key: str, val: str) -> None:
        """Callback for device mode updates."""
        self.device_status_label.configure(text=f"Device: {val}")

    def _setup_navigation_mappings(self) -> None:
        """Create buttons and define navigation mappings for the sidebar."""
        nav_items = [
            ("dashboard", "📊 Dashboard"),
            ("projects", "📁 Projects"),
            ("presenters", "👥 Presenters"),
            ("voices", "🔊 Voices"),
            ("lipsync", "👄 Lip Sync"),
            ("director", "🧠 Director AI"),
            ("broll", "🎞️ B-roll"),
            ("editor", "🎬 Editor"),
            ("production", "🚀 Production"),
            ("models", "📦 Models"),
            ("logs", "📝 Logs"),
            ("settings", "⚙️ Settings"),
        ]

        for i, (key, label) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label,
                font=Theme.get_font(13, "bold"),
                anchor="w",
                height=38,
                corner_radius=Theme.CORNER_RADIUS,
                border_spacing=10,
                fg_color="transparent",
                text_color=Theme.TEXT_SECONDARY,
                hover_color=Theme.BG_CARD_HOVER,
                command=lambda k=key: self.show_view(k)
            )
            btn.grid(row=i + 1, column=0, padx=10, pady=2, sticky="ew")
            self.sidebar_buttons[key] = btn

    def show_view(self, view_name: str) -> None:
        """Switch the visible view in the viewport and update sidebar selection.

        Args:
            view_name: ID of the view to present.
        """
        if view_name not in self.views:
            self._logger.error(f"Cannot navigate to unregistered view: {view_name}")
            return

        # Hide all views and un-highlight sidebar
        for k, view in self.views.items():
            view.grid_forget()
            btn = self.sidebar_buttons.get(k)
            if btn:
                btn.configure(
                    fg_color="transparent",
                    text_color=Theme.TEXT_SECONDARY
                )

        # Show target view and update sidebar style
        self.views[view_name].grid(row=0, column=0, sticky="nsew")
        
        # Trigger refresh on view if it defines an on_show hook
        show_hook = getattr(self.views[view_name], "on_show", None)
        if show_hook and callable(show_hook):
            try:
                show_hook()
            except Exception as e:
                self._logger.error(f"Error in on_show hook for view '{view_name}': {e}")
                
        btn = self.sidebar_buttons.get(view_name)
        if btn:
            btn.configure(
                fg_color=Theme.ACCENT,
                text_color=Theme.TEXT_ON_ACCENT
            )

        self._logger.debug(f"View navigation completed. Active: {view_name}")

    def update_status(self, text: str) -> None:
        """Update the text displayed in the status bar.

        Thread-safe: schedules the update on the Tkinter event loop if called
        from a background thread.

        Args:
            text: Information text to display.
        """
        try:
            self.after(0, lambda t=text: self.status_label.configure(text=t))
        except Exception:
            pass

    def set_active_project(self, project: Optional[Project]) -> None:
        """Set the active project context and update displays.

        Args:
            project: Project object to make active, or None.
        """
        self.current_project = project
        if project:
            self.project_status_label.configure(text=f"Active Project: {project.name}")
            # Refresh dashboard script and values if active
            dashboard_view = self.views.get("dashboard")
            if dashboard_view and hasattr(dashboard_view, "load_project_context"):
                dashboard_view.load_project_context(project)
        else:
            self.project_status_label.configure(text="Active Project: None")

    def show_error(self, title: str, message: str) -> None:
        """Launch a non-blocking graceful error alert dialog.

        Args:
            title: The dialog box header title.
            message: Explanation detail message of the error.
        """
        dialog = ErrorDialog(self, title=title, message=message)
        dialog.grab_set()

    def destroy(self) -> None:
        """Clean shutdown of all engines and worker threads."""
        if hasattr(self, "production_orchestrator"):
            self._logger.info("Shutting down ProductionOrchestrator...")
            try:
                self.production_orchestrator.shutdown()
            except Exception as e:
                self._logger.error(f"Error during ProductionOrchestrator shutdown: {e}")
        if hasattr(self, "export_engine"):
            self._logger.info("Shutting down ExportEngine background worker...")
            try:
                self.export_engine.shutdown()
            except Exception as e:
                self._logger.error(f"Error during ExportEngine shutdown: {e}")
        super().destroy()
