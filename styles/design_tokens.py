from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    page_max_width: int = 1400
    page_gutter: str = "14px"
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
    button_gap: str = "10px"

    font_body: str = '"Manrope", "Segoe UI", sans-serif'
    font_heading: str = '"Sora", "Manrope", sans-serif'
    font_size_body: str = "0.98rem"
    font_size_caption: str = "0.82rem"
    font_size_h1: str = "2.1rem"
    font_size_h2: str = "1.45rem"
    font_size_h3: str = "1.1rem"

    motion_fast: str = "0.16s"
    motion_normal: str = "0.24s"
    motion_curve: str = "cubic-bezier(0.2, 0.8, 0.2, 1)"

    text_body: str = "#E5EEF9"
    text_muted: str = "#AFC4DB"
    text_heading: str = "#FFFFFF"

    status_success: str = "#22C55E"
    status_warning: str = "#F59E0B"
    status_error: str = "#EF4444"
    status_info: str = "#38BDF8"


TOKENS = DesignTokens()
