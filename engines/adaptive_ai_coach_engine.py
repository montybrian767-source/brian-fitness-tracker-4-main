from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from engines.plateau_detection_engine import detect_plateaus
from engines.progressive_overload_engine import analyze_progressive_overload


UPPER_TOKENS = ["chest", "back", "shoulders", "biceps", "triceps", "upper", "push", "pull"]
LOWER_TOKENS = ["legs", "quads", "hamstrings", "glutes", "calves", "lower"]
CORE_TOKENS = ["core", "abs"]


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return str(value)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def _normalize_strength_history(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if df is not None else pd.DataFrame()
    for col in ["date", "day", "exercise", "weight_lbs", "reps", "rpe", "volume", "workout_session_id", "body_feedback_score"]:
        if col not in base.columns:
            base[col] = 0 if col in {"weight_lbs", "reps", "rpe", "volume", "body_feedback_score"} else ""
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).copy()
    for col in ["weight_lbs", "reps", "rpe", "volume", "body_feedback_score"]:
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)
    base["exercise"] = base["exercise"].astype(str).str.strip()
    base["day"] = base["day"].astype(str).str.strip()
    base = base[base["exercise"].ne("")]
    base["estimated_1rm"] = base["weight_lbs"] * (1 + (base["reps"] / 30.0))
    return base.sort_values(["date", "exercise"]).reset_index(drop=True)


def _distance_to_miles(value: Any, unit: Any) -> float:
    distance = _to_float(value, 0.0)
    label = _to_text(unit, "").strip().lower()
    if distance <= 0:
        return 0.0
    if label == "miles":
        return distance
    if label == "kilometers":
        return distance * 0.621371
    if label == "meters":
        return distance * 0.000621371
    if label == "yards":
        return distance * 0.000568182
    return 0.0


def _normalize_cardio_history(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if df is not None else pd.DataFrame()
    for col in ["activity_date", "activity_type", "category", "duration_minutes", "distance_value", "distance_unit", "calories_burned", "average_heart_rate", "rpe", "apple_workout_key", "workout_session_id"]:
        if col not in base.columns:
            base[col] = 0 if col in {"duration_minutes", "distance_value", "calories_burned", "average_heart_rate", "rpe"} else ""
    base["activity_date"] = pd.to_datetime(base["activity_date"], errors="coerce")
    base = base.dropna(subset=["activity_date"]).copy()
    for col in ["duration_minutes", "distance_value", "calories_burned", "average_heart_rate", "rpe"]:
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)
    base["activity_type"] = base["activity_type"].astype(str).str.strip()
    base["category"] = base["category"].astype(str).str.strip().str.lower().replace("", "cardio")
    base["distance_miles"] = base.apply(lambda row: _distance_to_miles(row.get("distance_value", 0), row.get("distance_unit", "")), axis=1)
    return base.sort_values(["activity_date", "activity_type"]).reset_index(drop=True)


def _normalize_apple_daily(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if df is not None else pd.DataFrame()
    if base.empty:
        return pd.DataFrame()
    if "activity_date" not in base.columns:
        return pd.DataFrame()
    base["activity_date"] = pd.to_datetime(base["activity_date"], errors="coerce", utc=True)
    base = base.dropna(subset=["activity_date"]).copy()
    numeric_cols = ["steps", "active_energy_kcal", "exercise_minutes", "stand_hours", "sleep_hours", "heart_rate_variability_ms", "resting_heart_rate"]
    for col in numeric_cols:
        if col not in base.columns:
            base[col] = pd.NA
        base[col] = pd.to_numeric(base[col], errors="coerce")
    return base.sort_values("activity_date").reset_index(drop=True)


def _normalize_apple_workouts(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if df is not None else pd.DataFrame()
    if base.empty:
        return pd.DataFrame()
    if "start_time" not in base.columns:
        return pd.DataFrame()
    base["start_time"] = pd.to_datetime(base["start_time"], errors="coerce", utc=True)
    base = base.dropna(subset=["start_time"]).copy()
    for col in ["duration_minutes", "total_energy_kcal", "total_distance_miles", "average_heart_rate"]:
        if col not in base.columns:
            base[col] = 0.0
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)
    if "workout_type" not in base.columns:
        base["workout_type"] = ""
    base["workout_type"] = base["workout_type"].astype(str).str.strip()
    return base.sort_values("start_time").reset_index(drop=True)


def _normalize_body_stats(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if df is not None else pd.DataFrame()
    if base.empty:
        return pd.DataFrame()
    if "date" not in base.columns:
        return pd.DataFrame()
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).copy()
    for col in ["body_weight_lbs", "body_fat_pct", "muscle_mass_lbs", "lean_body_mass_lbs"]:
        if col not in base.columns:
            base[col] = pd.NA
        base[col] = pd.to_numeric(base[col], errors="coerce")
    return base.sort_values("date").reset_index(drop=True)


def _extract_preferences(current_plan: Any) -> Dict[str, Any]:
    payload = current_plan if isinstance(current_plan, dict) else {}
    prefs = dict(payload.get("preferences", {}) or {})
    prefs.setdefault("preferred_workout_duration", 55)
    prefs.setdefault("training_days_per_week", 5)
    prefs.setdefault("preferred_cardio_types", ["Walking", "Outdoor Cycling", "Pickleball"])
    prefs.setdefault("preferred_strength_split", "Balanced Split")
    prefs.setdefault("equipment_access", "Full Gym")
    prefs.setdefault("aggressiveness", "Balanced")
    prefs.setdefault("avoided_exercises", [])
    prefs.setdefault("preferred_rest_days", ["Sunday"])
    return prefs


def _extract_goals(current_plan: Any) -> Dict[str, Any]:
    payload = current_plan if isinstance(current_plan, dict) else {}
    goals = dict(payload.get("goals", {}) or {})
    goals.setdefault("primary_goal", "Improve Fitness")
    goals.setdefault("secondary_goals", [])
    return goals


def _extract_workouts_df(current_plan: Any) -> pd.DataFrame:
    payload = current_plan if isinstance(current_plan, dict) else {}
    workouts_df = payload.get("workouts_df")
    return workouts_df.copy() if isinstance(workouts_df, pd.DataFrame) else pd.DataFrame()


def _readiness_score(readiness_result: Dict[str, Any]) -> int:
    return _to_int(readiness_result.get("readiness_score", 50), 50)


def _recent_strength_summary(strength_history: pd.DataFrame, target_date: date) -> Dict[str, Any]:
    if strength_history.empty:
        return {
            "days_trained_7": 0,
            "days_trained_14": 0,
            "weekly_volume": 0.0,
            "avg_rpe_7": 0.0,
            "high_rpe_sessions": 0,
            "body_feedback_avg_7": 0.0,
            "last_strength_date": None,
        }
    cutoff7 = pd.Timestamp(target_date) - pd.Timedelta(days=6)
    cutoff14 = pd.Timestamp(target_date) - pd.Timedelta(days=13)
    week = strength_history[strength_history["date"] >= cutoff7]
    fortnight = strength_history[strength_history["date"] >= cutoff14]
    sessions7 = int(week["date"].dt.date.nunique()) if not week.empty else 0
    sessions14 = int(fortnight["date"].dt.date.nunique()) if not fortnight.empty else 0
    session_rpe = week.groupby(week["date"].dt.date)["rpe"].mean() if not week.empty else pd.Series(dtype=float)
    high_rpe_sessions = int((session_rpe >= 9.0).sum()) if not session_rpe.empty else 0
    return {
        "days_trained_7": sessions7,
        "days_trained_14": sessions14,
        "weekly_volume": float(week["volume"].sum()) if not week.empty else 0.0,
        "avg_rpe_7": float(week["rpe"].mean()) if not week.empty else 0.0,
        "high_rpe_sessions": high_rpe_sessions,
        "body_feedback_avg_7": float(week["body_feedback_score"].mean()) if not week.empty else 0.0,
        "last_strength_date": week["date"].max() if not week.empty else strength_history["date"].max(),
    }


def _recent_cardio_summary(cardio_history: pd.DataFrame, target_date: date) -> Dict[str, Any]:
    if cardio_history.empty:
        return {
            "weekly_minutes": 0.0,
            "weekly_distance": 0.0,
            "weekly_sessions": 0,
            "avg_rpe_7": 0.0,
            "last_cardio_date": None,
            "top_activity": "",
            "pickleball_minutes": 0.0,
            "lower_body_minutes": 0.0,
            "upper_body_minutes": 0.0,
        }
    cutoff7 = pd.Timestamp(target_date) - pd.Timedelta(days=6)
    week = cardio_history[cardio_history["activity_date"] >= cutoff7].copy()
    if week.empty:
        week = cardio_history.tail(14).copy()
    lower_body_types = {"Running", "Treadmill", "Walking", "Outdoor Cycling", "Cycling", "Stationary Bike", "Stair Stepper", "Pickleball", "Tennis", "Basketball", "Soccer"}
    upper_body_types = {"Swimming", "Rowing"}
    top_activity = ""
    if not week.empty:
        counts = week.groupby("activity_type").size().sort_values(ascending=False)
        if not counts.empty:
            top_activity = str(counts.index[0])
    return {
        "weekly_minutes": float(week["duration_minutes"].sum()) if not week.empty else 0.0,
        "weekly_distance": float(week["distance_miles"].sum()) if not week.empty else 0.0,
        "weekly_sessions": int(len(week)) if not week.empty else 0,
        "avg_rpe_7": float(week["rpe"].mean()) if not week.empty else 0.0,
        "last_cardio_date": week["activity_date"].max() if not week.empty else cardio_history["activity_date"].max(),
        "top_activity": top_activity,
        "pickleball_minutes": float(week[week["activity_type"].eq("Pickleball")]["duration_minutes"].sum()) if not week.empty else 0.0,
        "lower_body_minutes": float(week[week["activity_type"].isin(lower_body_types)]["duration_minutes"].sum()) if not week.empty else 0.0,
        "upper_body_minutes": float(week[week["activity_type"].isin(upper_body_types)]["duration_minutes"].sum()) if not week.empty else 0.0,
    }


def _latest_apple_context(apple_daily: pd.DataFrame, target_date: date) -> Dict[str, Any]:
    if apple_daily.empty:
        return {"missing": ["sleep", "hrv", "resting_hr", "steps"]}
    rows = apple_daily[apple_daily["activity_date"].dt.date <= target_date]
    if rows.empty:
        rows = apple_daily
    latest = rows.iloc[-1].to_dict()
    missing = []
    if pd.isna(latest.get("sleep_hours")):
        missing.append("sleep")
    if pd.isna(latest.get("heart_rate_variability_ms")):
        missing.append("hrv")
    if pd.isna(latest.get("resting_heart_rate")):
        missing.append("resting_hr")
    if pd.isna(latest.get("steps")):
        missing.append("steps")
    latest["missing"] = missing
    return latest


def _ready_and_recovering_muscles(workouts_df: pd.DataFrame, readiness_result: Dict[str, Any], cardio_summary: Dict[str, Any]) -> Dict[str, List[str]]:
    day_groups = []
    if not workouts_df.empty and "muscle_group" in workouts_df.columns:
        day_groups = sorted(set(workouts_df["muscle_group"].astype(str).tolist()))
    positives = [str(x).lower() for x in (readiness_result.get("positive_factors", []) or [])]
    limiting = [str(x).lower() for x in (readiness_result.get("limiting_factors", []) or [])]

    ready = []
    recovering = []
    for group in day_groups:
        lower = group.lower()
        if any(token in lower for token in LOWER_TOKENS):
            if cardio_summary.get("lower_body_minutes", 0.0) >= 75:
                recovering.append(group)
            else:
                ready.append(group)
        elif any(token in lower for token in ["shoulder", "back"]) and cardio_summary.get("upper_body_minutes", 0.0) >= 45:
            recovering.append(group)
        else:
            ready.append(group)
    if any("sleep" in item for item in limiting) or any("hrv" in item for item in limiting):
        recovering = sorted(set(recovering + ready[:2]))
        ready = [item for item in ready if item not in recovering]
    return {
        "muscle_groups_ready": ready[:6],
        "muscle_groups_recovering": recovering[:6],
    }


def recommend_workout_category(
    readiness_result: Dict[str, Any],
    strength_history: pd.DataFrame,
    cardio_history: pd.DataFrame,
    apple_daily: pd.DataFrame,
    apple_workouts: pd.DataFrame,
    current_plan: Any,
    target_date: date,
) -> Dict[str, Any]:
    score = _readiness_score(readiness_result)
    prefs = _extract_preferences(current_plan)
    goals = _extract_goals(current_plan)
    strength_summary = _recent_strength_summary(strength_history, target_date)
    cardio_summary = _recent_cardio_summary(cardio_history, target_date)
    apple_context = _latest_apple_context(apple_daily, target_date)

    reasons: List[str] = []
    category = "Strength"
    if score <= 55:
        category = "Recovery"
        reasons.append("Readiness is low, so recovery is safer than loading another hard session.")
    elif _to_float(apple_context.get("sleep_hours"), 0.0) > 0 and _to_float(apple_context.get("sleep_hours"), 0.0) < 6.0:
        category = "Recovery"
        reasons.append("Sleep is below target, so training stress is reduced.")
    elif cardio_summary["lower_body_minutes"] >= 120 and score < 80:
        category = "Strength"
        reasons.append("Recent cardio heavily loaded the lower body, so strength should shift away from that fatigue.")
    elif cardio_summary["weekly_minutes"] >= 210 and strength_summary["days_trained_7"] >= 3:
        category = "Recovery"
        reasons.append("Recent total training load is already high across strength and cardio.")
    elif score >= 78 and strength_summary["days_trained_7"] >= 2 and cardio_summary["weekly_minutes"] >= 45 and prefs.get("preferred_workout_duration", 55) >= 50:
        category = "Mixed"
        reasons.append("Readiness and recent balance support a combined strength and cardio session.")
    elif cardio_summary["weekly_minutes"] < 60 and goals.get("primary_goal") in {"Improve Fitness", "Improve Endurance", "Lose Fat", "General Health"}:
        category = "Cardio"
        reasons.append("Recent cardio volume is low relative to the current goal.")
    elif cardio_summary["pickleball_minutes"] >= 60 and goals.get("primary_goal") == "Pickleball Performance":
        category = "Sport"
        reasons.append("Pickleball is already a frequent activity and matches the primary goal.")
    else:
        category = "Strength"
        reasons.append("Readiness is acceptable and strength progression history is available.")

    preferred_rest_days = {str(x) for x in (prefs.get("preferred_rest_days") or [])}
    if target_date.strftime("%A") in preferred_rest_days and score < 75:
        category = "Recovery"
        reasons.append("This is a preferred rest day and readiness is not high enough to override it.")

    return {
        "recommended_category": category,
        "coaching_reasons": reasons,
        "strength_summary": strength_summary,
        "cardio_summary": cardio_summary,
        "apple_context": apple_context,
    }


def recommend_training_focus(
    recommended_category: str,
    readiness_result: Dict[str, Any],
    strength_history: pd.DataFrame,
    cardio_history: pd.DataFrame,
    current_plan: Any,
    target_date: date,
) -> Dict[str, Any]:
    workouts_df = _extract_workouts_df(current_plan)
    prefs = _extract_preferences(current_plan)
    goals = _extract_goals(current_plan)
    cardio_summary = _recent_cardio_summary(cardio_history, target_date)
    muscle_map = _ready_and_recovering_muscles(workouts_df, readiness_result, cardio_summary)

    if recommended_category == "Recovery":
        return {
            "recommended_focus": "Recovery / Walking",
            "muscle_groups_ready": muscle_map["muscle_groups_ready"],
            "muscle_groups_recovering": muscle_map["muscle_groups_recovering"],
        }
    if recommended_category == "Cardio":
        preferred = list(prefs.get("preferred_cardio_types") or [])
        activity = preferred[0] if preferred else (cardio_summary.get("top_activity") or "Walking")
        return {
            "recommended_focus": f"{activity} Cardio",
            "muscle_groups_ready": muscle_map["muscle_groups_ready"],
            "muscle_groups_recovering": muscle_map["muscle_groups_recovering"],
        }
    if recommended_category == "Sport":
        if goals.get("primary_goal") == "Pickleball Performance":
            focus = "Pickleball Session"
        else:
            preferred = list(prefs.get("preferred_cardio_types") or [])
            sport = next((item for item in preferred if item in {"Pickleball", "Tennis", "Basketball", "Soccer", "Golf"}), "Pickleball")
            focus = f"{sport} Session"
        return {
            "recommended_focus": focus,
            "muscle_groups_ready": muscle_map["muscle_groups_ready"],
            "muscle_groups_recovering": muscle_map["muscle_groups_recovering"],
        }
    if recommended_category == "Mixed":
        if muscle_map["muscle_groups_recovering"] and muscle_map["muscle_groups_ready"]:
            focus = f"{muscle_map['muscle_groups_ready'][0]} + Cardio Finisher"
        else:
            focus = "Upper Body + Cardio Finisher"
        return {
            "recommended_focus": focus,
            "muscle_groups_ready": muscle_map["muscle_groups_ready"],
            "muscle_groups_recovering": muscle_map["muscle_groups_recovering"],
        }

    weekday = target_date.strftime("%A")
    if not workouts_df.empty and "day" in workouts_df.columns:
        today_rows = workouts_df[workouts_df["day"].astype(str) == weekday]
        if not today_rows.empty:
            focus = str(today_rows.iloc[0].get("muscle_group", weekday))
        else:
            focus = str(workouts_df.iloc[0].get("muscle_group", "Strength"))
    else:
        focus = "Strength"

    if muscle_map["muscle_groups_recovering"]:
        recovering_lower = " ".join(muscle_map["muscle_groups_recovering"]).lower()
        if any(token in recovering_lower for token in LOWER_TOKENS):
            upper_ready = next((g for g in muscle_map["muscle_groups_ready"] if not any(token in g.lower() for token in LOWER_TOKENS)), None)
            if upper_ready:
                focus = upper_ready
    return {
        "recommended_focus": focus,
        "muscle_groups_ready": muscle_map["muscle_groups_ready"],
        "muscle_groups_recovering": muscle_map["muscle_groups_recovering"],
    }


def recommend_strength_adjustments(
    readiness_result: Dict[str, Any],
    strength_history: pd.DataFrame,
    current_plan: Any,
) -> Dict[str, Any]:
    workouts_df = _extract_workouts_df(current_plan)
    prefs = _extract_preferences(current_plan)
    progression = analyze_progressive_overload(strength_history, workouts_df)
    plateau = detect_plateaus(strength_history)
    score = _readiness_score(readiness_result)
    avg_rpe_recent = _to_float(strength_history.tail(20).get("rpe", pd.Series(dtype=float)).mean() if not strength_history.empty else 0.0, 0.0)
    body_feedback_recent = _to_float(strength_history.tail(20).get("body_feedback_score", pd.Series(dtype=float)).mean() if not strength_history.empty else 0.0, 0.0)

    aggressiveness = str(prefs.get("aggressiveness", "Balanced"))
    duration_pref = _to_int(prefs.get("preferred_workout_duration", 55), 55)
    base_volume_adjust = 0
    rpe_ceiling = 8.0
    intensity_level = "Moderate"
    intensity_percent = "70-80%"
    if score <= 55:
        base_volume_adjust = -45
        rpe_ceiling = 6.5
        intensity_level = "Low"
        intensity_percent = "55-65%"
    elif score <= 69:
        base_volume_adjust = -20
        rpe_ceiling = 7.0
        intensity_level = "Moderate"
        intensity_percent = "60-72%"
    elif score >= 85:
        base_volume_adjust = 5 if aggressiveness == "Progressive" else 0
        rpe_ceiling = 8.5 if aggressiveness != "Conservative" else 8.0
        intensity_level = "Moderate-Heavy"
        intensity_percent = "72-85%"

    if avg_rpe_recent >= 9.0 or body_feedback_recent >= 4.0:
        base_volume_adjust = min(base_volume_adjust, -20)
        rpe_ceiling = min(rpe_ceiling, 7.0)
        intensity_level = "Moderate"
        intensity_percent = "60-72%"

    recommended_exercises: List[Dict[str, Any]] = []
    exercises_to_hold: List[str] = []
    exercises_to_reduce: List[str] = []
    reasons: List[str] = []
    by_exercise = progression.get("by_exercise", {}) or {}
    plateau_map = plateau.get("by_exercise", {}) or {}

    plan_rows = workouts_df.copy()
    if not plan_rows.empty and "exercise" in plan_rows.columns:
        plan_rows = plan_rows.head(8)
    for _, row in plan_rows.iterrows():
        exercise = _to_text(row.get("exercise", "")).strip()
        if not exercise:
            continue
        prog = by_exercise.get(exercise) or by_exercise.get(exercise.strip()) or {}
        plateau_info = plateau_map.get(exercise) or plateau_map.get(exercise.strip()) or {}
        suggested_sets = max(1, _to_int(row.get("target_sets", 3), 3))
        if base_volume_adjust <= -20:
            suggested_sets = max(1, suggested_sets - 1)
        suggested_weight = _to_float(prog.get("suggested_weight", row.get("base_weight", 0.0)), _to_float(row.get("base_weight", 0.0), 0.0))
        action = _to_text(prog.get("suggested_action", "Hold Weight"), "Hold Weight")
        reason = _to_text(prog.get("rationale", "Collect more sessions to refine progression."))
        confidence = 76
        last_rpe = _to_float(prog.get("last_rpe", 0.0), 0.0)
        trend = _to_text(prog.get("performance_trend", "stable"))
        if score <= 60 or last_rpe >= 9.0 or bool(plateau_info.get("possible_plateau")):
            if action == "Increase Weight":
                action = "Hold Weight"
                reason = "Aggressive progression was held back by readiness, high effort, or plateau signals."
            if last_rpe >= 9.0 or bool(plateau_info.get("possible_plateau")):
                action = "Reduce Load" if score <= 60 or last_rpe >= 9.3 else "Hold Weight"
                exercises_to_reduce.append(exercise) if action == "Reduce Load" else exercises_to_hold.append(exercise)
                suggested_weight = max(0.0, suggested_weight - (5.0 if suggested_weight >= 80 else 2.5)) if action == "Reduce Load" else suggested_weight
        elif action == "Hold Weight":
            exercises_to_hold.append(exercise)
        if trend == "improving" and action == "Increase Weight":
            confidence += 8
        if trend == "declining":
            confidence -= 15
        if last_rpe >= 8.5:
            confidence -= 12
        recommended_exercises.append(
            {
                "exercise": exercise,
                "muscle_group": _to_text(row.get("muscle_group", "General")),
                "suggested_sets": suggested_sets,
                "suggested_rep_range": _to_text(prog.get("suggested_rep_range", row.get("target_reps", "8-12"))),
                "suggested_starting_weight": round(suggested_weight, 1),
                "rest_seconds": 120 if "6" in _to_text(prog.get("suggested_rep_range", "")) else 90,
                "progression_action": action,
                "confidence": max(35, min(95, confidence)),
                "reason": reason,
                "last_weight": _to_float(prog.get("last_weight", 0.0), 0.0),
                "last_reps": _to_float(prog.get("last_reps", 0.0), 0.0),
                "last_rpe": last_rpe,
            }
        )
        if action == "Increase Weight":
            reasons.append(f"{exercise} can progress because recent reps were completed at manageable effort.")
        elif action in {"Reduce Load", "Recovery Recommended"}:
            reasons.append(f"{exercise} should be reduced because effort or recovery signals are limiting progression.")
    duration_minutes = max(25, min(90, duration_pref + int(base_volume_adjust * 0.2)))
    return {
        "recommended_exercises": recommended_exercises,
        "exercises_to_hold": sorted(set(exercises_to_hold))[:8],
        "exercises_to_reduce": sorted(set(exercises_to_reduce))[:8],
        "intensity_level": intensity_level,
        "intensity_percent": intensity_percent,
        "duration_minutes": duration_minutes,
        "volume_adjustment_percent": int(base_volume_adjust),
        "rpe_ceiling": rpe_ceiling,
        "coaching_reasons": reasons,
        "progression": progression,
        "plateau": plateau,
    }


def recommend_cardio_adjustments(
    recommended_category: str,
    readiness_result: Dict[str, Any],
    cardio_history: pd.DataFrame,
    apple_workouts: pd.DataFrame,
    current_plan: Any,
    target_date: date,
) -> Dict[str, Any]:
    prefs = _extract_preferences(current_plan)
    goals = _extract_goals(current_plan)
    cardio_summary = _recent_cardio_summary(cardio_history, target_date)
    preferred = list(prefs.get("preferred_cardio_types") or [])
    activity = preferred[0] if preferred else (cardio_summary.get("top_activity") or "Walking")
    score = _readiness_score(readiness_result)

    if recommended_category == "Sport":
        sport = next((item for item in preferred if item in {"Pickleball", "Tennis", "Basketball", "Soccer", "Golf"}), None)
        activity = sport or ("Pickleball" if goals.get("primary_goal") == "Pickleball Performance" else "Tennis")
    elif recommended_category == "Recovery":
        activity = "Walking"
    elif recommended_category == "Mixed":
        activity = "Treadmill"

    duration = 30
    intensity = "Easy"
    rpe_target = 4.0
    zone = None
    distance_target = None
    recovery_impact = "Low"
    reason = "Keeps aerobic work aligned with current recovery state."

    if activity in {"Outdoor Cycling", "Stationary Bike", "Treadmill", "Running", "Rowing", "Swimming"} and score >= 75:
        duration = 35 if recommended_category == "Cardio" else 15
        intensity = "Moderate"
        rpe_target = 6.0 if recommended_category == "Cardio" else 5.0
        recovery_impact = "Moderate"
        reason = f"{activity} fits current readiness without overshooting recent load."
    if activity == "Walking":
        duration = 25 if score <= 70 else 30
        intensity = "Easy"
        rpe_target = 3.0
        recovery_impact = "Low"
        reason = "Walking adds activity with low recovery cost."
    if activity == "Pickleball":
        duration = 60 if score >= 75 else 45
        intensity = "Normal Session"
        rpe_target = 6.5
        recovery_impact = "Moderate-High"
        reason = "Pickleball supports the current goal, but should limit next-day lower-body volume."
    if activity == "Swimming":
        duration = 30 if score < 75 else 40
        intensity = "Moderate"
        rpe_target = 6.0
        recovery_impact = "Moderate"
        reason = "Swimming can build fitness, but shoulder pressing should stay conservative afterward."

    if not apple_workouts.empty and "average_heart_rate" in apple_workouts.columns:
        hr = pd.to_numeric(apple_workouts.get("average_heart_rate"), errors="coerce").dropna()
        if not hr.empty:
            median_hr = int(hr.tail(20).median())
            zone = f"~{max(90, median_hr - 10)}-{median_hr + 5} bpm"
    if activity in {"Walking", "Running", "Treadmill", "Outdoor Cycling", "Stationary Bike"}:
        if activity in {"Walking", "Running", "Treadmill"}:
            distance_target = round(duration / 15.0, 1) if activity == "Walking" else round(duration / 10.0, 1)
        else:
            distance_target = round(duration / 3.0, 1)

    return {
        "activity_type": activity,
        "duration_minutes": duration,
        "intensity": intensity,
        "heart_rate_zone": zone,
        "distance_target": distance_target,
        "rpe_target": rpe_target,
        "recovery_impact": recovery_impact,
        "reason": reason,
    }


def recommend_recovery_actions(
    readiness_result: Dict[str, Any],
    cardio_history: pd.DataFrame,
    apple_daily: pd.DataFrame,
    current_plan: Any,
    target_date: date,
) -> Dict[str, Any]:
    score = _readiness_score(readiness_result)
    apple_context = _latest_apple_context(apple_daily, target_date)
    cardio_summary = _recent_cardio_summary(cardio_history, target_date)
    actions = []
    if score <= 60:
        actions.append("Walk 20-30 minutes at easy effort.")
        actions.append("Prioritize hydration and an early sleep window.")
    if _to_float(apple_context.get("sleep_hours"), 0.0) > 0 and _to_float(apple_context.get("sleep_hours"), 0.0) < 6.5:
        actions.append("Target 7.5-9.0 hours of sleep tonight.")
    if cardio_summary.get("weekly_minutes", 0.0) >= 180:
        actions.append("Keep cardio easy to avoid stacking additional fatigue.")
    if not actions:
        actions.append("Maintain normal recovery habits and hydration.")
    return {"recovery_actions": actions}


def calculate_coaching_confidence(
    readiness_result: Dict[str, Any],
    strength_history: pd.DataFrame,
    cardio_history: pd.DataFrame,
    apple_daily: pd.DataFrame,
    apple_workouts: pd.DataFrame,
) -> Dict[str, Any]:
    score = 28.0
    missing: List[str] = []
    strength_days = int(strength_history["date"].dt.date.nunique()) if not strength_history.empty else 0
    cardio_days = int(cardio_history["activity_date"].dt.date.nunique()) if not cardio_history.empty else 0
    apple_days = int(apple_daily["activity_date"].dt.date.nunique()) if not apple_daily.empty else 0
    score += min(22.0, strength_days * 1.2)
    score += min(14.0, cardio_days * 1.0)
    score += min(16.0, apple_days * 0.7)
    ready_conf = _to_float((readiness_result.get("data_quality", {}) or {}).get("readiness_confidence", readiness_result.get("confidence_score", 0.0)), 0.0)
    score += min(18.0, ready_conf * 0.18)
    latest_apple = _latest_apple_context(apple_daily, date.today())
    missing.extend(list(latest_apple.get("missing", [])))
    if apple_workouts.empty:
        missing.append("apple_workouts")
    if strength_days < 4:
        missing.append("strength_history_depth")
    if cardio_days < 3:
        missing.append("cardio_history_depth")
    score -= min(26.0, len(set(missing)) * 4.0)
    score = max(20.0, min(95.0, score))
    if score >= 78:
        label = "High confidence"
    elif score >= 55:
        label = "Moderate confidence"
    else:
        label = "Limited confidence"
    return {
        "confidence_score": round(score, 1),
        "confidence_label": label,
        "missing_data": sorted(set(missing)),
    }


def build_coaching_explanation(
    recommended_category: str,
    recommended_focus: str,
    readiness_result: Dict[str, Any],
    category_decision: Dict[str, Any],
    strength_adjustments: Dict[str, Any],
    cardio_recommendation: Dict[str, Any],
    confidence: Dict[str, Any],
) -> Dict[str, Any]:
    positives = list((readiness_result.get("positive_factors", []) or []))[:4]
    limiting = list((readiness_result.get("limiting_factors", []) or []))[:4]
    reasons = list(category_decision.get("coaching_reasons", [])) + list(strength_adjustments.get("coaching_reasons", []))[:3]
    if recommended_category in {"Cardio", "Sport", "Recovery"}:
        reasons.append(_to_text(cardio_recommendation.get("reason", "")))
    reasons = [item for item in reasons if _to_text(item).strip()]
    if not reasons:
        reasons.append("Recommendation is based on available training, recovery, and activity data.")
    main_reason = reasons[0]
    return {
        "main_reason": main_reason,
        "why_this_plan": f"{recommended_category} is recommended with a focus on {recommended_focus}.",
        "positive_factors": positives or ["No strong positive factor available from current data."],
        "limiting_factors": limiting or ["No major limiting factor detected from current data."],
        "missing_data": list(confidence.get("missing_data", [])),
        "coaching_reasons": reasons,
    }


def build_next_7_day_outlook(
    target_date: date,
    readiness_result: Dict[str, Any],
    strength_history: pd.DataFrame,
    cardio_history: pd.DataFrame,
    apple_daily: pd.DataFrame,
    apple_workouts: pd.DataFrame,
    body_stats: pd.DataFrame,
    current_plan: Any,
) -> List[Dict[str, Any]]:
    workouts_df = _extract_workouts_df(current_plan)
    categories = []
    focus_cycle = []
    if not workouts_df.empty and "muscle_group" in workouts_df.columns:
        focus_cycle = [str(x) for x in workouts_df["muscle_group"].astype(str).dropna().unique().tolist() if str(x).strip()]
    if not focus_cycle:
        focus_cycle = ["Upper Body", "Lower Body", "Cardio", "Recovery"]

    score = _readiness_score(readiness_result)
    recent_cardio = _recent_cardio_summary(cardio_history, target_date)
    outlook: List[Dict[str, Any]] = []
    for idx in range(7):
        day = target_date + timedelta(days=idx)
        est_readiness = max(48, min(92, score + (4 if idx in {2, 5} else 0) - (8 if idx in {1, 4} and recent_cardio.get("weekly_minutes", 0.0) > 120 else 0) - (3 if idx == 0 else 0)))
        if est_readiness <= 58:
            category = "Recovery"
            focus = "Recovery / Walking"
            duration = 25
            goal = "Restore readiness"
        elif idx in {1, 4} and recent_cardio.get("pickleball_minutes", 0.0) > 0:
            category = "Sport"
            focus = "Pickleball Session"
            duration = 60
            goal = "Sport performance"
        elif idx == 5 and est_readiness >= 78:
            category = "Mixed"
            focus = "Strength + Cardio"
            duration = 60
            goal = "Balanced workload"
        elif idx in {2, 6}:
            category = "Cardio"
            focus = "Cardio Base"
            duration = 35
            goal = "Aerobic support"
        else:
            category = "Strength"
            focus = focus_cycle[idx % len(focus_cycle)]
            duration = 55
            goal = "Progress strength"
        confidence = "High confidence" if est_readiness >= 75 else ("Moderate confidence" if est_readiness >= 60 else "Limited confidence")
        outlook.append(
            {
                "date": str(day),
                "day": day.strftime("%A"),
                "recommended_category": category,
                "focus": focus,
                "estimated_readiness": int(est_readiness),
                "duration_minutes": duration,
                "main_goal": goal,
                "confidence": confidence,
            }
        )
    return outlook


def build_daily_coaching_plan(
    target_date: Any,
    readiness_result: Dict[str, Any],
    strength_history: Optional[pd.DataFrame],
    cardio_history: Optional[pd.DataFrame],
    apple_daily: Optional[pd.DataFrame],
    apple_workouts: Optional[pd.DataFrame],
    body_stats: Optional[pd.DataFrame],
    current_plan: Any,
) -> Dict[str, Any]:
    target = pd.to_datetime(target_date, errors="coerce")
    if pd.isna(target):
        target = pd.Timestamp(date.today())
    target_day = target.date()

    strength_df = _normalize_strength_history(strength_history)
    cardio_df = _normalize_cardio_history(cardio_history)
    apple_daily_df = _normalize_apple_daily(apple_daily)
    apple_workouts_df = _normalize_apple_workouts(apple_workouts)
    body_df = _normalize_body_stats(body_stats)

    category_decision = recommend_workout_category(
        readiness_result=readiness_result,
        strength_history=strength_df,
        cardio_history=cardio_df,
        apple_daily=apple_daily_df,
        apple_workouts=apple_workouts_df,
        current_plan=current_plan,
        target_date=target_day,
    )
    recommended_category = _to_text(category_decision.get("recommended_category", "Strength"), "Strength")
    focus_decision = recommend_training_focus(
        recommended_category=recommended_category,
        readiness_result=readiness_result,
        strength_history=strength_df,
        cardio_history=cardio_df,
        current_plan=current_plan,
        target_date=target_day,
    )
    strength_adjustments = recommend_strength_adjustments(
        readiness_result=readiness_result,
        strength_history=strength_df,
        current_plan=current_plan,
    )
    cardio_recommendation = recommend_cardio_adjustments(
        recommended_category=recommended_category,
        readiness_result=readiness_result,
        cardio_history=cardio_df,
        apple_workouts=apple_workouts_df,
        current_plan=current_plan,
        target_date=target_day,
    )
    recovery_actions = recommend_recovery_actions(
        readiness_result=readiness_result,
        cardio_history=cardio_df,
        apple_daily=apple_daily_df,
        current_plan=current_plan,
        target_date=target_day,
    )
    confidence = calculate_coaching_confidence(
        readiness_result=readiness_result,
        strength_history=strength_df,
        cardio_history=cardio_df,
        apple_daily=apple_daily_df,
        apple_workouts=apple_workouts_df,
    )
    explanation = build_coaching_explanation(
        recommended_category=recommended_category,
        recommended_focus=_to_text(focus_decision.get("recommended_focus", "Strength")),
        readiness_result=readiness_result,
        category_decision=category_decision,
        strength_adjustments=strength_adjustments,
        cardio_recommendation=cardio_recommendation,
        confidence=confidence,
    )
    outlook = build_next_7_day_outlook(
        target_date=target_day,
        readiness_result=readiness_result,
        strength_history=strength_df,
        cardio_history=cardio_df,
        apple_daily=apple_daily_df,
        apple_workouts=apple_workouts_df,
        body_stats=body_df,
        current_plan=current_plan,
    )

    duration_minutes = strength_adjustments.get("duration_minutes", 45)
    if recommended_category in {"Cardio", "Sport", "Recovery"}:
        duration_minutes = cardio_recommendation.get("duration_minutes", duration_minutes)
    if recommended_category == "Mixed":
        duration_minutes = max(duration_minutes, cardio_recommendation.get("duration_minutes", 15) + max(20, duration_minutes - 15))

    recommended_exercises = list(strength_adjustments.get("recommended_exercises", []))
    if recommended_category in {"Cardio", "Sport", "Recovery"}:
        recommended_exercises = []
    elif recommended_category == "Mixed":
        recommended_exercises = recommended_exercises[:4]

    cardio_block = None
    if recommended_category in {"Cardio", "Sport", "Mixed", "Recovery"}:
        cardio_block = {
            "activity_type": cardio_recommendation.get("activity_type"),
            "duration_minutes": cardio_recommendation.get("duration_minutes"),
            "intensity": cardio_recommendation.get("intensity"),
            "heart_rate_zone": cardio_recommendation.get("heart_rate_zone"),
            "distance_target": cardio_recommendation.get("distance_target"),
            "rpe_target": cardio_recommendation.get("rpe_target"),
            "reason": cardio_recommendation.get("reason"),
        }

    if recommended_category == "Recovery":
        recommended_exercises = [
            {"exercise": "Mobility Flow", "suggested_sets": 1, "suggested_rep_range": "10-15 min", "suggested_starting_weight": 0.0, "rest_seconds": 0, "progression_action": "Recovery"},
            {"exercise": "Easy Walk", "suggested_sets": 1, "suggested_rep_range": f"{cardio_recommendation.get('duration_minutes', 25)} min", "suggested_starting_weight": 0.0, "rest_seconds": 0, "progression_action": "Recovery"},
        ]

    return {
        "recommended_category": recommended_category,
        "recommended_focus": _to_text(focus_decision.get("recommended_focus", "Strength")),
        "readiness_score": _readiness_score(readiness_result),
        "recovery_status": _to_text(readiness_result.get("recovery_status", "Moderate"), "Moderate"),
        "intensity_level": strength_adjustments.get("intensity_level", "Moderate") if recommended_category in {"Strength", "Mixed"} else cardio_recommendation.get("intensity", "Easy"),
        "intensity_percent": _to_text(strength_adjustments.get("intensity_percent", "60-72%")),
        "duration_minutes": int(duration_minutes),
        "volume_adjustment_percent": int(strength_adjustments.get("volume_adjustment_percent", 0)),
        "rpe_ceiling": float(strength_adjustments.get("rpe_ceiling", 7.5)),
        "recommended_exercises": recommended_exercises,
        "cardio_recommendation": cardio_block,
        "exercises_to_hold": list(strength_adjustments.get("exercises_to_hold", [])),
        "exercises_to_reduce": list(strength_adjustments.get("exercises_to_reduce", [])),
        "muscle_groups_ready": list(focus_decision.get("muscle_groups_ready", [])),
        "muscle_groups_recovering": list(focus_decision.get("muscle_groups_recovering", [])),
        "coaching_reasons": list(explanation.get("coaching_reasons", [])),
        "confidence_score": float(confidence.get("confidence_score", 45.0)),
        "confidence_label": _to_text(confidence.get("confidence_label", "Limited confidence")),
        "missing_data": list(confidence.get("missing_data", [])),
        "next_7_day_outlook": outlook,
        "main_reason": _to_text(explanation.get("main_reason", "Recommendation is based on available data.")),
        "positive_factors": list(explanation.get("positive_factors", [])),
        "limiting_factors": list(explanation.get("limiting_factors", [])),
        "why_this_plan": _to_text(explanation.get("why_this_plan", "")),
        "recovery_actions": list(recovery_actions.get("recovery_actions", [])),
        "goal_context": _extract_goals(current_plan),
        "preferences_used": _extract_preferences(current_plan),
        "apple_context": category_decision.get("apple_context", {}),
        "strength_summary": category_decision.get("strength_summary", {}),
        "cardio_summary": category_decision.get("cardio_summary", {}),
        "safety_note": "Training recommendations are estimates based on logged fitness and activity data. They are not medical advice.",
    }
