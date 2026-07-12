from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    page_max_width: int = 1400
    space_xs: str = "6px"
    space_sm: str = "10px"
    space_md: str = "14px"
    space_lg: str = "20px"
    space_xl: str = "28px"

    radius_sm: str = "10px"
    radius_md: str = "16px"
    radius_lg: str = "22px"

    border_subtle: str = "1px solid rgba(96, 165, 250, 0.20)"
    border_strong: str = "1px solid rgba(96, 165, 250, 0.38)"

    shadow_soft: str = "0 10px 28px rgba(0, 0, 0, 0.24)"
    shadow_card: str = "0 16px 44px rgba(0, 0, 0, 0.32)"

    button_height: str = "46px"

    text_body: str = "#E5EEF9"
    text_muted: str = "#AFC4DB"
    text_heading: str = "#FFFFFF"

    status_success: str = "#22C55E"
    status_warning: str = "#F59E0B"
    status_error: str = "#EF4444"
    status_info: str = "#38BDF8"


TOKENS = DesignTokens()
