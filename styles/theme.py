# ==========================================================
# Brian Fitness Tracker X
# Executive Design System
# ==========================================================

from dataclasses import dataclass

@dataclass(frozen=True)
class Theme:
    BACKGROUND = "#08111F"

    CARD = "#121C2E"
    CARD_ALT = "#172338"

    PRIMARY = "#3B82F6"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    DANGER = "#EF4444"
    AI = "#8B5CF6"

    TEXT = "#FFFFFF"
    TEXT_SECONDARY = "#B8C2D1"

    BORDER = "#24334A"

    RADIUS = 18

    SHADOW = """
    0px 12px 24px rgba(0,0,0,.35)
    """

    PAGE_PADDING = 24
