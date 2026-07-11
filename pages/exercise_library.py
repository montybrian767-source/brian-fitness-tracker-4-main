from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.exercise_detail_panel import render_exercise_detail_panel
from engines.exercise_intelligence import ExerciseIntelligence
from engines.muscle_readiness_engine import build_muscle_readiness_snapshot
from engines.progressive_overload_engine import analyze_progressive_overload
from engines.plateau_detection_engine import detect_plateaus


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


def _exercise_snapshot(log_df: pd.DataFrame, exercise_name: str, progression: dict, plateau: dict) -> dict:
    payload = {
        "last_performance": "No history",
        "personal_best": "No history",
        "estimated_1rm": "N/A",
        "weight_trend": "stable",
        "rep_trend": "stable",
        "volume_trend": "stable",
        "recent_sessions": pd.DataFrame(),
        "progression": "Hold Weight",
        "suggested_next_weight": "N/A",
        "suggested_rep_range": "8-12",
        "plateau_status": "No plateau signal",
    }

    if log_df is None or log_df.empty:
        return payload

    ex = log_df[log_df["exercise"].astype(str).str.lower() == str(exercise_name).lower()].copy()
    if ex.empty:
        return payload

    ex["date"] = pd.to_datetime(ex["date"], errors="coerce")
    ex = ex.dropna(subset=["date"]).sort_values("date")
    for col in ["weight_lbs", "reps", "volume"]:
        ex[col] = pd.to_numeric(ex.get(col, 0), errors="coerce").fillna(0)
    ex["estimated_1rm"] = ex["weight_lbs"] * (1 + (ex["reps"] / 30.0))

    last = ex.iloc[-1]
    best = ex.loc[ex["weight_lbs"].idxmax()] if not ex.empty else last

    payload["last_performance"] = f"{str(pd.Timestamp(last['date']).date())} • {float(last['weight_lbs']):.1f} lbs x {int(last['reps'])}"
    payload["personal_best"] = f"{float(best['weight_lbs']):.1f} lbs"
    payload["estimated_1rm"] = f"{float(ex['estimated_1rm'].max()):.1f} lbs"
    payload["recent_sessions"] = ex.tail(8)[["date", "weight_lbs", "reps", "volume", "estimated_1rm"]].copy()
    payload["recent_sessions"]["date"] = payload["recent_sessions"]["date"].dt.date.astype(str)

    if len(ex) >= 4:
        w0 = float(ex.head(2)["weight_lbs"].mean())
        w1 = float(ex.tail(2)["weight_lbs"].mean())
        r0 = float(ex.head(2)["reps"].mean())
        r1 = float(ex.tail(2)["reps"].mean())
        v0 = float(ex.head(2)["volume"].mean())
        v1 = float(ex.tail(2)["volume"].mean())
        payload["weight_trend"] = "up" if w1 > (w0 * 1.02) else ("down" if w1 < (w0 * 0.98) else "stable")
        payload["rep_trend"] = "up" if r1 > (r0 * 1.05) else ("down" if r1 < (r0 * 0.95) else "stable")
        payload["volume_trend"] = "up" if v1 > (v0 * 1.05) else ("down" if v1 < (v0 * 0.95) else "stable")

    p_item = (progression or {}).get("by_exercise", {}).get(exercise_name)
    if p_item:
        payload["progression"] = str(p_item.get("suggested_action", "Hold Weight"))
        payload["suggested_next_weight"] = f"{float(p_item.get('suggested_weight', 0) or 0):.1f} lbs"
        payload["suggested_rep_range"] = str(p_item.get("suggested_rep_range", "8-12"))

    pl_item = (plateau or {}).get("by_exercise", {}).get(exercise_name)
    if pl_item and bool(pl_item.get("possible_plateau")):
        payload["plateau_status"] = f"Possible Plateau • {pl_item.get('likely_reason', '')}"

    return payload


def render_exercise_library_page(assets_dir: Path, workout_log_df: pd.DataFrame | None = None):
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
            if st.button(label, key=f"exercise_pick_{idx}", width='stretch'):
                st.session_state.exercise_library_selected = str(row["exercise"])
    st.markdown('</div>', unsafe_allow_html=True)

    profile = intel.get_profile(st.session_state.exercise_library_selected)
    source_log = workout_log_df if workout_log_df is not None else _safe_read_csv(_DATA_DIR / "workout_log.csv")
    progression = analyze_progressive_overload(source_log, library_df)
    plateau = detect_plateaus(source_log)
    coach = _exercise_snapshot(source_log, st.session_state.exercise_library_selected, progression, plateau)

    muscle_snapshot = build_muscle_readiness_snapshot(
        workout_log_df=source_log,
        recovery_df=_safe_read_csv(_DATA_DIR / "recovery_log.csv"),
        body_df=_safe_read_csv(_DATA_DIR / "body_stats.csv"),
    )
    render_exercise_detail_panel(profile, assets_dir, muscle_snapshot)

    st.markdown("### Exercise Intelligence")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("Last Performance", coach["last_performance"])
    i2.metric("Personal Best", coach["personal_best"])
    i3.metric("Estimated 1RM", coach["estimated_1rm"])
    i4.metric("AI Progression", coach["progression"])

    st.caption(f"Primary muscle: {profile.get('primary_muscles', ['Unknown'])[0] if profile.get('primary_muscles') else 'Unknown'}")
    st.caption(f"Secondary muscles: {', '.join(profile.get('secondary_muscles', []) or ['N/A'])}")
    st.caption(f"Plateau status: {coach['plateau_status']}")
    st.caption(f"Suggested next weight: {coach['suggested_next_weight']} • Suggested rep range: {coach['suggested_rep_range']}")
    st.caption(f"Weight trend: {coach['weight_trend']} • Rep trend: {coach['rep_trend']} • Volume trend: {coach['volume_trend']}")

    recent_sessions = coach.get("recent_sessions", pd.DataFrame())
    if recent_sessions is not None and not recent_sessions.empty:
        c1, c2, c3 = st.columns(3)
        c1.line_chart(recent_sessions.set_index("date")["weight_lbs"])
        c2.line_chart(recent_sessions.set_index("date")["reps"])
        c3.line_chart(recent_sessions.set_index("date")["volume"])
        st.dataframe(recent_sessions, width='stretch')
