from __future__ import annotations

import html
from typing import Dict

import streamlit as st


_PROGRESS_CSS = """
<style>
.titan-progression-panel {display:grid;gap:14px;}
.titan-progress-card {border:1px solid rgba(96,165,250,.18);border-radius:22px;padding:16px;background:linear-gradient(180deg,rgba(10,20,34,.98),rgba(7,17,31,.98));box-shadow:0 16px 40px rgba(0,0,0,.22);position:relative;overflow:hidden;}
.titan-progress-card:before {content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,rgba(96,165,250,.42),rgba(245,158,11,.35));}
.titan-progress-title {font-size:.8rem;letter-spacing:.18em;text-transform:uppercase;color:#93c5fd;font-weight:900;margin-bottom:12px;}
.titan-progress-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;}
.titan-progress-metric {border:1px solid rgba(148,163,184,.14);border-radius:16px;padding:14px;background:rgba(15,31,52,.72);}
.titan-progress-label {font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#8fb5df;font-weight:900;}
.titan-progress-value {margin-top:8px;color:#fff;font-size:1rem;line-height:1.4;font-weight:900;}
.titan-confidence {display:flex;align-items:center;justify-content:space-between;gap:12px;}
.titan-confidence-score {font-size:2rem;color:#fff;font-weight:950;line-height:1;}
.titan-confidence-bar {height:10px;border-radius:999px;background:#102033;border:1px solid rgba(148,163,184,.12);overflow:hidden;margin-top:10px;}
.titan-confidence-fill {height:100%;border-radius:999px;background:linear-gradient(90deg,#22c55e,#60a5fa);}
.titan-inline-list {display:grid;gap:8px;margin:0;padding-left:18px;color:#dce5f3;font-size:.94rem;line-height:1.6;}
.titan-inline-list li {margin-bottom:4px;}
.titan-similar-wrap {display:flex;gap:8px;flex-wrap:wrap;}
.titan-similar-pill {padding:8px 10px;border-radius:12px;border:1px solid rgba(148,163,184,.16);background:rgba(11,30,50,.66);color:#d6e3f7;font-size:.84rem;font-weight:800;}
@media (max-width: 900px) {
  .titan-progress-grid {grid-template-columns:1fr;}
}
</style>
"""


def render_exercise_progression_panel(exercise_data: Dict) -> None:
    st.markdown(_PROGRESS_CSS, unsafe_allow_html=True)

    coaching_notes = exercise_data.get("ai_coaching_recommendations", []) or ["More workout history is needed for stronger coaching suggestions."]
    similar = exercise_data.get("similar_exercises", []) or ["No similar exercises suggested yet."]
    confidence = int(exercise_data.get("ai_confidence_score", 0) or 0)

    st.markdown(
        (
            '<div class="titan-progression-panel">'
            '<div class="titan-progress-card">'
            '<div class="titan-progress-title">Progression Panel</div>'
            '<div class="titan-progress-grid">'
            f'<div class="titan-progress-metric"><div class="titan-progress-label">Personal Record</div><div class="titan-progress-value">{html.escape(str(exercise_data.get("personal_record", "No personal records logged yet.")))}</div></div>'
            f'<div class="titan-progress-metric"><div class="titan-progress-label">Estimated 1RM</div><div class="titan-progress-value">{html.escape(str(exercise_data.get("estimated_one_rep_max", "N/A")))}</div></div>'
            f'<div class="titan-progress-metric"><div class="titan-progress-label">Last Workout</div><div class="titan-progress-value">{html.escape(str(exercise_data.get("last_workout", "No workout history yet.")))}</div></div>'
            f'<div class="titan-progress-metric"><div class="titan-progress-label">Recommended Weight</div><div class="titan-progress-value">{html.escape(str(exercise_data.get("recommended_weight", "Build a baseline first.")))}</div></div>'
            '</div>'
            '</div>'
            '<div class="titan-progress-card">'
            '<div class="titan-progress-title">AI Confidence</div>'
            '<div class="titan-confidence">'
            '<div>'
            '<div class="titan-progress-label">Recommendation Confidence</div>'
            f'<div class="titan-confidence-score">{confidence}%</div>'
            '</div>'
            '<div style="flex:1;">'
            f'<div class="titan-confidence-bar"><div class="titan-confidence-fill" style="width:{confidence}%;"></div></div>'
            '</div>'
            '</div>'
            '</div>'
            '<div class="titan-progress-card">'
            '<div class="titan-progress-title">AI Coaching Recommendations</div>'
            f'<ul class="titan-inline-list">{"".join(f"<li>{html.escape(str(item))}</li>" for item in coaching_notes)}</ul>'
            '</div>'
            '<div class="titan-progress-card">'
            '<div class="titan-progress-title">Similar Exercises</div>'
            '<div class="titan-similar-wrap">'
            f'{"".join(f"<span class=\"titan-similar-pill\">{html.escape(str(item))}</span>" for item in similar)}'
            '</div>'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )
