from __future__ import annotations

import html
from pathlib import Path
from typing import Dict

import streamlit as st

from components.exercise_image_gallery import render_exercise_image_gallery
from components.exercise_progression_panel import render_exercise_progression_panel
from components.muscle_focus_panel import render_muscle_focus_panel


_DETAIL_CSS = """
<style>
.titan-detail-shell {display:grid;gap:18px;}
.titan-title-block {border:1px solid rgba(96,165,250,.2);border-radius:26px;padding:22px 24px;background:radial-gradient(circle at 4% -30%,rgba(37,99,235,.18),transparent 48%),linear-gradient(180deg,rgba(10,20,34,.98),rgba(7,17,31,.98));box-shadow:0 18px 46px rgba(0,0,0,.24);}
.titan-title-row {display:flex;align-items:flex-start;justify-content:space-between;gap:16px;}
.titan-eyebrow {font-size:.76rem;letter-spacing:.22em;text-transform:uppercase;color:#86c5ff;font-weight:900;}
.titan-title {margin-top:8px;font-size:2.2rem;line-height:1.02;color:#fff;font-weight:950;}
.titan-sub {margin-top:8px;color:#a9bad1;font-size:.97rem;max-width:760px;line-height:1.6;}
.titan-tag-row {display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;}
.titan-tag {padding:7px 12px;border-radius:999px;background:rgba(17,37,61,.95);border:1px solid rgba(96,165,250,.2);color:#dbeafe;font-size:.82rem;font-weight:800;}
.titan-fav {padding:10px 14px;border-radius:14px;border:1px solid rgba(148,163,184,.16);background:rgba(11,19,34,.9);color:#dce6f5;font-size:.86rem;font-weight:800;white-space:nowrap;box-shadow:inset 0 0 0 1px rgba(255,255,255,.03);}
.titan-meta-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px;}
.titan-meta-card {border:1px solid rgba(148,163,184,.14);border-radius:16px;padding:14px;background:rgba(11,24,40,.78);}
.titan-meta-label {font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;color:#8fb5df;font-weight:900;}
.titan-meta-value {margin-top:8px;color:#fff;font-size:.95rem;line-height:1.45;font-weight:850;}
.titan-rating-row {display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:16px;}
.titan-star-wrap {display:flex;gap:4px;align-items:center;padding:8px 10px;border-radius:12px;background:rgba(11,24,40,.78);border:1px solid rgba(148,163,184,.14);}
.titan-star {font-size:1rem;color:#fbbf24;}
.titan-icon-wrap {display:flex;gap:8px;flex-wrap:wrap;}
.titan-icon-pill {padding:8px 10px;border-radius:12px;background:rgba(11,30,50,.66);border:1px solid rgba(148,163,184,.16);color:#d6e3f7;font-size:.82rem;font-weight:800;}
.titan-card-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;}
.titan-copy-card {border:1px solid rgba(96,165,250,.16);border-radius:22px;padding:18px;background:linear-gradient(180deg,rgba(15,31,52,.96),rgba(7,17,31,.98));box-shadow:0 14px 34px rgba(0,0,0,.18);position:relative;overflow:hidden;}
.titan-copy-card:before {content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,rgba(96,165,250,.42),rgba(34,197,94,.35));}
.titan-copy-title {font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;font-weight:900;color:#93c5fd;margin-bottom:12px;}
.titan-copy-list {margin:0;padding-left:18px;color:#dce5f3;line-height:1.7;font-size:.95rem;}
.titan-copy-list li {margin-bottom:8px;}
.titan-variation-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}
.titan-variation {border:1px solid rgba(148,163,184,.16);border-radius:16px;padding:12px;background:linear-gradient(180deg,rgba(9,21,36,.96),rgba(6,14,24,.94));color:#eef4ff;font-size:.88rem;font-weight:800;min-height:88px;display:flex;align-items:flex-end;}
@media (max-width: 900px) {
    .titan-meta-grid,.titan-card-grid,.titan-variation-grid {grid-template-columns:1fr;}
  .titan-title-row {flex-direction:column;}
    .titan-title {font-size:1.8rem;}
}
</style>
"""


def _list_card(title: str, items, accent: str) -> str:
    safe_items = items or ["No coaching notes loaded yet."]
    list_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in safe_items)
    return (
        '<div class="titan-copy-card" style="border-color:' + accent + '26;">'
        f'<div class="titan-copy-title" style="color:{accent};">{html.escape(title)}</div>'
        f'<ul class="titan-copy-list">{list_html}</ul>'
        '</div>'
    )


def _difficulty_stars(difficulty: str) -> str:
    text = str(difficulty or "Intermediate").lower()
    count = 2 if "beginner" in text else 4 if "advanced" in text else 3
    stars = "".join('<span class="titan-star">★</span>' for _ in range(count))
    stars += "".join('<span class="titan-star" style="opacity:.22;">★</span>' for _ in range(5 - count))
    return stars


def render_exercise_detail_panel(exercise_data: Dict, assets_dir: Path) -> None:
    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)

    tags = exercise_data.get("tags", []) or []
    if exercise_data.get("muscle_group") and exercise_data["muscle_group"] not in tags:
        tags = [exercise_data["muscle_group"]] + tags
    equipment_icons = exercise_data.get("equipment_icons", []) or ["General"]

    header_html = (
        '<div class="titan-title-block">'
        '<div class="titan-title-row">'
        '<div>'
        '<div class="titan-eyebrow">Exercise Library</div>'
        f'<div class="titan-title">{html.escape(str(exercise_data.get("exercise", "Exercise")))}</div>'
        f'<div class="titan-sub">{html.escape(str(exercise_data.get("summary", "Detailed coaching notes, muscle focus, and image guidance for your current Project Titan movement library.")))}</div>'
        '<div class="titan-tag-row">'
        f'{"".join(f"<span class=\"titan-tag\">{html.escape(str(tag))}</span>" for tag in tags[:8])}'
        '</div>'
        '<div class="titan-rating-row">'
        f'<div class="titan-star-wrap">{_difficulty_stars(str(exercise_data.get("difficulty", "Intermediate")))}</div>'
        '<div class="titan-icon-wrap">'
        f'{"".join(f"<span class=\"titan-icon-pill\">{html.escape(str(item))}</span>" for item in equipment_icons)}'
        '</div>'
        '</div>'
        '<div class="titan-meta-grid">'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Category</div><div class="titan-meta-value">{html.escape(str(exercise_data.get("category", exercise_data.get("muscle_group", "General"))))}</div></div>'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Equipment</div><div class="titan-meta-value">{html.escape(str(exercise_data.get("equipment", "Bodyweight")))}</div></div>'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Difficulty</div><div class="titan-meta-value">{html.escape(str(exercise_data.get("difficulty", "Intermediate")))}</div></div>'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Primary Muscles</div><div class="titan-meta-value">{html.escape(", ".join(exercise_data.get("primary_muscles", []) or ["Unknown"]))}</div></div>'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Secondary Muscles</div><div class="titan-meta-value">{html.escape(", ".join(exercise_data.get("secondary_muscles", []) or ["N/A"]))}</div></div>'
        f'<div class="titan-meta-card"><div class="titan-meta-label">Stabilizers</div><div class="titan-meta-value">{html.escape(", ".join(exercise_data.get("stabilizers", []) or ["Core"]))}</div></div>'
        '</div>'
        '</div>'
        '<div class="titan-fav">☆ Premium Detail</div>'
        '</div>'
        '</div>'
    )

    left, right = st.columns([1.75, 1.0], gap="large")
    with left:
        st.markdown(header_html, unsafe_allow_html=True)
        render_exercise_image_gallery(exercise_data, assets_dir)
        st.markdown(
            '<div class="titan-card-grid">'
            + _list_card("Instructions", exercise_data.get("instructions", []), "#60a5fa")
            + _list_card("AI Coaching Tips", exercise_data.get("tips", []), "#22c55e")
            + _list_card("Common Mistakes", exercise_data.get("common_mistakes", []), "#f59e0b")
            + '<div class="titan-copy-card">'
            '<div class="titan-copy-title" style="color:#d8b4fe;">Variations</div>'
            '<div class="titan-variation-grid">'
            + "".join(f'<div class="titan-variation">{html.escape(str(item))}</div>' for item in (exercise_data.get("variations", []) or ["Variation slot reserved"]))
            + '</div></div></div>',
            unsafe_allow_html=True,
        )
    with right:
        render_muscle_focus_panel(exercise_data)
        render_exercise_progression_panel(exercise_data)
