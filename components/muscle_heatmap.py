from __future__ import annotations

import html
from typing import Dict, List

import streamlit as st


_HEATMAP_CSS = """
<style>
:root {
    --titan-type-display: "Space Grotesk", "Sora", "Avenir Next", "Segoe UI", sans-serif;
    --titan-type-body: "Manrope", "Avenir Next", "Segoe UI", sans-serif;
}
.titan-heat-shell {display:grid;gap:16px;margin-top:12px;}
.titan-heat-card {border:1px solid rgba(125,211,252,.22);border-radius:24px;padding:18px;background:radial-gradient(circle at 8% -25%,rgba(56,189,248,.18),transparent 48%),linear-gradient(168deg,rgba(10,20,34,.98),rgba(6,14,26,.99));box-shadow:0 20px 54px rgba(2,6,23,.45);position:relative;overflow:hidden;animation:titanFadeUp .42s ease-out both;}
.titan-heat-card:before {content:"";position:absolute;inset:0 auto auto 0;width:100%;height:2px;background:linear-gradient(90deg,rgba(34,197,94,.55),rgba(125,211,252,.62),rgba(249,115,22,.45));}
.titan-heat-card:after {content:"";position:absolute;top:0;left:-120%;width:50%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.04),transparent);transform:skewX(-20deg);animation:titanShine 6.5s ease-in-out infinite;pointer-events:none;}
.titan-heat-head {display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:14px;}
.titan-heat-title {font-family:var(--titan-type-display);font-size:.76rem;letter-spacing:.22em;text-transform:uppercase;color:#bae6fd;font-weight:900;}
.titan-heat-sub {font-family:var(--titan-type-body);margin-top:8px;color:#cbd5e1;font-size:.94rem;max-width:740px;line-height:1.58;}
.titan-heat-legend {display:flex;flex-wrap:wrap;gap:8px;}
.titan-heat-pill {font-family:var(--titan-type-body);padding:6px 10px;border-radius:999px;font-size:.75rem;font-weight:850;border:1px solid rgba(148,163,184,.24);background:rgba(10,20,35,.72);color:#e2e8f0;}
.titan-heat-map-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start;}
.titan-heat-map {border:1px solid rgba(148,163,184,.16);border-radius:18px;padding:12px;background:radial-gradient(circle at 50% 0%,rgba(56,189,248,.18),rgba(7,17,31,.98) 62%);box-shadow:inset 0 0 0 1px rgba(255,255,255,.03),0 10px 24px rgba(2,6,23,.24);transition:transform .24s ease, border-color .24s ease;}
.titan-heat-map:hover {transform:translateY(-2px);border-color:rgba(125,211,252,.3);}
.titan-heat-label {font-family:var(--titan-type-display);text-align:center;color:#a9bad1;font-size:.73rem;letter-spacing:.23em;text-transform:uppercase;font-weight:900;margin-top:8px;}
.titan-card-title {font-family:var(--titan-type-display);font-size:.74rem;letter-spacing:.22em;text-transform:uppercase;color:#93c5fd;font-weight:900;margin:14px 0 10px;}
.titan-muscle-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
.titan-muscle-card {border:1px solid rgba(148,163,184,.16);border-radius:16px;padding:12px;background:linear-gradient(180deg,rgba(15,31,52,.94),rgba(7,17,31,.96));box-shadow:0 10px 26px rgba(2,6,23,.24);transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease;animation:titanFadeUp .36s ease-out both;}
.titan-muscle-card:hover {transform:translateY(-2px);box-shadow:0 16px 32px rgba(2,6,23,.33);border-color:rgba(148,163,184,.3);}
.titan-muscle-head {display:flex;justify-content:space-between;gap:10px;align-items:center;}
.titan-muscle-name {font-family:var(--titan-type-display);font-size:.96rem;color:#f8fafc;font-weight:900;letter-spacing:.01em;}
.titan-muscle-badge {font-family:var(--titan-type-body);padding:4px 8px;border-radius:999px;border:1px solid rgba(148,163,184,.24);font-size:.73rem;font-weight:850;}
.titan-muscle-metrics {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px;}
.titan-muscle-item {border:1px solid rgba(148,163,184,.13);border-radius:10px;padding:8px;background:rgba(11,24,40,.62);}
.titan-muscle-label {font-family:var(--titan-type-display);font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:#94a3b8;font-weight:900;}
.titan-muscle-value {font-family:var(--titan-type-body);margin-top:4px;color:#f1f5f9;font-size:.83rem;font-weight:850;line-height:1.35;}
.titan-muscle-ai {font-family:var(--titan-type-body);margin-top:8px;padding:8px;border:1px solid rgba(148,163,184,.14);border-radius:10px;background:rgba(2,6,23,.38);color:#dbeafe;font-size:.82rem;line-height:1.45;}
.titan-muscle-select {margin-top:8px;}
.titan-muscle-select button {width:100%;}
.titan-detail-row {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
.titan-detail-item {border:1px solid rgba(148,163,184,.16);border-radius:12px;padding:10px;background:rgba(11,24,40,.62);}
.titan-detail-label {font-family:var(--titan-type-display);font-size:.66rem;letter-spacing:.17em;text-transform:uppercase;color:#93c5fd;font-weight:900;}
.titan-detail-value {font-family:var(--titan-type-body);margin-top:6px;color:#fff;font-size:.92rem;font-weight:800;line-height:1.46;}
.titan-heat-fallback {font-family:var(--titan-type-body);border:1px dashed rgba(148,163,184,.28);border-radius:16px;padding:16px;background:rgba(6,14,26,.6);color:#cbd5e1;line-height:1.55;}
@keyframes titanFadeUp {
    from {opacity:0; transform:translateY(8px);}
    to {opacity:1; transform:translateY(0);}
}
@keyframes titanShine {
    0%, 75% {left:-120%;}
    100% {left:130%;}
}
@media (max-width: 900px) {
    .titan-heat-map-grid,.titan-muscle-grid,.titan-detail-row,.titan-muscle-metrics {grid-template-columns:1fr;}
    .titan-heat-card {padding:14px;}
}
</style>
"""


_REQUIRED_CARD_ORDER = [
        "chest",
        "back",
        "shoulders",
        "biceps",
        "triceps",
        "core",
        "glutes",
        "quads",
        "hamstrings",
        "calves",
]


_FRONT_REGIONS = {
        "chest": '<path d="M87 98 Q100 78 118 86 Q105 106 88 112 Z" fill="{color}" opacity=".86"/><path d="M153 98 Q140 78 122 86 Q135 106 152 112 Z" fill="{color}" opacity=".86"/>',
        "shoulders": '<ellipse cx="76" cy="92" rx="13" ry="16" fill="{color}" opacity=".84"/><ellipse cx="164" cy="92" rx="13" ry="16" fill="{color}" opacity=".84"/>',
        "biceps": '<ellipse cx="71" cy="128" rx="11" ry="19" fill="{color}" opacity=".82"/><ellipse cx="169" cy="128" rx="11" ry="19" fill="{color}" opacity=".82"/>',
        "core": '<rect x="105" y="116" width="30" height="52" rx="10" fill="{color}" opacity=".84"/>',
        "quads": '<path d="M97 186 Q107 184 111 196 L107 247 Q96 253 88 245 L91 198 Z" fill="{color}" opacity=".82"/><path d="M143 186 Q133 184 129 196 L133 247 Q144 253 152 245 L149 198 Z" fill="{color}" opacity=".82"/>',
        "calves": '<path d="M92 250 Q102 246 108 252 L106 292 Q96 300 88 292 Z" fill="{color}" opacity=".78"/><path d="M148 250 Q138 246 132 252 L134 292 Q144 300 152 292 Z" fill="{color}" opacity=".78"/>',
}


_BACK_REGIONS = {
        "back": '<path d="M88 99 Q96 81 119 90 L109 164 Q85 156 80 126 Z" fill="{color}" opacity=".84"/><path d="M152 99 Q144 81 121 90 L131 164 Q155 156 160 126 Z" fill="{color}" opacity=".84"/>',
        "shoulders": '<ellipse cx="76" cy="92" rx="13" ry="16" fill="{color}" opacity=".82"/><ellipse cx="164" cy="92" rx="13" ry="16" fill="{color}" opacity=".82"/>',
        "triceps": '<ellipse cx="71" cy="132" rx="10" ry="18" fill="{color}" opacity=".8"/><ellipse cx="169" cy="132" rx="10" ry="18" fill="{color}" opacity=".8"/>',
        "glutes": '<path d="M96 168 Q106 162 117 169 Q113 188 98 194 Q90 184 96 168 Z" fill="{color}" opacity=".83"/><path d="M144 168 Q134 162 123 169 Q127 188 142 194 Q150 184 144 168 Z" fill="{color}" opacity=".83"/>',
        "hamstrings": '<path d="M96 196 Q108 192 112 203 L109 249 Q96 257 88 246 L90 206 Z" fill="{color}" opacity=".8"/><path d="M144 196 Q132 192 128 203 L131 249 Q144 257 152 246 L150 206 Z" fill="{color}" opacity=".8"/>',
        "calves": '<path d="M92 252 Q102 248 108 254 L106 292 Q96 300 88 292 Z" fill="{color}" opacity=".76"/><path d="M148 252 Q138 248 132 254 L134 292 Q144 300 152 292 Z" fill="{color}" opacity=".76"/>',
}


_BASE_BODY = """
<svg viewBox=\"0 0 240 340\" width=\"100%\" height=\"100%\" xmlns=\"http://www.w3.org/2000/svg\">
    <defs>
        <linearGradient id=\"skinGradient\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">
            <stop offset=\"0%\" stop-color=\"#d9e3f2\" stop-opacity=\".94\"/>
            <stop offset=\"100%\" stop-color=\"#b9c6d9\" stop-opacity=\".9\"/>
        </linearGradient>
        <filter id=\"glow\" x=\"-40%\" y=\"-40%\" width=\"180%\" height=\"180%\">
            <feGaussianBlur stdDeviation=\"2.2\" result=\"blur\"/>
            <feMerge>
                <feMergeNode in=\"blur\"/>
                <feMergeNode in=\"SourceGraphic\"/>
            </feMerge>
        </filter>
    </defs>
    <circle cx=\"120\" cy=\"35\" r=\"18\" fill=\"url(#skinGradient)\"/>
    <path d=\"M96 58 Q120 49 144 58 L161 92 Q154 136 148 163 L144 188 L136 304 L123 304 L120 205 L117 304 L104 304 L96 188 L92 163 Q86 136 79 92 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M79 92 Q63 120 61 158 L75 160 Q80 128 93 102 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M161 92 Q177 120 179 158 L165 160 Q160 128 147 102 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M61 158 Q58 184 60 214 L74 214 Q76 185 75 160 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M179 158 Q182 184 180 214 L166 214 Q164 185 165 160 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M96 188 L88 264 Q86 286 96 304 L106 304 L112 218 Z\" fill=\"url(#skinGradient)\"/>
    <path d=\"M144 188 L152 264 Q154 286 144 304 L134 304 L128 218 Z\" fill=\"url(#skinGradient)\"/>
    <g filter=\"url(#glow)\">{overlays}</g>
</svg>
"""


def _status_meta(status: str) -> Dict[str, str]:
        normalized = str(status or "").strip().lower()
        if normalized == "green":
                return {"label": "Ready", "color": "#22c55e", "chip": "#bbf7d0"}
        if normalized == "yellow":
                return {"label": "Moderate", "color": "#facc15", "chip": "#fde68a"}
        if normalized == "orange":
                return {"label": "Recovering", "color": "#f97316", "chip": "#fdba74"}
        if normalized == "red":
                return {"label": "Fatigued", "color": "#ef4444", "chip": "#fecaca"}
        return {"label": "Moderate", "color": "#facc15", "chip": "#fde68a"}


def _default_row(muscle: str) -> Dict:
        meta = _status_meta("yellow")
        return {
                "muscle": muscle,
                "readiness_percent": 0,
                "status": "Yellow",
                "status_label": meta["label"],
                "status_color": meta["color"],
                "last_trained": "No recent log",
                "weekly_volume": 0,
                "recommended_action": "Collect more workout data to personalize guidance.",
                "recommended_exercises": [],
                "ai_recommendation": "No AI recommendation available yet.",
        }


def _normalize_rows(snapshot: Dict) -> Dict[str, Dict]:
        rows_df = (snapshot or {}).get("rows")
        rows = rows_df.to_dict("records") if rows_df is not None and not rows_df.empty else []
        normalized: Dict[str, Dict] = {}
        for row in rows:
                muscle = str(row.get("muscle", "")).strip().lower()
                if not muscle:
                        continue
                item = dict(row)
                meta = _status_meta(str(item.get("status", "Yellow")))
                item["status_label"] = str(item.get("status_label") or meta["label"])
                item["status_color"] = str(item.get("status_color") or meta["color"])
                normalized[muscle] = item

        for muscle in _REQUIRED_CARD_ORDER:
                if muscle not in normalized:
                        normalized[muscle] = _default_row(muscle)

        return normalized


def _build_svg(side: str, readiness_map: Dict[str, Dict]) -> str:
    source = _FRONT_REGIONS if side == "front" else _BACK_REGIONS
    overlays: List[str] = []
    for muscle, markup in source.items():
        item = readiness_map.get(muscle)
        if not item:
            continue
        color = str(item.get("status_color", "#facc15"))
        overlays.append(markup.format(color=color))
    return _BASE_BODY.format(overlays="".join(overlays))


def _render_detail(selected: Dict) -> str:
    if not selected:
        return (
            '<div class="titan-detail-item"><div class="titan-detail-label">Muscle Detail</div>'
            '<div class="titan-detail-value">Choose a muscle to inspect recovery %, volume, and recommendations.</div></div>'
        )

    exercises = selected.get("recommended_exercises", []) or []
    ex_text = ", ".join(html.escape(str(x)) for x in exercises[:5]) if exercises else "No specific exercise suggestions available yet."

    return (
        '<div class="titan-detail-row">'
        f'<div class="titan-detail-item"><div class="titan-detail-label">Recovery</div><div class="titan-detail-value">{int(selected.get("readiness_percent", 0))}% • {html.escape(str(selected.get("status_label", "Moderate")))}</div></div>'
        f'<div class="titan-detail-item"><div class="titan-detail-label">Weekly Volume</div><div class="titan-detail-value">{int(selected.get("weekly_volume", 0)):,} lbs</div></div>'
        f'<div class="titan-detail-item"><div class="titan-detail-label">Last Trained</div><div class="titan-detail-value">{html.escape(str(selected.get("last_trained") or "No recent log"))}</div></div>'
        f'<div class="titan-detail-item"><div class="titan-detail-label">Recommended Action</div><div class="titan-detail-value">{html.escape(str(selected.get("recommended_action", "No action recommendation.")))}</div></div>'
        f'<div class="titan-detail-item"><div class="titan-detail-label">Recommended Exercises</div><div class="titan-detail-value">{ex_text}</div></div>'
        f'<div class="titan-detail-item"><div class="titan-detail-label">AI Recommendation</div><div class="titan-detail-value">{html.escape(str(selected.get("ai_recommendation", "No AI recommendation available.")))}</div></div>'
        '</div>'
    )



def _card_markup(item: Dict, selected: bool) -> str:
    status = str(item.get("status", "Yellow"))
    meta = _status_meta(status)
    pct = int(item.get("readiness_percent", 0) or 0)
    weekly_volume = int(item.get("weekly_volume", 0) or 0)
    border = f"border-color:{meta['color']}66;"
    active = "box-shadow:0 0 0 1px rgba(255,255,255,.06),0 0 22px rgba(56,189,248,.22);" if selected else ""

    return (
        f'<div class="titan-muscle-card" style="{border}{active}">'
        '<div class="titan-muscle-head">'
        f'<div class="titan-muscle-name">{html.escape(str(item.get("muscle", "muscle")).title())}</div>'
        f'<div class="titan-muscle-badge" style="border-color:{meta["color"]};color:{meta["chip"]};">{html.escape(str(item.get("status_label", meta["label"])))}</div>'
        '</div>'
        '<div class="titan-muscle-metrics">'
        f'<div class="titan-muscle-item"><div class="titan-muscle-label">Readiness</div><div class="titan-muscle-value">{pct}%</div></div>'
        f'<div class="titan-muscle-item"><div class="titan-muscle-label">Weekly Volume</div><div class="titan-muscle-value">{weekly_volume:,} lbs</div></div>'
        f'<div class="titan-muscle-item"><div class="titan-muscle-label">Last Trained</div><div class="titan-muscle-value">{html.escape(str(item.get("last_trained") or "No recent log"))}</div></div>'
        f'<div class="titan-muscle-item"><div class="titan-muscle-label">Action</div><div class="titan-muscle-value">{html.escape(str(item.get("recommended_action", "Train with controlled effort.")))}</div></div>'
        '</div>'
        f'<div class="titan-muscle-ai"><strong>AI:</strong> {html.escape(str(item.get("ai_recommendation", "No AI recommendation available.")))}</div>'
        '</div>'
    )

def render_muscle_heatmap(snapshot: Dict, key_prefix: str = "heatmap") -> None:
    st.markdown(_HEATMAP_CSS, unsafe_allow_html=True)
    ready_map = _normalize_rows(snapshot)
    rows_exist = bool((snapshot or {}).get("rows") is not None and not (snapshot or {}).get("rows").empty)

    st.markdown('<div class="titan-heat-shell">', unsafe_allow_html=True)
    st.markdown('<div class="titan-heat-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="titan-heat-head">'
        '<div><div class="titan-heat-title">Muscle Intelligence Map</div><div class="titan-heat-sub">Professional recovery visualization based on your recent training load, readiness scoring, and adaptive coaching intelligence.</div></div>'
        '<div class="titan-heat-legend">'
        '<span class="titan-heat-pill" style="border-color:#22c55e;color:#bbf7d0;">Green • Ready</span>'
        '<span class="titan-heat-pill" style="border-color:#facc15;color:#fde68a;">Yellow • Moderate</span>'
        '<span class="titan-heat-pill" style="border-color:#f97316;color:#fdba74;">Orange • Recovering</span>'
        '<span class="titan-heat-pill" style="border-color:#ef4444;color:#fecaca;">Red • Fatigued</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if not rows_exist:
        st.markdown(
            '<div class="titan-heat-fallback">No muscle readiness logs yet. We are displaying a premium preview layout. Log workouts and recovery entries to unlock live muscle scoring and coaching recommendations.</div>',
            unsafe_allow_html=True,
        )

    front_svg = _build_svg("front", ready_map)
    back_svg = _build_svg("back", ready_map)
    st.markdown(
        '<div class="titan-heat-map-grid">'
        f'<div class="titan-heat-map">{front_svg}<div class="titan-heat-label">Front Body</div></div>'
        f'<div class="titan-heat-map">{back_svg}<div class="titan-heat-label">Back Body</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    selected_key = f"{key_prefix}_selected_muscle"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = _REQUIRED_CARD_ORDER[0]

    st.markdown('<div class="titan-card-title">Muscle Readiness Cards</div>', unsafe_allow_html=True)
    grid_cols = st.columns(2)
    for idx, muscle in enumerate(_REQUIRED_CARD_ORDER):
        item = ready_map.get(muscle, _default_row(muscle))
        with grid_cols[idx % 2]:
            st.markdown(_card_markup(item, str(st.session_state.get(selected_key, "")).lower() == muscle), unsafe_allow_html=True)
            if st.button(f"Inspect {muscle.title()}", key=f"{key_prefix}_{muscle}_inspect", use_container_width=True):
                st.session_state[selected_key] = muscle

    selected = ready_map.get(str(st.session_state.get(selected_key, "")).lower(), {})
    st.markdown(_render_detail(selected), unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)
