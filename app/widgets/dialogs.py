"""Custom Dialogs and Popups for AI News Studio.

Implements reusable visual alert windows that conform to the design theme.
"""

import customtkinter as ctk

from app.theme import Theme


class ErrorDialog(ctk.CTkToplevel):
    """A modal popup dialog for displaying application errors and crash traces."""

    def __init__(self, parent: ctk.CTk, title: str, message: str) -> None:
        """Initialize the ErrorDialog.

        Args:
            parent: MainWindow application context.
            title: Title text of the error box.
            message: Multi-line string detailing the error message.
        """
        super().__init__(parent)

        self.title("System Notification")
        self.geometry("460x220")
        self.resizable(False, False)
        
        # Center popup relative to parent
        self.transient(parent)
        self.update_idletasks()
        
        # Calculate coordinate offsets
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        
        x = px + (pw - 460) // 2
        y = py + (ph - 220) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Styling window frame background
        self.configure(fg_color=Theme.BG_CARD)

        # Layout grids
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            self,
            text=f"⚠️ {title}",
            font=Theme.get_font(15, "bold"),
            text_color=Theme.DANGER
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Message Text
        msg_textbox = ctk.CTkTextbox(
            self,
            font=Theme.get_font(12),
            fg_color=Theme.BG_MAIN,
            text_color=Theme.TEXT_PRIMARY,
            border_width=Theme.BORDER_WIDTH,
            border_color=Theme.BORDER_COLOR,
            corner_radius=Theme.CORNER_RADIUS - 4
        )
        msg_textbox.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="nsew")
        msg_textbox.insert("1.0", message)
        msg_textbox.configure(state="disabled")

        # Close button
        ok_btn = ctk.CTkButton(
            self,
            text="Close Alert",
            font=Theme.get_font(12, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            corner_radius=Theme.CORNER_RADIUS - 4,
            height=32,
            width=100,
            command=self.destroy
        )
        ok_btn.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="e")
