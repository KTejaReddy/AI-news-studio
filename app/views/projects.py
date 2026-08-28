"""Project Management View for AI News Studio.

Allows users to create, search, open, and delete video creation projects.
"""

import logging
from typing import TYPE_CHECKING, List

import customtkinter as ctk

from app.theme import Theme
from core.managers import Project

if TYPE_CHECKING:
    from app.gui import MainWindow


class ProjectsView(ctk.CTkFrame):
    """View showing all projects in the workspace and providing CRUD actions."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize ProjectsView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Scrollable list expands

        self._create_header()
        self._create_creation_card()
        self._create_list_card()

    def _create_header(self) -> None:
        """Create view title."""
        ctk.CTkLabel(
            self,
            text="Project Manager",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    def _create_creation_card(self) -> None:
        """Create project creation inputs card."""
        card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        card.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # Title label
        ctk.CTkLabel(
            card,
            text="Create New Project",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(12, 5), sticky="w")

        # Name Entry
        ctk.CTkLabel(
            card,
            text="Project Name:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).grid(row=1, column=0, padx=(15, 10), pady=(0, 15), sticky="w")

        self.name_entry = ctk.CTkEntry(
            card,
            placeholder_text="e.g. Morning News Broadcast",
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.name_entry.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="ew")

        # Create Button
        create_btn = ctk.CTkButton(
            card,
            text="➕ Create",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            width=90,
            command=self._on_create_clicked
        )
        create_btn.grid(row=1, column=2, padx=15, pady=(0, 15))

    def _create_list_card(self) -> None:
        """Create scrollable project list panel."""
        self.list_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.list_card.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.list_card.grid_columnconfigure(0, weight=1)
        self.list_card.grid_rowconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(
            self.list_card,
            text="Existing Projects Workspace",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

        # Scrollable container
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.list_card,
            fg_color="transparent"
        )
        self.scroll_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def on_show(self) -> None:
        """Refresh scroll list automatically when page is navigated to."""
        self._refresh_project_list()

    def _refresh_project_list(self) -> None:
        """Load all project metadata records and draw layout list rows."""
        # Clear existing children
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        projects: List[Project] = self.main_window.project_mgr.list_projects()
        if not projects:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No projects configured in current workspace. Create one above to get started.",
                font=Theme.get_font(12, "italic"),
                text_color=Theme.TEXT_MUTED
            ).pack(pady=40)
            return

        for proj in projects:
            row = ctk.CTkFrame(
                self.scroll_frame,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            row.pack(fill="x", pady=5, ipady=5)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=0)
            row.grid_columnconfigure(2, weight=0)

            # Details
            details_f = ctk.CTkFrame(row, fg_color="transparent")
            details_f.grid(row=0, column=0, padx=15, pady=5, sticky="w")

            # Emphasize active project
            is_active = self.main_window.current_project and self.main_window.current_project.id == proj.id
            title_suffix = " (Active)" if is_active else ""
            title_color = Theme.ACCENT if is_active else Theme.TEXT_PRIMARY
            
            ctk.CTkLabel(
                details_f,
                text=f"{proj.name}{title_suffix}",
                font=Theme.get_font(13, "bold"),
                text_color=title_color
            ).pack(anchor="w")

            created_dt = proj.created_at.replace("T", " ")[:16]
            ctk.CTkLabel(
                details_f,
                text=f"Created: {created_dt}  |  Aspect Ratio: {proj.aspect_ratio}  |  Status: {proj.status}",
                font=Theme.get_font(11),
                text_color=Theme.TEXT_MUTED
            ).pack(anchor="w")

            # Actions
            open_btn = ctk.CTkButton(
                row,
                text="📁 Open",
                font=Theme.get_font(11, "bold"),
                width=75,
                height=28,
                fg_color=Theme.ACCENT,
                hover_color=Theme.ACCENT_HOVER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda p=proj: self._on_open_clicked(p)
            )
            open_btn.grid(row=0, column=1, padx=5, pady=5)

            # Highlight delete differently for safety
            delete_btn = ctk.CTkButton(
                row,
                text="🗑️ Delete",
                font=Theme.get_font(11, "bold"),
                width=75,
                height=28,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER,
                corner_radius=Theme.CORNER_RADIUS - 4,
                command=lambda p_id=proj.id: self._on_delete_clicked(p_id)
            )
            delete_btn.grid(row=0, column=2, padx=(5, 15), pady=5)

    def _on_create_clicked(self) -> None:
        """Event: creates a project using the text entry input."""
        name = self.name_entry.get().strip()
        if not name:
            self.main_window.show_error("Validation Error", "Project name field cannot be empty.")
            return

        # Create
        ratio_default = self.main_window.settings_mgr.aspect_ratio
        new_proj = self.main_window.project_mgr.create_project(name=name, aspect_ratio=ratio_default)
        self.main_window.set_active_project(new_proj)
        
        # Clear textbox
        self.name_entry.delete(0, ctk.END)
        self._refresh_project_list()
        self.main_window.update_status(f"Project '{name}' successfully established.")

    def _on_open_clicked(self, project: Project) -> None:
        """Event: opens selected project context and routes view back to Dashboard."""
        self.main_window.set_active_project(project)
        self.main_window.show_view("dashboard")

    def _on_delete_clicked(self, project_id: str) -> None:
        """Event: deletes a project directory and updates active context if needed."""
        # Check active context
        if self.main_window.current_project and self.main_window.current_project.id == project_id:
            self.main_window.set_active_project(None)

        success = self.main_window.project_mgr.delete_project(project_id)
        if success:
            self._refresh_project_list()
            self.main_window.update_status("Project successfully removed.")
        else:
            self.main_window.show_error("Deletion Error", "Could not remove project folder from workspace disk.")
        self._refresh_project_list()
