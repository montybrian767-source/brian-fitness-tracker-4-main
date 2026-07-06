from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.exercise_detail_panel import render_exercise_detail_panel
from engines.exercise_intelligence import ExerciseIntelligence
from engines.muscle_readiness_engine import build_muscle_readiness_snapshot


_PAGE_CSS = """
<style>
.titan-library-hero {border:1px solid rgba(96,165,250,.26);border-radius:30px;padding:26px 28px;background:radial-gradient(circle at 12% -20%,rgba(37,99,235,.24),transparent 48%),linear-gradient(150deg,#0f2238,#081321 58%,#0d2a48);box-shadow:0 26px 58px rgba(0,0,0,.3);margin:10px 0 20px 0;}
.titan-library-kicker {letter-spacing:.22em;font-size:.78rem;color:#22c55e;font-weight:950;text-transform:uppercase;}
.titan-library-title {font-size:2.45rem;font-weight:950;color:#fff;line-height:1.02;margin-top:8px;}
.titan-library-sub {color:#a9bad1;font-size:1rem;margin-top:10px;max-width:820px;line-height:1.55;}
.titan-library-toolbar {border:1px solid rgba(96,165,250,.2);border-radius:24px;padding:14px 14px 6px 14px;background:linear-gradient(180deg,rgba(15,31,52,.95),rgba(7,17,31,.98));margin-bottom:16px;box-shadow:0 12px 34px rgba(0,0,0,.2);}
.titan-library-results {border:1px solid rgba(96,165,250,.16);border-radius:24px;padding:18px;background:linear-gradient(180deg,rgba(10,20,34,.98),rgba(7,17,31,.99));margin-bottom:20px;box-shadow:0 14px 38px rgba(0,0,0,.2);}
.titan-results-title {font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;font-weight:900;color:#93c5fd;margin-bottom:12px;}
.titan-results-meta {color:#c6d4e6;font-size:.92rem;margin-bottom:14px;line-height:1.5;}
.titan-result-chip {display:inline-flex;align-items:center;gap:10px;padding:8px 12px;border-radius:12px;border:1px solid rgba(96,165,250,.18);background:rgba(11,30,50,.68);color:#d6e3f7;font-size:.82rem;font-weight:800;}
.titan-result-count {width:24px;height:24px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;background:rgba(37,99,235,.3);border:1px solid rgba(96,165,250,.3);color:#fff;font-size:.76rem;font-weight:900;}
@media (max-width: 900px) {
    .titan-library-title {font-size:1.9rem;}
}
</style>
"""


_APP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _APP_DIR / "data"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _filtered_library(library_df: pd.DataFrame, search: str, muscle_filter: str, equipment_filter: str, difficulty_filter: str) -> pd.DataFrame:
    filtered = library_df.copy()
    if search:
        filtered = filtered[
            filtered["exercise"].astype(str).str.contains(search, case=False, na=False)
        ]
    if muscle_filter != "All":
        filtered = filtered[filtered["muscle_group"].astype(str) == muscle_filter]
    if equipment_filter != "All":
        filtered = filtered[filtered["equipment"].astype(str) == equipment_filter]
    if difficulty_filter != "All":
        filtered = filtered[filtered["difficulty"].astype(str) == difficulty_filter]
    return filtered.reset_index(drop=True)


def render_exercise_library_page(assets_dir: Path):
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    intel = ExerciseIntelligence()
    library_df = intel.get_library_dataframe()
    if library_df.empty:
        st.warning("Exercise library data is unavailable.")
        return

    st.markdown(
        '<div class="titan-library-hero"><div class="titan-library-kicker">Project Titan</div><div class="titan-library-title">Exercise Library</div><div class="titan-library-sub">Detailed exercise guidance with premium intelligence cards, multi-angle imagery, and muscle emphasis designed to match the new Project Titan visual target.</div></div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="titan-library-toolbar">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.6, 1, 1, 1])
        with c1:
            search = st.text_input("Search exercises", placeholder="Dumbbell bench press, pulldown, face pull...", key="exercise_library_search")
        with c2:
            muscle_filter = st.selectbox("Muscle Group", ["All"] + sorted(library_df["muscle_group"].dropna().astype(str).unique().tolist()), key="exercise_library_muscle")
        with c3:
            equipment_filter = st.selectbox("Equipment", ["All"] + sorted(library_df["equipment"].dropna().astype(str).unique().tolist()), key="exercise_library_equipment")
        with c4:
            difficulty_filter = st.selectbox("Difficulty", ["All"] + sorted(library_df["difficulty"].dropna().astype(str).unique().tolist()), key="exercise_library_difficulty")
        st.markdown('</div>', unsafe_allow_html=True)

    filtered = _filtered_library(library_df, search, muscle_filter, equipment_filter, difficulty_filter)
    if filtered.empty:
        st.info("No exercises match the current search and filters.")
        return

    selected = st.session_state.get("exercise_library_selected")
    if selected not in filtered["exercise"].tolist():
        st.session_state.exercise_library_selected = str(filtered.iloc[0]["exercise"])

    st.markdown('<div class="titan-library-results">', unsafe_allow_html=True)
    st.markdown(f'<div class="titan-results-title">Library Results</div><div class="titan-results-meta">{len(filtered)} exercises loaded. Choose a movement to inspect the full intelligence layout.</div>', unsafe_allow_html=True)
    result_cols = st.columns(4)
    for idx, (_, row) in enumerate(filtered.iterrows()):
        with result_cols[idx % 4]:
            st.markdown(
                f'<div class="titan-result-chip"><span class="titan-result-count">{idx+1}</span><span>{row["movement_pattern"]}</span></div>',
                unsafe_allow_html=True,
            )
            label = f"{row['exercise']}\n{row['muscle_group']}"
            if st.button(label, key=f"exercise_pick_{idx}", use_container_width=True):
                st.session_state.exercise_library_selected = str(row["exercise"])
    st.markdown('</div>', unsafe_allow_html=True)

    profile = intel.get_profile(st.session_state.exercise_library_selected)
    muscle_snapshot = build_muscle_readiness_snapshot(
        workout_log_df=_safe_read_csv(_DATA_DIR / "workout_log.csv"),
        recovery_df=_safe_read_csv(_DATA_DIR / "recovery_log.csv"),
        body_df=_safe_read_csv(_DATA_DIR / "body_stats.csv"),
    )
    render_exercise_detail_panel(profile, assets_dir, muscle_snapshot)
