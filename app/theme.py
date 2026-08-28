"""Design Tokens and Theme Constants for AI News Studio.

Defines the color palettes, fonts, borders, and margins to ensure visual consistency
across the entire user interface.
"""

from typing import Tuple


class Theme:
    """Design system constants matching modern, premium, dark-first aesthetics."""

    # Brand Colors (Light, Dark)
    ACCENT: Tuple[str, str] = ("#4F46E5", "#6366F1")         # Indigo (light mode: dark indigo, dark mode: bright indigo)
    ACCENT_HOVER: Tuple[str, str] = ("#4338CA", "#4F46E5")   # Indigo Hover
    
    # Status Colors
    SUCCESS: Tuple[str, str] = ("#059669", "#10B981")        # Emerald
    WARNING: Tuple[str, str] = ("#D97706", "#F59E0B")        # Amber
    DANGER: Tuple[str, str] = ("#DC2626", "#EF4444")         # Rose
    INFO: Tuple[str, str] = ("#2563EB", "#3B82F6")           # Blue

    # Neutrals & Panels
    BG_MAIN: Tuple[str, str] = ("#F9FAFB", "#0F0F11")        # Main background (light: off-white, dark: deep charcoal)
    BG_SIDEBAR: Tuple[str, str] = ("#F3F4F6", "#09090A")     # Sidebar background (light: slate-100, dark: near-black)
    BG_CARD: Tuple[str, str] = ("#FFFFFF", "#18181C")        # Cards and containers (light: pure white, dark: zinc-900)
    BG_CARD_HOVER: Tuple[str, str] = ("#F3F4F6", "#202025")  # Cards hover states
    
    # Text Neutral
    TEXT_PRIMARY: Tuple[str, str] = ("#111827", "#F4F4F5")   # Primary text (light: slate-900, dark: zinc-100)
    TEXT_SECONDARY: Tuple[str, str] = ("#4B5563", "#A1A1AA") # Secondary text (light: slate-600, dark: zinc-400)
    TEXT_MUTED: Tuple[str, str] = ("#9CA3AF", "#71717A")     # Muted labels (light: slate-400, dark: zinc-500)
    TEXT_ON_ACCENT: Tuple[str, str] = ("#FFFFFF", "#FFFFFF") # Text overlaid on solid accent color

    # Borders
    BORDER_COLOR: Tuple[str, str] = ("#E5E7EB", "#27272A")   # Line dividers (light: gray-200, dark: zinc-800)

    # Layout Sizing
    CORNER_RADIUS: int = 10
    BORDER_WIDTH: int = 1
    
    # Typography
    FONT_FAMILY: str = "Segoe UI"
    
    @classmethod
    def get_font(cls, size: int = 12, weight: str = "normal") -> Tuple[str, int, str]:
        """Generate a font tuple for Tkinter configuration.

        Args:
            size: Font size in points.
            weight: Font weight (e.g. 'normal', 'bold').

        Returns:
            Font tuple.
        """
        return (cls.FONT_FAMILY, size, weight)
