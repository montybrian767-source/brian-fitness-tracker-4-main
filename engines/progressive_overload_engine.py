from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


DEFAULT_INCREMENT_RULES = {
    "dumbbell": 5.0,
    "machine": 5.0,
    "barbell": 5.0,
    "lower_body_machine": 10.0,
    "other": 2.5,
}


LOWER_BODY_MUSCLES = {"quads", "hamstrings", "glutes", "calves"}


@dataclass
class ProgressionResult:
    exercise: str
    last_weight: float
    last_reps: float
    last_rpe: float
    recent_avg_weight: float
    recent_avg_reps: float
    estimated_1rm: float
    best_estimated_1rm: float
    volume_trend: str
    sessions_since_last_progression: int
    performance_trend: str
    suggested_action: str
    suggested_weight: float
    suggested_rep_range: str
    rationale: str


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_log(log_df: pd.DataFrame) -> pd.DataFrame:
    base = log_df.copy() if log_df is not None else pd.DataFrame()
    for col in [
        "date",
        "exercise",
        "weight_lbs",
        "reps",
        "rpe",
        "volume",
        "set_number",
        "workout_session_id",
    ]:
        if col not in base.columns:
            base[col] = 0 if col in {"weight_lbs", "reps", "rpe", "volume", "set_number"} else ""

    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).copy()
    for col in ["weight_lbs", "reps", "rpe", "volume", "set_number"]:
        base[col] = _to_num(base[col]).fillna(0)

    base["exercise"] = base["exercise"].astype(str).str.strip()
    base = base[base["exercise"].ne("")]
    base["session_key"] = base["workout_session_id"].astype(str).str.strip()
    empty = base["session_key"].eq("")
    base.loc[empty, "session_key"] = base.loc[empty, "date"].dt.date.astype(str)
    return base.sort_values(["date", "set_number"]).reset_index(drop=True)


def _parse_rep_range(value: object) -> Tuple[int, int]:
    text = str(value or "").strip().lower().replace("reps", "").replace("rep", "")
    if not text:
        return 8, 12
    if "-" in text:
        left, right = text.split("-", 1)
        try:
            lo = int(float(left.strip()))
            hi = int(float(right.strip().split()[0]))
            if lo > hi:
                lo, hi = hi, lo
            return max(1, lo), max(1, hi)
        except Exception:
            return 8, 12
    try:
        val = int(float(text.split()[0]))
        return max(1, val), max(1, val)
    except Exception:
        return 8, 12


def _classify_equipment(exercise_name: str, workouts_df: Optional[pd.DataFrame]) -> str:
    if workouts_df is None or workouts_df.empty:
        lowered = str(exercise_name).lower()
        if "dumbbell" in lowered:
            return "dumbbell"
        if "barbell" in lowered:
            return "barbell"
        if "machine" in lowered or "press" in lowered:
            return "machine"
        return "other"

    hit = workouts_df[workouts_df["exercise"].astype(str).str.lower() == str(exercise_name).lower()]
    if hit.empty:
        return _classify_equipment(exercise_name, None)

    row = hit.iloc[0]
    ex_text = str(row.get("exercise", "")).lower()
    group_text = str(row.get("muscle_group", "")).lower()
    if "dumbbell" in ex_text:
        return "dumbbell"
    if "barbell" in ex_text:
        return "barbell"
    if "machine" in ex_text:
        if any(m in group_text for m in LOWER_BODY_MUSCLES):
            return "lower_body_machine"
        return "machine"
    return "other"


def _increment_for_exercise(exercise_name: str, workouts_df: Optional[pd.DataFrame]) -> float:
    equipment = _classify_equipment(exercise_name, workouts_df)
    return DEFAULT_INCREMENT_RULES.get(equipment, DEFAULT_INCREMENT_RULES["other"])


def _performance_trend(ex_df: pd.DataFrame) -> str:
    recent = ex_df.tail(6).copy()
    if len(recent) < 3:
        return "insufficient_data"
    recent["est_1rm"] = recent["weight_lbs"] * (1 + (recent["reps"] / 30.0))
    first = float(recent.head(3)["est_1rm"].mean())
    last = float(recent.tail(3)["est_1rm"].mean())
    if last >= first * 1.02:
        return "improving"
    if last <= first * 0.98:
        return "declining"
    return "stable"


def _volume_trend(ex_df: pd.DataFrame) -> str:
    recent = ex_df.tail(8).copy()
    if len(recent) < 4:
        return "stable"
    first = float(recent.head(4)["volume"].mean())
    last = float(recent.tail(4)["volume"].mean())
    if last >= first * 1.04:
        return "up"
    if last <= first * 0.96:
        return "down"
    return "stable"


def _sessions_since_progression(ex_df: pd.DataFrame) -> int:
    sessions = (
        ex_df.groupby("session_key", as_index=False)
        .agg(weight=("weight_lbs", "max"), reps=("reps", "max"), date=("date", "max"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    if len(sessions) < 2:
        return 0

    best_weight = float(sessions["weight"].iloc[-1])
    best_reps = float(sessions["reps"].iloc[-1])
    count = 0
    for i in range(len(sessions) - 2, -1, -1):
        prior_w = float(sessions.iloc[i]["weight"])
        prior_r = float(sessions.iloc[i]["reps"])
        if prior_w < best_weight or (prior_w == best_weight and prior_r < best_reps):
            break
        count += 1
    return int(count)


def _action_and_target(
    exercise: str,
    ex_df: pd.DataFrame,
    target_rep_range: Tuple[int, int],
    workouts_df: Optional[pd.DataFrame],
) -> Tuple[str, float, str, str]:
    last = ex_df.iloc[-1]
    last_weight = float(last["weight_lbs"])
    last_reps = float(last["reps"])
    last_rpe = float(last["rpe"])
    trend = _performance_trend(ex_df)

    rep_low, rep_high = target_rep_range
    recent = ex_df.tail(4)
    avg_rpe = float(recent["rpe"].mean()) if not recent.empty else last_rpe
    min_recent_reps = float(recent["reps"].min()) if not recent.empty else last_reps

    increment = _increment_for_exercise(exercise, workouts_df)

    if min_recent_reps <= rep_low - 2 and avg_rpe >= 9.2:
        next_weight = max(0.0, last_weight - increment)
        return (
            "Reduce Weight",
            next_weight,
            f"{rep_low}-{rep_high}",
            "Reps are dropping and RPE is consistently high; reduce load temporarily.",
        )

    if avg_rpe >= 9.4 and trend == "declining":
        return (
            "Recovery Recommended",
            last_weight,
            f"{rep_low}-{rep_high}",
            "High effort with decline trend; prioritize recovery before progression.",
        )

    if last_reps >= rep_high and avg_rpe <= 8.0 and trend in {"stable", "improving"}:
        next_weight = last_weight + increment
        return (
            "Increase Weight",
            next_weight,
            f"{rep_low}-{rep_high}",
            "Target reps achieved with manageable effort and stable/improving performance.",
        )

    if last_reps < rep_high and avg_rpe <= 8.5 and trend in {"stable", "improving"}:
        return (
            "Increase Reps",
            last_weight,
            f"{rep_low}-{rep_high}",
            "Keep weight stable and progress reps toward the top of the range.",
        )

    if 8.0 <= avg_rpe <= 9.0 and trend == "stable":
        return (
            "Hold Weight",
            last_weight,
            f"{rep_low}-{rep_high}",
            "Performance is stable with moderate-hard effort; hold load and refine execution.",
        )

    return (
        "Hold Weight",
        last_weight,
        f"{rep_low}-{rep_high}",
        "No clear progression signal yet; keep load steady and collect more sessions.",
    )


def analyze_progressive_overload(
    workout_log_df: pd.DataFrame,
    workouts_df: Optional[pd.DataFrame] = None,
) -> Dict:
    log_df = _normalize_log(workout_log_df)
    if log_df.empty:
        return {
            "has_sufficient_history": False,
            "message": "Complete more workouts to improve personalized recommendations.",
            "recommendations": [],
            "by_exercise": {},
        }

    out: List[ProgressionResult] = []
    by_exercise: Dict[str, Dict] = {}

    for exercise, ex_df in log_df.groupby("exercise"):
        ex_df = ex_df.sort_values(["date", "set_number"]).reset_index(drop=True)
        if len(ex_df) < 2:
            continue

        target_range = (8, 12)
        if workouts_df is not None and not workouts_df.empty and "target_reps" in workouts_df.columns:
            match = workouts_df[workouts_df["exercise"].astype(str).str.lower() == exercise.lower()]
            if not match.empty:
                target_range = _parse_rep_range(match.iloc[0].get("target_reps"))

        last = ex_df.iloc[-1]
        recent = ex_df.tail(5)
        est_1rm_series = ex_df["weight_lbs"] * (1 + (ex_df["reps"] / 30.0))
        action, next_weight, rep_range_text, rationale = _action_and_target(
            exercise=exercise,
            ex_df=ex_df,
            target_rep_range=target_range,
            workouts_df=workouts_df,
        )

        result = ProgressionResult(
            exercise=exercise,
            last_weight=round(float(last["weight_lbs"]), 1),
            last_reps=round(float(last["reps"]), 1),
            last_rpe=round(float(last["rpe"]), 1),
            recent_avg_weight=round(float(recent["weight_lbs"].mean()), 1),
            recent_avg_reps=round(float(recent["reps"].mean()), 1),
            estimated_1rm=round(float(est_1rm_series.iloc[-1]), 1),
            best_estimated_1rm=round(float(est_1rm_series.max()), 1),
            volume_trend=_volume_trend(ex_df),
            sessions_since_last_progression=_sessions_since_progression(ex_df),
            performance_trend=_performance_trend(ex_df),
            suggested_action=action,
            suggested_weight=round(float(next_weight), 1),
            suggested_rep_range=rep_range_text,
            rationale=rationale,
        )
        out.append(result)
        by_exercise[exercise] = result.__dict__

    if not out:
        return {
            "has_sufficient_history": False,
            "message": "Complete more workouts to improve personalized recommendations.",
            "recommendations": [],
            "by_exercise": {},
        }

    recommendations = [r.__dict__ for r in sorted(out, key=lambda x: x.exercise.lower())]
    return {
        "has_sufficient_history": True,
        "message": "",
        "recommendations": recommendations,
        "by_exercise": by_exercise,
    }
