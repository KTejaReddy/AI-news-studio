"""Settings/Preferences View for AI News Studio.

Binds configurations from SettingsManager to editable dropdowns and path inputs.
"""

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.theme import Theme

if TYPE_CHECKING:
    from app.gui import MainWindow


class SettingsView(ctk.CTkFrame):
    """System preferences view managing paths, UI styles, and compute devices."""

    def __init__(self, parent: ctk.CTkFrame, main_window: "MainWindow") -> None:
        """Initialize SettingsView.

        Args:
            parent: Parent container frame.
            main_window: Main application window reference.
        """
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self._logger = logging.getLogger(self.__class__.__name__)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_content()

    def _create_header(self) -> None:
        """Create view title."""
        ctk.CTkLabel(
            self,
            text="System Preferences",
            font=Theme.get_font(24, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    def _create_content(self) -> None:
        """Construct scrollable settings layout form."""
        self.scroll_card = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR
        )
        self.scroll_card.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # --- Section: Styling & Locale ---
        ctk.CTkLabel(
            self.scroll_card,
            text="User Interface & Localization",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Theme Selector
        ctk.CTkLabel(
            self.scroll_card,
            text="Appearance Mode (Theme):",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.theme_opt = ctk.CTkOptionMenu(
            self.scroll_card,
            values=["dark", "light", "system"],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.theme_opt.pack(fill="x", padx=15, pady=(0, 15))

        # Language Selector
        ctk.CTkLabel(
            self.scroll_card,
            text="System Language:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.lang_opt = ctk.CTkOptionMenu(
            self.scroll_card,
            values=["en", "es", "fr", "de"],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.lang_opt.pack(fill="x", padx=15, pady=(0, 15))

        # --- Section: Hardware & Compute ---
        ctk.CTkLabel(
            self.scroll_card,
            text="Hardware Acceleration",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Device mode
        ctk.CTkLabel(
            self.scroll_card,
            text="Primary Compute Engine:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.device_opt = ctk.CTkOptionMenu(
            self.scroll_card,
            values=["GPU", "CPU"],
            font=Theme.get_font(12),
            dropdown_font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.BG_CARD
        )
        self.device_opt.pack(fill="x", padx=15, pady=(0, 15))

        # --- Section: Folder paths configuration ---
        ctk.CTkLabel(
            self.scroll_card,
            text="Directories Configuration",
            font=Theme.get_font(16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Output Folder Path
        ctk.CTkLabel(
            self.scroll_card,
            text="Output Video Directory:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.output_entry = ctk.CTkEntry(
            self.scroll_card,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.output_entry.pack(fill="x", padx=15, pady=(0, 15))

        # Models Folder Path
        ctk.CTkLabel(
            self.scroll_card,
            text="Model Weights Directory:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.model_entry = ctk.CTkEntry(
            self.scroll_card,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.model_entry.pack(fill="x", padx=15, pady=(0, 15))

        # Cache Folder Path
        ctk.CTkLabel(
            self.scroll_card,
            text="System Cache Directory:",
            font=Theme.get_font(12, "bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.cache_entry = ctk.CTkEntry(
            self.scroll_card,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32
        )
        self.cache_entry.pack(fill="x", padx=15, pady=(0, 15))

        # Save Button
        save_btn = ctk.CTkButton(
            self.scroll_card,
            text="💾 Save Preferences",
            font=Theme.get_font(13, "bold"),
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=38,
            command=self._on_save_clicked
        )
        save_btn.pack(padx=15, pady=25)

    def on_show(self) -> None:
        """Hydrate inputs from SettingsManager data fields when view activates."""
        self.theme_opt.set(self.main_window.settings_mgr.theme)
        self.lang_opt.set(self.main_window.settings_mgr.language)
        self.device_opt.set(self.main_window.settings_mgr.device_mode)

        self.output_entry.delete(0, ctk.END)
        self.output_entry.insert(0, self.main_window.settings_mgr.output_folder)

        self.model_entry.delete(0, ctk.END)
        self.model_entry.insert(0, self.main_window.settings_mgr.model_folder)

        self.cache_entry.delete(0, ctk.END)
        self.cache_entry.insert(0, self.main_window.settings_mgr.cache_folder)

    def _on_save_clicked(self) -> None:
        """Write visual configurations back to SettingsManager."""
        theme = self.theme_opt.get()
        lang = self.lang_opt.get()
        device = self.device_opt.get()
        output_f = self.output_entry.get().strip()
        model_f = self.model_entry.get().strip()
        cache_f = self.cache_entry.get().strip()

        # Input Validations
        if not output_f or not model_f or not cache_f:
            self.main_window.show_error("Validation Error", "Directory folders paths cannot be left empty.")
            return

        try:
            self.main_window.settings_mgr.theme = theme
            self.main_window.settings_mgr.language = lang
            self.main_window.settings_mgr.device_mode = device
            self.main_window.settings_mgr.output_folder = output_f
            self.main_window.settings_mgr.model_folder = model_f
            self.main_window.settings_mgr.cache_folder = cache_f

            self._logger.info("Preferences successfully updated on disk configuration JSON.")
            self.main_window.update_status("System settings updated successfully.")
        except Exception as e:
            self._logger.error(f"Failed to update preferences: {e}")
            self.main_window.show_error("Save Error", f"Failed to save configurations: {e}")
