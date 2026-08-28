"""Logs View for AI News Studio.

Subscribes to standard logger updates and streams them into a read-only console card.
"""

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.theme import Theme

if TYPE_CHECKING:
    from app.gui import MainWindow


class LogsView(ctk.CTkFrame):
    """View demonstrating live rolling terminal of active logger operations."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize LogsView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self._tracking_paused = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_console_card()

    def _create_header(self) -> None:
        """Create view title."""
        header_f = ctk.CTkFrame(self, fg_color="transparent")
        header_f.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_f.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_f,
            text="System Logs Console",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w")

        # Controls row
        ctrls_f = ctk.CTkFrame(header_f, fg_color="transparent")
        ctrls_f.grid(row=0, column=1, sticky="e")

        # Pause Checkbox
        self.chk_pause = ctk.CTkCheckBox(
            ctrls_f,
            text="Pause Auto Scroll",
            font=Theme.get_font(11),
            text_color=Theme.TEXT_PRIMARY,
            checkmark_color=Theme.TEXT_ON_ACCENT,
            fg_color=Theme.ACCENT,
            command=self._on_pause_toggled
        )
        self.chk_pause.grid(row=0, column=0, padx=10)

        # Clear Button
        ctk.CTkButton(
            ctrls_f,
            text="Clear Console",
            font=Theme.get_font(11, "bold"),
            width=100,
            height=28,
            fg_color=Theme.BG_CARD,
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.BG_CARD_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            command=self._on_clear_clicked
        ).grid(row=0, column=1, padx=5)

    def _create_console_card(self) -> None:
        """Construct read-only console textbox."""
        card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        card.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self.console_textbox = ctk.CTkTextbox(
            card,
            font=("Courier New", 12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 2
        )
        self.console_textbox.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        # Configure standard tag fonts/colors
        # Note: tkinter supports tags for coloring segments of text
        self.console_textbox.configure(state="disabled")

    def on_show(self) -> None:
        """Hook callback to logger ui_handler to read stream updates."""
        # Retrieve handler from MainWindow initialized during bootstrap
        # We can grab it from root logger
        root_logger = logging.getLogger()
        
        # Search handlers
        ui_handler = None
        for h in root_logger.handlers:
            if h.__class__.__name__ == "UIQueueHandler":
                ui_handler = h
                break

        if ui_handler:
            # Register callback
            ui_handler.register_callback(self._append_log_line)
            self._logger.debug("Successfully registered console view callback to UIQueueHandler.")
        else:
            self._logger.warning("Could not resolve active UIQueueHandler from logger.")

    def on_hide(self) -> None:
        """Unsubscribe callback when navigating away to avoid leak."""
        root_logger = logging.getLogger()
        ui_handler = None
        for h in root_logger.handlers:
            if h.__class__.__name__ == "UIQueueHandler":
                ui_handler = h
                break

        if ui_handler:
            ui_handler.unregister_callback(self._append_log_line)
            self._logger.debug("Unsubscribed console view from UIQueueHandler.")

    def _append_log_line(self, line: str) -> None:
        """Receive log line and write into text area.

        Args:
            line: Formatted string containing log message.
        """
        if self._tracking_paused:
            return

        # Execute inside UI safety queue using after
        self.console_textbox.after(0, lambda: self._write_to_textbox(line))

    def _write_to_textbox(self, line: str) -> None:
        """Insert string inside tkinter context and scroll to bottom."""
        try:
            self.console_textbox.configure(state="normal")
            self.console_textbox.insert(ctk.END, line + "\n")
            
            # Format rows based on keyword content
            # e.g. color line based on ERROR/WARNING
            # Simple text insertion suffices as a robust core.
            
            self.console_textbox.configure(state="disabled")
            
            # Scroll to end
            self.console_textbox.see(ctk.END)
        except Exception:
            pass  # Avoid errors if widget is destroyed mid-write

    def _on_pause_toggled(self) -> None:
        """Pause rolling monitor."""
        self._tracking_paused = self.chk_pause.get() == 1

    def _on_clear_clicked(self) -> None:
        """Clear text display contents."""
        self.console_textbox.configure(state="normal")
        self.console_textbox.delete("1.0", ctk.END)
        self.console_textbox.configure(state="disabled")
