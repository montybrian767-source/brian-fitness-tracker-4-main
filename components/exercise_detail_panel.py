from __future__ import annotations

import html
from pathlib import Path
from typing import Dict

import streamlit as st

from components.exercise_image_gallery import render_exercise_image_gallery
from components.exercise_progression_panel import render_exercise_progression_panel
from components.muscle_focus_panel import render_muscle_focus_panel
from engines.muscle_readiness_engine import get_readiness_for_muscle_list


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
.titan-recovery-card {margin-top:14px;border:1px solid rgba(34,197,94,.2);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(9,25,20,.72),rgba(7,17,31,.95));}
.titan-recovery-title {font-family:"Space Grotesk","Sora","Avenir Next","Segoe UI",sans-serif;font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;color:#86efac;font-weight:900;margin-bottom:10px;}
.titan-recovery-row {display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
.titan-recovery-pill {font-family:"Manrope","Avenir Next","Segoe UI",sans-serif;padding:6px 10px;border-radius:999px;border:1px solid rgba(148,163,184,.2);font-size:.79rem;font-weight:850;color:#e8eef9;background:rgba(11,24,40,.7);line-height:1.3;}
.titan-recovery-warning {font-family:"Manrope","Avenir Next","Segoe UI",sans-serif;margin-top:10px;padding:10px 12px;border-radius:12px;border:1px solid rgba(239,68,68,.45);background:rgba(127,29,29,.35);color:#fecaca;font-size:.86rem;font-weight:700;line-height:1.45;}
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


def _recovery_color(status: str) -> str:
    s = str(status or "").lower()
    if s in {"green", "ready"}:
        return "#22c55e"
    if s in {"yellow", "moderate"}:
        return "#f59e0b"
    if s in {"orange", "recovering"}:
        return "#f97316"
    if s in {"red", "fatigued", "recover"}:
        return "#ef4444"
    return "#94a3b8"


def _recovery_markup(exercise_data: Dict, muscle_snapshot: Dict) -> str:
    primary = get_readiness_for_muscle_list(muscle_snapshot, exercise_data.get("primary_muscles", []) or [])
    secondary = get_readiness_for_muscle_list(muscle_snapshot, exercise_data.get("secondary_muscles", []) or [])
    stabilizers = get_readiness_for_muscle_list(muscle_snapshot, exercise_data.get("stabilizers", []) or [])

    if not primary and not secondary and not stabilizers:
        return (
            '<div class="titan-recovery-card">'
            '<div class="titan-recovery-title">Muscle Readiness Overlay</div>'
            '<div class="titan-recovery-row"><span class="titan-recovery-pill">Recovery guidance will appear after workout and recovery logs are available.</span></div>'
            '</div>'
        )

    def _row(items, label):
        if not items:
            return f'<div class="titan-recovery-row"><span class="titan-recovery-pill">{label}: No mapped muscles</span></div>'
        pills = []
        for item in items:
            status = str(item.get("status", "Unknown"))
            pct = int(item.get("readiness_percent", 0) or 0)
            status_label = str(item.get("status_label", status))
            weekly_volume = int(item.get("weekly_volume", 0) or 0)
            color = _recovery_color(status)
            pills.append(f'<span class="titan-recovery-pill" style="border-color:{color};">{html.escape(str(item.get("muscle", "muscle")).title())}: {pct}% • {html.escape(status_label)} • {weekly_volume:,} lbs/wk</span>')
        return f'<div class="titan-recovery-row"><span class="titan-recovery-pill">{label}</span>{"".join(pills)}</div>'

    warning_targets = [item for item in primary if str(item.get("status", "")) in {"Orange", "Red"}]
    warning = ""
    if warning_targets:
        names = ", ".join(str(item.get("muscle", "")).title() for item in warning_targets[:3])
        warning = f'<div class="titan-recovery-warning">Warning: primary target muscles are not ready ({html.escape(names)}). Reduce load or choose a different focus.</div>'

    return (
        '<div class="titan-recovery-card">'
        '<div class="titan-recovery-title">Muscle Readiness Overlay</div>'
        f'{_row(primary, "Primary")}'
        f'{_row(secondary, "Secondary")}'
        f'{_row(stabilizers, "Stabilizers")}'
        f'{warning}'
        '</div>'
    )


def render_exercise_detail_panel(exercise_data: Dict, assets_dir: Path, muscle_snapshot: Dict | None = None) -> None:
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
        st.markdown(_recovery_markup(exercise_data, muscle_snapshot or {}), unsafe_allow_html=True)
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
