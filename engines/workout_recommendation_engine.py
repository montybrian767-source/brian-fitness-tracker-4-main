from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from engines.progressive_overload_engine import analyze_progressive_overload


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_log(log_df: pd.DataFrame) -> pd.DataFrame:
    base = log_df.copy() if log_df is not None else pd.DataFrame()
    for col in ["date", "day", "exercise", "weight_lbs", "reps", "rpe", "volume", "workout_session_id"]:
        if col not in base.columns:
            base[col] = 0 if col in {"weight_lbs", "reps", "rpe", "volume"} else ""
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).copy()
    for col in ["weight_lbs", "reps", "rpe", "volume"]:
        base[col] = _to_num(base[col]).fillna(0)
    base["exercise"] = base["exercise"].astype(str).str.strip()
    base = base[base["exercise"].ne("")]
    return base


def _parse_rep_range(value: object) -> Tuple[int, int]:
    text = str(value or "").strip().lower().replace("reps", "").replace("rep", "")
    if not text:
        return 8, 12
    if "-" in text:
        left, right = text.split("-", 1)
        try:
            lo = int(float(left.strip()))
            hi = int(float(right.strip().split()[0]))
            return max(1, min(lo, hi)), max(1, max(lo, hi))
        except Exception:
            return 8, 12
    try:
        val = int(float(text.split()[0]))
        return max(1, val), max(1, val)
    except Exception:
        return 8, 12


def _last_trained_by_day(log_df: pd.DataFrame) -> Dict[str, pd.Timestamp]:
    if log_df.empty or "day" not in log_df.columns:
        return {}
    tmp = log_df.copy()
    tmp["day"] = tmp["day"].astype(str)
    return tmp.groupby("day")["date"].max().to_dict()


def _focus_from_readiness(
    workouts_df: pd.DataFrame,
    recovery_snapshot: Optional[Dict],
    history_df: pd.DataFrame,
) -> str:
    if recovery_snapshot:
        top_ready = recovery_snapshot.get("top_ready", []) or []
        ready_muscles = [str(x.get("muscle", "")).lower() for x in top_ready]
        if any(m in ready_muscles for m in ["chest", "shoulders", "triceps"]):
            return "Push"
        if any(m in ready_muscles for m in ["back", "biceps"]):
            return "Pull"
        if any(m in ready_muscles for m in ["quads", "hamstrings", "glutes", "calves"]):
            return "Legs"

    if workouts_df.empty or "day" not in workouts_df.columns:
        return "Full Body"

    day_map = _last_trained_by_day(history_df)
    if not day_map:
        return str(workouts_df.iloc[0].get("day", "Full Body"))

    sorted_days = sorted(day_map.items(), key=lambda x: x[1])
    last_day = str(sorted_days[-1][0]) if sorted_days else ""
    all_days = [str(d) for d in workouts_df["day"].dropna().astype(str).unique().tolist()]
    if not all_days:
        return "Full Body"

    if last_day in all_days:
        idx = all_days.index(last_day)
        return all_days[(idx + 1) % len(all_days)]
    return all_days[0]


def _build_exercise_rows(
    base_plan: pd.DataFrame,
    progression_map: Dict[str, Dict],
    max_exercises: int,
) -> List[Dict]:
    exercises: List[Dict] = []
    for _, row in base_plan.head(max_exercises).iterrows():
        exercise = str(row.get("exercise", "")).strip()
        if not exercise:
            continue

        target_sets = int(_to_num(pd.Series([row.get("target_sets", 3)])).fillna(3).iloc[0])
        target_reps = str(row.get("target_reps", "8-12"))
        rep_lo, rep_hi = _parse_rep_range(target_reps)
        prog = progression_map.get(exercise, {})

        suggested_weight = float(_to_num(pd.Series([prog.get("suggested_weight", row.get("base_weight", 0))])).fillna(0).iloc[0])
        suggested_action = str(prog.get("suggested_action", "Hold Weight"))
        rationale = str(prog.get("rationale", "Use clean reps and log performance."))

        exercises.append(
            {
                "exercise": exercise,
                "muscle_group": str(row.get("muscle_group", "General")),
                "suggested_sets": max(1, target_sets),
                "suggested_rep_range": f"{rep_lo}-{rep_hi}",
                "suggested_starting_weight": round(suggested_weight, 1),
                "rest_seconds": 120 if rep_hi <= 6 else 90,
                "progression_action": suggested_action,
                "coaching_note": rationale,
            }
        )
    return exercises


def generate_next_workout(
    workout_log_df: pd.DataFrame,
    workouts_df: pd.DataFrame,
    recovery_snapshot: Optional[Dict] = None,
    max_exercises: int = 8,
) -> Dict:
    log_df = _normalize_log(workout_log_df)
    if workouts_df is None or workouts_df.empty:
        return {
            "has_sufficient_history": False,
            "message": "Complete more workouts to improve personalized recommendations.",
            "focus": "N/A",
            "estimated_duration_min": 0,
            "intensity": "Moderate",
            "recommended_exercises": [],
            "coaching_note": "Workout plan data is missing.",
        }

    progression = analyze_progressive_overload(log_df, workouts_df)
    progression_map = progression.get("by_exercise", {})

    focus = _focus_from_readiness(workouts_df, recovery_snapshot, log_df)

    if focus in workouts_df["day"].astype(str).tolist():
        plan_rows = workouts_df[workouts_df["day"].astype(str) == focus].copy()
    else:
        plan_rows = workouts_df[workouts_df["muscle_group"].astype(str).str.contains(str(focus), case=False, na=False)].copy()
        if plan_rows.empty:
            plan_rows = workouts_df.copy()

    if log_df.empty or len(log_df["exercise"].unique()) < 3:
        return {
            "has_sufficient_history": False,
            "message": "Complete more workouts to improve personalized recommendations.",
            "focus": str(focus),
            "estimated_duration_min": 0,
            "intensity": "Moderate",
            "recommended_exercises": _build_exercise_rows(plan_rows, progression_map, max_exercises=5),
            "coaching_note": "Baseline recommendation from your existing weekly plan.",
        }

    recent14 = log_df[log_df["date"] >= (pd.Timestamp(date.today()) - pd.Timedelta(days=13))]
    avg_recent_rpe = float(recent14["rpe"].mean()) if not recent14.empty else 7.5
    recent_volume = float(recent14["volume"].sum()) if not recent14.empty else 0.0

    if avg_recent_rpe >= 9.0:
        intensity = "Lower"
    elif avg_recent_rpe >= 8.0:
        intensity = "Moderate"
    else:
        intensity = "High"

    exercises = _build_exercise_rows(plan_rows, progression_map, max_exercises=max(5, min(8, int(max_exercises))))
    if intensity == "Lower":
        for item in exercises:
            item["suggested_sets"] = max(2, int(item["suggested_sets"]) - 1)
            item["rest_seconds"] = max(90, int(item["rest_seconds"]))

    est_duration = int(sum((e["suggested_sets"] * 2.5) + (e["rest_seconds"] / 60.0) for e in exercises))
    est_duration = max(35, min(95, est_duration))

    ready = []
    needs_recovery = []
    if recovery_snapshot:
        ready = [str(x.get("muscle", "")).title() for x in (recovery_snapshot.get("top_ready", []) or [])]
        needs_recovery = [str(x.get("muscle", "")).title() for x in (recovery_snapshot.get("top_fatigued", []) or [])]

    coaching_note = (
        f"Focus {focus}. Keep intensity {intensity.lower()} with clean technique. "
        f"Recent 14-day volume: {int(recent_volume):,}. "
    )
    if needs_recovery:
        coaching_note += f"Limit fatigue on {', '.join(needs_recovery[:3])}. "
    if ready:
        coaching_note += f"Best readiness: {', '.join(ready[:3])}."

    return {
        "has_sufficient_history": True,
        "message": "",
        "focus": str(focus),
        "estimated_duration_min": est_duration,
        "intensity": intensity,
        "recommended_exercises": exercises,
        "coaching_note": coaching_note.strip(),
    }
