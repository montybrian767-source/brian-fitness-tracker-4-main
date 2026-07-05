from __future__ import annotations

import html
from typing import Dict, List, Tuple

import streamlit as st


_PANEL_CSS = """
<style>
.titan-muscle-panel {display:grid;gap:14px;}
.titan-muscle-card {border:1px solid rgba(96,165,250,.18);border-radius:22px;padding:16px;background:linear-gradient(180deg,rgba(10,20,34,.98),rgba(7,17,31,.98));box-shadow:0 16px 40px rgba(0,0,0,.22);position:relative;overflow:hidden;}
.titan-muscle-card:before {content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,rgba(239,68,68,.55),rgba(245,158,11,.45),rgba(250,204,21,.4));}
.titan-muscle-card-title {font-size:.8rem;letter-spacing:.18em;text-transform:uppercase;color:#93c5fd;font-weight:900;margin-bottom:12px;}
.titan-muscle-diagrams {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;}
.titan-muscle-diagram {border:1px solid rgba(148,163,184,.12);border-radius:18px;padding:10px;background:radial-gradient(circle at top,#11263f,#07111f 70%);}
.titan-muscle-figure-title {margin-top:8px;color:#9cb6d8;font-size:.76rem;letter-spacing:.16em;text-transform:uppercase;font-weight:800;text-align:center;}
.titan-muscle-legend {display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;color:#d5deee;font-size:.82rem;}
.titan-muscle-legend span {display:inline-flex;align-items:center;gap:8px;}
.titan-muscle-dot {width:10px;height:10px;border-radius:999px;display:inline-block;}
.titan-highlight-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}
.titan-highlight {border-radius:12px;padding:10px;background:rgba(15,31,52,.76);border:1px solid rgba(148,163,184,.14);}
.titan-highlight-label {font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:#9cb6d8;font-weight:900;}
.titan-highlight-value {margin-top:6px;color:#fff;font-size:.85rem;line-height:1.45;font-weight:800;}
.titan-muscle-list {display:grid;gap:10px;}
.titan-muscle-row {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;}
.titan-muscle-name {color:#dbe5f4;font-size:.92rem;}
.titan-muscle-pct {color:#fff;font-weight:900;font-size:.88rem;}
.titan-muscle-bar {margin-top:6px;height:8px;border-radius:999px;background:#102033;overflow:hidden;border:1px solid rgba(148,163,184,.12);}
.titan-muscle-fill {height:100%;border-radius:999px;background:linear-gradient(90deg,#ef4444,#f59e0b);}
.titan-mini-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;}
.titan-mini-card {border:1px solid rgba(148,163,184,.12);border-radius:16px;padding:14px;background:rgba(15,31,52,.72);}
.titan-mini-label {font-size:.74rem;letter-spacing:.18em;text-transform:uppercase;color:#86c5ff;font-weight:900;}
.titan-mini-value {margin-top:8px;color:#fff;font-weight:900;font-size:1rem;line-height:1.4;}
.titan-pill-wrap {display:flex;gap:8px;flex-wrap:wrap;}
.titan-pill {padding:7px 10px;border-radius:999px;border:1px solid rgba(96,165,250,.22);background:rgba(11,43,79,.66);color:#dbeafe;font-size:.82rem;font-weight:800;}
.titan-stab-list {display:flex;gap:8px;flex-wrap:wrap;}
.titan-stab {padding:8px 10px;border-radius:12px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.18);color:#d9ffe8;font-size:.84rem;font-weight:700;}
@media (max-width: 900px) {
    .titan-muscle-diagrams,.titan-mini-grid,.titan-highlight-grid {grid-template-columns:1fr;}
}
</style>
"""


_FRONT_REGIONS = {
    "chest": '<ellipse cx="100" cy="84" rx="20" ry="18" fill="{color}" opacity="0.95"/><ellipse cx="140" cy="84" rx="20" ry="18" fill="{color}" opacity="0.95"/>',
    "front_shoulders": '<ellipse cx="73" cy="85" rx="12" ry="14" fill="{color}" opacity="0.9"/><ellipse cx="167" cy="85" rx="12" ry="14" fill="{color}" opacity="0.9"/>',
    "biceps": '<ellipse cx="68" cy="120" rx="10" ry="18" fill="{color}" opacity="0.9"/><ellipse cx="172" cy="120" rx="10" ry="18" fill="{color}" opacity="0.9"/>',
    "forearms": '<ellipse cx="60" cy="156" rx="8" ry="18" fill="{color}" opacity="0.85"/><ellipse cx="180" cy="156" rx="8" ry="18" fill="{color}" opacity="0.85"/>',
    "abs": '<rect x="104" y="108" width="32" height="52" rx="10" fill="{color}" opacity="0.9"/>',
    "obliques": '<ellipse cx="92" cy="128" rx="10" ry="24" fill="{color}" opacity="0.82"/><ellipse cx="148" cy="128" rx="10" ry="24" fill="{color}" opacity="0.82"/>',
    "quadriceps": '<ellipse cx="104" cy="212" rx="14" ry="32" fill="{color}" opacity="0.88"/><ellipse cx="136" cy="212" rx="14" ry="32" fill="{color}" opacity="0.88"/>',
    "adductors": '<ellipse cx="116" cy="212" rx="9" ry="28" fill="{color}" opacity="0.82"/><ellipse cx="124" cy="212" rx="9" ry="28" fill="{color}" opacity="0.82"/>',
    "calves": '<ellipse cx="103" cy="284" rx="10" ry="24" fill="{color}" opacity="0.84"/><ellipse cx="137" cy="284" rx="10" ry="24" fill="{color}" opacity="0.84"/>',
}

_BACK_REGIONS = {
    "rear_shoulders": '<ellipse cx="73" cy="84" rx="12" ry="14" fill="{color}" opacity="0.9"/><ellipse cx="167" cy="84" rx="12" ry="14" fill="{color}" opacity="0.9"/>',
    "traps": '<path d="M98 62 L120 78 L142 62 L152 86 L88 86 Z" fill="{color}" opacity="0.9"/>',
    "lats": '<path d="M86 92 Q62 124 74 164 L101 158 L109 100 Z" fill="{color}" opacity="0.86"/><path d="M154 92 Q178 124 166 164 L139 158 L131 100 Z" fill="{color}" opacity="0.86"/>',
    "triceps": '<ellipse cx="68" cy="122" rx="10" ry="18" fill="{color}" opacity="0.88"/><ellipse cx="172" cy="122" rx="10" ry="18" fill="{color}" opacity="0.88"/>',
    "spinal_erectors": '<rect x="112" y="98" width="16" height="68" rx="8" fill="{color}" opacity="0.82"/>',
    "glutes": '<ellipse cx="102" cy="176" rx="16" ry="18" fill="{color}" opacity="0.9"/><ellipse cx="138" cy="176" rx="16" ry="18" fill="{color}" opacity="0.9"/>',
    "hamstrings": '<ellipse cx="104" cy="220" rx="13" ry="32" fill="{color}" opacity="0.84"/><ellipse cx="136" cy="220" rx="13" ry="32" fill="{color}" opacity="0.84"/>',
    "calves": '<ellipse cx="103" cy="284" rx="10" ry="24" fill="{color}" opacity="0.84"/><ellipse cx="137" cy="284" rx="10" ry="24" fill="{color}" opacity="0.84"/>',
}

_BASE_BODY = """
<svg viewBox=\"0 0 240 340\" width=\"100%\" height=\"100%\" xmlns=\"http://www.w3.org/2000/svg\">
  <circle cx=\"120\" cy=\"34\" r=\"20\" fill=\"#ced8e6\" opacity=\"0.9\"/>
  <path d=\"M92 60 Q120 50 148 60 L166 98 Q156 140 150 164 L144 190 L136 304 L122 304 L120 208 L118 304 L104 304 L96 190 L90 164 Q84 140 74 98 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M74 98 Q58 120 54 158 L70 160 Q74 128 88 104 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M166 98 Q182 120 186 158 L170 160 Q166 128 152 104 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M54 158 Q50 184 52 214 L68 214 Q70 184 70 160 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M186 158 Q190 184 188 214 L172 214 Q170 184 170 160 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M96 190 L86 264 Q84 286 96 304 L106 304 L112 220 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  <path d=\"M144 190 L154 264 Q156 286 144 304 L134 304 L128 220 Z\" fill=\"#c3cedd\" opacity=\"0.92\"/>
  {overlays}
</svg>
"""


_COLOR_MAP = {
    "primary": "#ef4444",
    "secondary": "#f59e0b",
    "stabilizer": "#facc15",
}


def _region_for_muscle(name: str) -> List[str]:
    n = str(name or "").lower()
    mapping = {
        "pectoral": ["chest"],
        "chest": ["chest"],
        "anterior deltoid": ["front_shoulders"],
        "deltoid": ["front_shoulders", "rear_shoulders"],
        "shoulder": ["front_shoulders", "rear_shoulders"],
        "biceps": ["biceps"],
        "triceps": ["triceps", "biceps"],
        "forearm": ["forearms"],
        "brachioradialis": ["forearms"],
        "lat": ["lats"],
        "rhomboid": ["traps"],
        "trapezius": ["traps"],
        "trap": ["traps"],
        "erector": ["spinal_erectors"],
        "core": ["abs", "obliques"],
        "ab": ["abs"],
        "oblique": ["obliques"],
        "glute": ["glutes"],
        "hamstring": ["hamstrings"],
        "quad": ["quadriceps"],
        "adductor": ["adductors"],
        "abductor": ["glutes"],
        "calf": ["calves"],
        "soleus": ["calves"],
        "gastrocnemius": ["calves"],
    }
    regions: List[str] = []
    for key, value in mapping.items():
        if key in n:
            regions.extend(value)
    return list(dict.fromkeys(regions))


def _collect_regions(exercise_data: Dict) -> Dict[str, str]:
    region_colors: Dict[str, str] = {}
    priority = [
        (exercise_data.get("stabilizers", []), _COLOR_MAP["stabilizer"]),
        (exercise_data.get("secondary_muscles", []), _COLOR_MAP["secondary"]),
        (exercise_data.get("primary_muscles", []), _COLOR_MAP["primary"]),
    ]
    for muscles, color in priority:
        for muscle in muscles:
            for region in _region_for_muscle(str(muscle)):
                region_colors[region] = color
    return region_colors


def _build_svg(side: str, region_colors: Dict[str, str]) -> str:
    overlays = []
    source = _FRONT_REGIONS if side == "front" else _BACK_REGIONS
    for region, markup in source.items():
        color = region_colors.get(region)
        if color:
            overlays.append(markup.format(color=color))
    return _BASE_BODY.format(overlays="".join(overlays))


def _render_muscle_percentage_list(muscle_percentages: List[Dict]) -> str:
    rows = []
    for item in muscle_percentages:
        muscle = html.escape(str(item.get("muscle", "Unknown")))
        percentage = int(float(item.get("percentage", 0)))
        rows.append(
            '<div class="titan-muscle-row">'
            '<div>'
            f'<div class="titan-muscle-name">{muscle}</div>'
            f'<div class="titan-muscle-bar"><div class="titan-muscle-fill" style="width:{percentage}%;"></div></div>'
            '</div>'
            f'<div class="titan-muscle-pct">{percentage}%</div>'
            '</div>'
        )
    return "".join(rows)


def render_muscle_focus_panel(exercise_data: Dict) -> None:
    st.markdown(_PANEL_CSS, unsafe_allow_html=True)

    region_colors = _collect_regions(exercise_data)
    front_svg = _build_svg("front", region_colors)
    back_svg = _build_svg("back", region_colors)
    stabilizers = exercise_data.get("stabilizers", []) or ["Core"]
    tags = exercise_data.get("tags", []) or []
    muscle_percentages = exercise_data.get("muscle_percentages", []) or []
    primary = exercise_data.get("primary_muscles", []) or ["Unknown"]
    secondary = exercise_data.get("secondary_muscles", []) or ["N/A"]
    recovery_pct = int(exercise_data.get("muscle_recovery_pct", 100) or 100)
    weekly_volume = int(exercise_data.get("weekly_volume", 0) or 0)

    st.markdown(
        (
            '<div class="titan-muscle-panel">'
            '<div class="titan-muscle-card">'
            '<div class="titan-muscle-card-title">Muscle Focus</div>'
            '<div class="titan-highlight-grid">'
            f'<div class="titan-highlight"><div class="titan-highlight-label">Primary</div><div class="titan-highlight-value">{html.escape(str(primary[0]))}</div></div>'
            f'<div class="titan-highlight"><div class="titan-highlight-label">Secondary</div><div class="titan-highlight-value">{html.escape(str(secondary[0]))}</div></div>'
            f'<div class="titan-highlight"><div class="titan-highlight-label">Stabilizer</div><div class="titan-highlight-value">{html.escape(str(stabilizers[0]))}</div></div>'
            '</div>'
            '<div style="height:12px"></div>'
            '<div class="titan-muscle-diagrams">'
            f'<div><div class="titan-muscle-diagram">{front_svg}</div><div class="titan-muscle-figure-title">Front View</div></div>'
            f'<div><div class="titan-muscle-diagram">{back_svg}</div><div class="titan-muscle-figure-title">Back View</div></div>'
            '</div>'
            '<div class="titan-muscle-legend">'
            '<span><i class="titan-muscle-dot" style="background:#ef4444"></i>Primary</span>'
            '<span><i class="titan-muscle-dot" style="background:#f59e0b"></i>Secondary</span>'
            '<span><i class="titan-muscle-dot" style="background:#facc15"></i>Stabilizers</span>'
            '</div>'
            '</div>'
            '<div class="titan-muscle-card">'
            '<div class="titan-muscle-card-title">Muscles Worked</div>'
            f'<div class="titan-muscle-list">{_render_muscle_percentage_list(muscle_percentages)}</div>'
            '</div>'
            '<div class="titan-muscle-card">'
            '<div class="titan-mini-grid">'
            '<div class="titan-mini-card">'
            '<div class="titan-mini-label">Recovery</div>'
            f'<div class="titan-mini-value">{recovery_pct}%</div>'
            '</div>'
            '<div class="titan-mini-card">'
            '<div class="titan-mini-label">Weekly Volume</div>'
            f'<div class="titan-mini-value">{weekly_volume:,} lbs</div>'
            '</div>'
            '<div class="titan-mini-card">'
            '<div class="titan-mini-label">Equipment</div>'
            f'<div class="titan-mini-value">{html.escape(str(exercise_data.get("equipment", "Bodyweight")))}</div>'
            '</div>'
            '<div class="titan-mini-card">'
            '<div class="titan-mini-label">Level</div>'
            f'<div class="titan-mini-value">{html.escape(str(exercise_data.get("difficulty", "Intermediate")))}</div>'
            '</div>'
            '</div>'
            '</div>'
            '<div class="titan-muscle-card">'
            '<div class="titan-muscle-card-title">Stabilizers</div>'
            '<div class="titan-stab-list">'
            f'{"".join(f"<span class=\"titan-stab\">{html.escape(str(item))}</span>" for item in stabilizers)}'
            '</div>'
            '</div>'
            '<div class="titan-muscle-card">'
            '<div class="titan-muscle-card-title">Exercise Tags</div>'
            '<div class="titan-pill-wrap">'
            f'{"".join(f"<span class=\"titan-pill\">{html.escape(str(tag))}</span>" for tag in tags)}'
            '</div>'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )
