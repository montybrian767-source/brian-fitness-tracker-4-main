from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List

import pandas as pd


REQUIRED_LOG_COLUMNS = [
    "date",
    "day",
    "exercise",
    "set_number",
    "weight_lbs",
    "reps",
    "rpe",
    "pain",
    "body_feedback_score",
    "notes",
    "body_feedback_notes",
    "volume",
]


@dataclass
class WorkoutGrade:
    date: str
    volume_score: float
    intensity_score: float
    consistency_score: float
    completion_score: float
    overall_score: float
    label: str



def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")



def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))



def normalize_workout_log(df: pd.DataFrame) -> pd.DataFrame:
    log_df = df.copy() if df is not None else pd.DataFrame(columns=REQUIRED_LOG_COLUMNS)
    for col in REQUIRED_LOG_COLUMNS:
        if col not in log_df.columns:
            log_df[col] = ""

    log_df["date"] = pd.to_datetime(log_df["date"], errors="coerce")
    for col in ["weight_lbs", "reps", "volume", "rpe", "pain", "body_feedback_score"]:
        log_df[col] = _to_num(log_df[col]).fillna(0)

    log_df = log_df.dropna(subset=["date"])
    return log_df



def build_pr_summary(workout_log_df: pd.DataFrame) -> Dict:
    log_df = normalize_workout_log(workout_log_df)
    if log_df.empty:
        return {
            "total_prs": 0,
            "rows": pd.DataFrame(columns=["exercise", "heaviest_weight", "most_reps", "highest_est_1rm", "highest_total_volume"]),
            "top_exercises": [],
        }

    log_df = log_df.copy()
    log_df["exercise"] = log_df["exercise"].astype(str).str.strip()
    log_df = log_df[log_df["exercise"].ne("")]

    if log_df.empty:
        return {
            "total_prs": 0,
            "rows": pd.DataFrame(columns=["exercise", "heaviest_weight", "most_reps", "highest_est_1rm", "highest_total_volume"]),
            "top_exercises": [],
        }

    log_df["est_1rm"] = log_df["weight_lbs"] * (1 + (log_df["reps"] / 30.0))

    grouped = log_df.groupby("exercise", as_index=False).agg(
        heaviest_weight=("weight_lbs", "max"),
        most_reps=("reps", "max"),
        highest_est_1rm=("est_1rm", "max"),
        highest_total_volume=("volume", "max"),
    )

    grouped = grouped.sort_values(["highest_est_1rm", "heaviest_weight"], ascending=False).reset_index(drop=True)

    return {
        "total_prs": int(len(grouped)),
        "rows": grouped,
        "top_exercises": grouped.head(5)["exercise"].tolist(),
    }



def workout_streak_days(workout_log_df: pd.DataFrame) -> int:
    log_df = normalize_workout_log(workout_log_df)
    if log_df.empty:
        return 0

    unique_days = sorted({d.date() for d in log_df["date"]})
    if not unique_days:
        return 0

    streak = 0
    cursor = unique_days[-1]
    day_set = set(unique_days)
    while cursor in day_set:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak



def compute_workout_grade(workout_log_df: pd.DataFrame, target_sessions_per_week: int = 5) -> WorkoutGrade:
    log_df = normalize_workout_log(workout_log_df)
    if log_df.empty:
        return WorkoutGrade(
            date="N/A",
            volume_score=0.0,
            intensity_score=0.0,
            consistency_score=0.0,
            completion_score=0.0,
            overall_score=0.0,
            label="Needs Work",
        )

    latest_date = log_df["date"].max()
    latest_workout = log_df[log_df["date"] == latest_date].copy()

    volume_total = float(latest_workout["volume"].sum())
    avg_rpe = float(latest_workout["rpe"].mean()) if not latest_workout.empty else 0.0
    avg_reps = float(latest_workout["reps"].mean()) if not latest_workout.empty else 0.0

    volume_score = _clamp((volume_total / 5000.0) * 100.0)
    intensity_score = _clamp((avg_rpe / 10.0) * 65.0 + min(35.0, (avg_reps / 15.0) * 35.0))

    seven_day_cut = latest_date - pd.Timedelta(days=6)
    recent = log_df[log_df["date"] >= seven_day_cut]
    sessions_last_7 = recent["date"].dt.date.nunique()
    consistency_score = _clamp((sessions_last_7 / max(1, target_sessions_per_week)) * 100.0)

    per_day_sets = log_df.groupby(log_df["date"].dt.date).size().sort_values(ascending=False)
    baseline_sets = float(per_day_sets.iloc[1:].mean()) if len(per_day_sets) > 1 else float(per_day_sets.iloc[0])
    latest_sets = float(len(latest_workout))
    baseline_sets = baseline_sets if baseline_sets > 0 else max(1.0, latest_sets)
    completion_score = _clamp((latest_sets / baseline_sets) * 100.0)

    overall = _clamp(
        (volume_score * 0.30)
        + (intensity_score * 0.25)
        + (consistency_score * 0.25)
        + (completion_score * 0.20)
    )

    if overall >= 95:
        label = "A+"
    elif overall >= 90:
        label = "A"
    elif overall >= 80:
        label = "B"
    elif overall >= 70:
        label = "C"
    else:
        label = "Needs Work"

    return WorkoutGrade(
        date=str(latest_date.date()),
        volume_score=round(volume_score, 1),
        intensity_score=round(intensity_score, 1),
        consistency_score=round(consistency_score, 1),
        completion_score=round(completion_score, 1),
        overall_score=round(overall, 1),
        label=label,
    )



def performance_scores(workout_log_df: pd.DataFrame) -> Dict[str, float]:
    log_df = normalize_workout_log(workout_log_df)
    if log_df.empty:
        return {
            "strength_score": 0.0,
            "fitness_score": 0.0,
            "weekly_volume": 0.0,
            "personal_records": 0.0,
        }

    today = pd.Timestamp(date.today())
    week_cut = today - pd.Timedelta(days=6)
    recent = log_df[log_df["date"] >= week_cut]

    weekly_volume = float(recent["volume"].sum())
    sessions = float(recent["date"].dt.date.nunique())

    strength_score = _clamp(min(60.0, log_df["weight_lbs"].max() * 0.35) + min(40.0, log_df["reps"].max() * 1.5))
    fitness_score = _clamp((sessions / 5.0) * 45.0 + min(35.0, weekly_volume / 250.0) + min(20.0, log_df["exercise"].nunique() * 1.25))

    prs = build_pr_summary(log_df)

    return {
        "strength_score": round(strength_score, 1),
        "fitness_score": round(fitness_score, 1),
        "weekly_volume": round(weekly_volume, 1),
        "personal_records": float(prs["total_prs"]),
    }



def recovery_recommendation(recovery_pct: float, workout_grade: WorkoutGrade, muscle_snapshot: Dict) -> Dict[str, str]:
    fatigued = [m for m in (muscle_snapshot.get("top_fatigued", []) or []) if m.get("status") in {"Red", "Recover", "Fatigued", "Orange"}]

    if recovery_pct >= 85 and workout_grade.overall_score >= 85 and len(fatigued) <= 1:
        training = "Train hard"
        note = "You are ready for a high-intensity session with progressive overload."
    elif recovery_pct >= 70:
        training = "Moderate workout"
        note = "Use controlled intensity and keep technique sharp."
    elif recovery_pct >= 55:
        training = "Stretch / mobility"
        note = "Lower the load and focus on movement quality and blood flow."
    else:
        training = "Recovery day"
        note = "Prioritize recovery. Avoid heavy loading today."

    hydration = "Hydration reminder: target 100 oz water today."
    sleep = "Sleep goal: 7.5 to 9 hours tonight."

    return {
        "training": training,
        "note": note,
        "hydration": hydration,
        "sleep": sleep,
    }
