from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from engines.recovery_engine import (
    RECOVERY_COLUMNS,
    ensure_recovery_log,
    get_latest_recovery,
    load_recovery_log,
    save_recovery_entry,
)


def _safe_read(path: Path, columns):
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns)


def _latest_nutrition_defaults(nutrition_path: Path):
    nutrition_cols = ["date", "meal", "calories", "protein_g", "carbs_g", "fat_g", "water_oz", "notes"]
    df = _safe_read(nutrition_path, nutrition_cols)
    if df.empty:
        return 0.0, 0.0, 0.0

    today = str(date.today())
    daily = df[df["date"].astype(str) == today] if "date" in df.columns else pd.DataFrame()
    source = daily if not daily.empty else df.tail(1)

    calories = pd.to_numeric(source.get("calories", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    protein = pd.to_numeric(source.get("protein_g", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    hydration = pd.to_numeric(source.get("water_oz", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    return float(calories), float(protein), float(hydration)


def _latest_body_defaults(body_path: Path):
    body_cols = [
        "date",
        "body_weight_lbs",
        "goal_weight_lbs",
        "waist_in",
        "body_fat_pct",
        "muscle_mass_lbs",
        "bmi",
        "water_pct",
        "protein_pct",
        "bone_mass_lbs",
        "bmr_cal",
        "metabolic_age",
        "visceral_fat",
        "lean_body_mass_lbs",
        "notes",
    ]
    df = _safe_read(body_path, body_cols)
    if df.empty:
        return 180.0, 20.0

    latest = df.iloc[-1]
    weight = pd.to_numeric(pd.Series([latest.get("body_weight_lbs", 180)]), errors="coerce").fillna(180).iloc[0]
    body_fat = pd.to_numeric(pd.Series([latest.get("body_fat_pct", 20)]), errors="coerce").fillna(20).iloc[0]
    return float(weight), float(body_fat)


def _latest_intensity_default(workout_log_path: Path):
    log_cols = [
        "date",
        "day",
        "exercise",
        "set_number",
        "weight_lbs",
        "reps",
        "rpe",
        "pain",
        "pain_score",
        "body_feedback_score",
        "notes",
        "pain_notes",
        "body_feedback_notes",
        "volume",
    ]
    df = _safe_read(workout_log_path, log_cols)
    if df.empty:
        return "Normal"

    if "date" not in df.columns:
        return "Normal"

    latest_date = str(df["date"].astype(str).iloc[-1])
    latest = df[df["date"].astype(str) == latest_date]
    if latest.empty or "rpe" not in latest.columns:
        return "Normal"

    avg_rpe = pd.to_numeric(latest["rpe"], errors="coerce").fillna(0).mean()
    if avg_rpe >= 8.5:
        return "Heavy"
    if avg_rpe >= 6.5:
        return "Normal"
    if avg_rpe > 0:
        return "Light"
    return "Normal"


def render_recovery_center(recovery_path: Path, nutrition_path: Path, body_path: Path, workout_log_path: Path):
    ensure_recovery_log(recovery_path)

    default_calories, default_protein, default_hydration = _latest_nutrition_defaults(nutrition_path)
    default_weight, default_body_fat = _latest_body_defaults(body_path)
    default_intensity = _latest_intensity_default(workout_log_path)

    st.markdown(
        '<div class="hero"><div class="kicker">PROJECT TITAN</div><div class="title">Recovery Center</div><div class="sub">Daily readiness scoring to guide intensity and protect long-term performance.</div></div>',
        unsafe_allow_html=True,
    )

    latest = get_latest_recovery(recovery_path)
    if latest:
        c1, c2, c3 = st.columns(3)
        c1.metric("Daily Recovery Score", f"{int(latest.get('recovery_score', 0))}/100")
        c2.metric("Recovery Status", str(latest.get("recovery_status", "-")))
        c3.metric("Readiness Color", str(latest.get("readiness_color", "-")))

    st.markdown("### Daily Recovery Inputs")
    col1, col2, col3 = st.columns(3)

    with col1:
        sleep_hours = st.number_input("Sleep Hours", min_value=0.0, max_value=14.0, value=7.0, step=0.25)
        sleep_quality = st.number_input("Sleep Quality (1-10)", min_value=1.0, max_value=10.0, value=7.0, step=1.0)
        soreness = st.number_input("Muscle Soreness (1-10)", min_value=1.0, max_value=10.0, value=4.0, step=1.0)
        energy = st.number_input("Energy Level (1-10)", min_value=1.0, max_value=10.0, value=7.0, step=1.0)

    with col2:
        stress = st.number_input("Stress Level (1-10)", min_value=1.0, max_value=10.0, value=4.0, step=1.0)
        hydration = st.number_input("Hydration (oz)", min_value=0.0, max_value=300.0, value=float(default_hydration), step=4.0)
        previous_intensity = st.selectbox(
            "Previous Workout Intensity",
            ["Heavy", "Normal", "Light", "Recovery"],
            index=["Heavy", "Normal", "Light", "Recovery"].index(default_intensity)
            if default_intensity in ["Heavy", "Normal", "Light", "Recovery"]
            else 1,
        )
        calories = st.number_input("Calories", min_value=0.0, max_value=8000.0, value=float(default_calories), step=50.0)

    with col3:
        protein = st.number_input("Protein", min_value=0.0, max_value=500.0, value=float(default_protein), step=5.0)
        body_weight = st.number_input("Body Weight", min_value=1.0, max_value=600.0, value=float(default_weight), step=0.5)
        body_fat = st.number_input("Body Fat %", min_value=1.0, max_value=80.0, value=float(default_body_fat), step=0.1)

    if st.button("Compute Recovery", use_container_width=True):
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sleep_hours": sleep_hours,
            "sleep_quality": sleep_quality,
            "muscle_soreness": soreness,
            "energy_level": energy,
            "stress_level": stress,
            "hydration_oz": hydration,
            "previous_workout_intensity": previous_intensity,
            "calories": calories,
            "protein_g": protein,
            "body_weight_lbs": body_weight,
            "body_fat_pct": body_fat,
        }
        result = save_recovery_entry(recovery_path, payload)
        st.success("Recovery entry saved.")

        st.markdown("### Recovery Outputs")
        o1, o2, o3 = st.columns(3)
        o1.metric("Recovery %", f"{int(result.get('recovery_pct', 0))}%")
        o2.metric("Recovery Status", str(result.get("recovery_status", "-")))
        o3.metric("Readiness Color", str(result.get("readiness_color", "-")))

        st.markdown(
            f'<div class="side-card"><div class="side-title">AI Recommendation</div><div class="small">{result.get("recommendation", "")}</div><div class="small" style="margin-top:8px;">Last Updated: {payload["timestamp"]}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Recovery History")
    hist = load_recovery_log(recovery_path)
    if hist.empty:
        st.info("No recovery entries yet. Compute your first readiness score above.")
    else:
        st.dataframe(hist.tail(30)[RECOVERY_COLUMNS], use_container_width=True, hide_index=True)
