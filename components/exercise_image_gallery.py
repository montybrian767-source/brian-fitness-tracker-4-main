from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Dict, Optional

import streamlit as st


_GALLERY_CSS = """
<style>
.titan-gallery {display:grid;gap:16px;}
.titan-gallery-hero {border:1px solid rgba(96,165,250,.26);border-radius:26px;padding:18px;background:radial-gradient(circle at 0% -28%,rgba(37,99,235,.22),transparent 42%),linear-gradient(160deg,#0f1f34,#081322);box-shadow:0 20px 48px rgba(0,0,0,.24);}
.titan-gallery-hero-media {aspect-ratio: 16 / 10;border-radius:18px;background:radial-gradient(circle at top,#11263f,#06101d 68%);display:flex;align-items:center;justify-content:center;overflow:hidden;border:1px solid rgba(148,163,184,.16);}
.titan-gallery-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;}
.titan-gallery-slot {border:1px solid rgba(96,165,250,.18);border-radius:18px;padding:12px;background:linear-gradient(180deg,rgba(15,31,52,.96),rgba(7,17,31,.96));}
.titan-gallery-slot-media {aspect-ratio: 5 / 4;border-radius:14px;background:radial-gradient(circle at top,#11263f,#06101d 72%);display:flex;align-items:center;justify-content:center;overflow:hidden;border:1px solid rgba(148,163,184,.14);}
.titan-gallery-slot-title {margin-top:10px;font-size:.8rem;letter-spacing:.18em;text-transform:uppercase;color:#93c5fd;font-weight:900;}
.titan-gallery-slot-sub {margin-top:6px;color:#c8d3e6;font-size:.9rem;line-height:1.45;}
.titan-gallery-image {width:100%;height:100%;object-fit:contain;display:block;filter:drop-shadow(0 12px 18px rgba(0,0,0,.18));}
.titan-gallery-placeholder {width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:18px;color:#dbeafe;background:linear-gradient(135deg,rgba(29,124,255,.1),rgba(34,197,94,.08));}
.titan-gallery-placeholder-kicker {font-size:.74rem;letter-spacing:.2em;text-transform:uppercase;color:#86c5ff;font-weight:900;margin-bottom:10px;}
.titan-gallery-placeholder-title {font-size:1.05rem;font-weight:900;color:#fff;}
.titan-gallery-placeholder-sub {margin-top:8px;font-size:.88rem;color:#b9c5d9;max-width:220px;line-height:1.45;}
@media (max-width: 900px) {
  .titan-gallery-grid {grid-template-columns:1fr;}
}
</style>
"""


def _image_to_data_uri(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _resolve_image_path(assets_dir: Path, image_name: str) -> Optional[Path]:
    image_name = str(image_name or "").strip()
    if not image_name:
        return None
    path = assets_dir / image_name
    if path.exists():
        return path
    alt = Path(image_name)
    if alt.exists():
        return alt
    return None


def _resolve_slot_path(exercise_data: Dict, assets_dir: Path, slot_key: str, explicit_name: str) -> Optional[Path]:
    explicit = _resolve_image_path(assets_dir, explicit_name)
    if explicit:
        return explicit

    folder_name = str(exercise_data.get("asset_folder", "")).strip()
    if not folder_name:
        return None

    slot_aliases = {
        "hero": ["hero", "hero_image", "main"],
        "start": ["start", "start_position"],
        "finish": ["finish", "end", "finish_position"],
        "side": ["side", "side_profile"],
        "top": ["top", "top_view"],
    }
    folder = assets_dir / folder_name
    if not folder.exists():
        return None

    for candidate in slot_aliases.get(slot_key, [slot_key]):
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            path = folder / f"{candidate}{ext}"
            if path.exists():
                return path
    return None


def _build_media_markup(title: str, image_name: str, assets_dir: Path, exercise_data: Dict, slot_key: str, featured: bool = False) -> str:
    path = _resolve_slot_path(exercise_data, assets_dir, slot_key, image_name)
    if path:
        data_uri = _image_to_data_uri(path)
        if data_uri:
            return f'<img class="titan-gallery-image" src="{data_uri}" alt="{html.escape(title)}" />'

    placeholder_title = "Primary Visual Ready" if featured else "Future Visual Slot"
    placeholder_sub = (
        "No approved image loaded yet. Add a higher-resolution reference without changing the layout."
        if featured
        else "Reserved for a cleaner coaching angle when better source images are available."
    )
    return (
        '<div class="titan-gallery-placeholder">'
        f'<div class="titan-gallery-placeholder-title">{html.escape(placeholder_title)}</div>'
        f'<div class="titan-gallery-placeholder-sub">{html.escape(placeholder_sub)}</div>'
        '</div>'
    )


def render_exercise_image_gallery(exercise_data: Dict, assets_dir: Path) -> None:
    st.markdown(_GALLERY_CSS, unsafe_allow_html=True)

    hero_image = exercise_data.get("hero_image") or exercise_data.get("start_image") or exercise_data.get("image_file") or ""
    slots = [
        ("Start Position", "start", exercise_data.get("start_image") or hero_image, "Setup and start alignment."),
        ("Finish Position", "finish", exercise_data.get("end_image"), "Peak contraction or finish position."),
        ("Side View", "side", exercise_data.get("side_image"), "Reserved for lateral mechanics and torso angle."),
        ("Top View", "top", exercise_data.get("top_image"), "Reserved for path, spacing, and symmetry cues."),
    ]

    hero_markup = _build_media_markup(str(exercise_data.get("exercise", "Exercise")), str(hero_image), assets_dir, exercise_data, "hero", featured=True)
    slot_markup = []
    for title, slot_key, image_name, subtitle in slots:
        slot_markup.append(
            '<div class="titan-gallery-slot">'
            f'<div class="titan-gallery-slot-media">{_build_media_markup(title, str(image_name or ""), assets_dir, exercise_data, slot_key)}</div>'
            f'<div class="titan-gallery-slot-title">{html.escape(title)}</div>'
            f'<div class="titan-gallery-slot-sub">{html.escape(subtitle)}</div>'
            '</div>'
        )

    st.markdown(
        (
            '<div class="titan-gallery">'
            '<div class="titan-gallery-hero">'
            f'<div class="titan-gallery-hero-media">{hero_markup}</div>'
            '</div>'
            '<div class="titan-gallery-grid">'
            f'{"".join(slot_markup)}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )
