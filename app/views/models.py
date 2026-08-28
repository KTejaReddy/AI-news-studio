"""Models Download View for AI News Studio.

Displays the installation status of AI model weights and provides triggers
to download/delete them.
"""

import logging
import threading
import time
from typing import TYPE_CHECKING, Dict, List

import customtkinter as ctk

from app.theme import Theme

if TYPE_CHECKING:
    from app.gui import MainWindow


class ModelsView(ctk.CTkFrame):
    """View demonstrating required neural model files and managing downloads/deletes."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize ModelsView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._active_downloads: Dict[str, bool] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_list_card()

    def _create_header(self) -> None:
        """Create view title."""
        ctk.CTkLabel(
            self,
            text="Model Weights Center",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    def _create_list_card(self) -> None:
        """Construct scroll container card."""
        self.list_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.list_card.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.list_card.grid_columnconfigure(0, weight=1)
        self.list_card.grid_rowconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(
            self.list_card,
            text="Required AI Models Configuration",
            font=Theme.get_font(14, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

        # Scroll Frame
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.list_card,
            fg_color="transparent"
        )
        self.scroll_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def on_show(self) -> None:
        """Fetch model files status when view is focused."""
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Redraw all model elements."""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        statuses = self.main_window.model_mgr.get_model_status()

        for m in statuses:
            m_id = m["id"]
            
            card = ctk.CTkFrame(
                self.scroll_frame,
                fg_color=Theme.BG_MAIN,
                corner_radius=Theme.CORNER_RADIUS - 4,
                border_width=Theme.BORDER_WIDTH,
                border_color=Theme.BORDER_COLOR
            )
            card.pack(fill="x", pady=6, ipady=6)
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)

            # Left side metadata
            meta_frame = ctk.CTkFrame(card, fg_color="transparent")
            meta_frame.grid(row=0, column=0, padx=15, pady=10, sticky="w")

            ctk.CTkLabel(
                meta_frame,
                text=m["name"],
                font=Theme.get_font(13, "bold"),
                text_color=Theme.TEXT_PRIMARY
            ).pack(anchor="w")

            ctk.CTkLabel(
                meta_frame,
                text=m["description"],
                font=Theme.get_font(11),
                text_color=Theme.TEXT_MUTED,
                wraplength=550,
                justify="left"
            ).pack(anchor="w", pady=2)

            # Status details
            if m["installed"]:
                status_text = f"Installed ({m['actual_size_gb']} GB)"
                status_color = Theme.SUCCESS
            else:
                status_text = f"Missing (Requires {m['expected_size_gb']} GB)"
                status_color = Theme.DANGER

            ctk.CTkLabel(
                meta_frame,
                text=f"Status: {status_text}  |  File: {m['filename']}",
                font=Theme.get_font(11, "bold"),
                text_color=status_color
            ).pack(anchor="w")

            # Check if active download session exists
            is_downloading = self._active_downloads.get(m_id, False)

            if is_downloading:
                # Show loading text
                ctk.CTkLabel(
                    card,
                    text="⚡ Downloading...",
                    font=Theme.get_font(11, "bold"),
                    text_color=Theme.WARNING
                ).grid(row=0, column=1, padx=15, pady=10)
            else:
                # Action Buttons
                if m["installed"]:
                    action_btn = ctk.CTkButton(
                        card,
                        text="🗑️ Delete File",
                        font=Theme.get_font(11, "bold"),
                        width=120,
                        height=28,
                        fg_color=Theme.DANGER,
                        hover_color=Theme.DANGER,
                        corner_radius=Theme.CORNER_RADIUS - 4,
                        command=lambda m_id=m_id: self._on_delete_clicked(m_id)
                    )
                else:
                    action_btn = ctk.CTkButton(
                        card,
                        text="📥 Download",
                        font=Theme.get_font(11, "bold"),
                        width=120,
                        height=28,
                        fg_color=Theme.ACCENT,
                        hover_color=Theme.ACCENT_HOVER,
                        corner_radius=Theme.CORNER_RADIUS - 4,
                        command=lambda m_id=m_id: self._on_download_clicked(m_id)
                    )
                action_btn.grid(row=0, column=1, padx=15, pady=10)

    def _on_download_clicked(self, model_id: str) -> None:
        """Trigger simulated model downloading thread."""
        if self._active_downloads.get(model_id, False):
            return

        self._active_downloads[model_id] = True
        self._refresh_list()
        self.main_window.update_status("Starting weight download connection...")

        # Spawn download simulation thread
        thread = threading.Thread(target=self._simulate_download, args=(model_id,), daemon=True)
        thread.start()

    def _simulate_download(self, model_id: str) -> None:
        """Background downloader sequence simulating file bytes loading.

        Args:
            model_id: The ID of the model weights to install.
        """
        def progress(pct: float) -> None:
            # Output download status
            self.main_window.update_status(f"Downloading model ({int(pct * 100)}%)")

        success = self.main_window.model_mgr.install_mock_model(model_id, progress_callback=progress)
        
        # Clear active session
        self._active_downloads[model_id] = False
        
        # Redraw
        if success:
            self.main_window.update_status("Model weights downloaded successfully.")
        else:
            self.main_window.update_status("Model download failed.")

        self.scroll_frame.after(0, self._refresh_list)

    def _on_delete_clicked(self, model_id: str) -> None:
        """Remove model weights from directory."""
        success = self.main_window.model_mgr.remove_model(model_id)
        if success:
            self.main_window.update_status("Weights file deleted.")
        else:
            self.main_window.show_error("Cleanup Error", "Could not delete file from system folders.")
        self._refresh_list()
