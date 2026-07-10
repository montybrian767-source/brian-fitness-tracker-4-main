from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_log(log_df: pd.DataFrame) -> pd.DataFrame:
    base = log_df.copy() if log_df is not None else pd.DataFrame()
    for col in ["date", "exercise", "weight_lbs", "reps", "rpe", "volume", "workout_session_id"]:
        if col not in base.columns:
            base[col] = 0 if col in {"weight_lbs", "reps", "rpe", "volume"} else ""

    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).copy()
    for col in ["weight_lbs", "reps", "rpe", "volume"]:
        base[col] = _to_num(base[col]).fillna(0)
    base["exercise"] = base["exercise"].astype(str).str.strip()
    base = base[base["exercise"].ne("")]
    base["session_key"] = base["workout_session_id"].astype(str).str.strip()
    empty = base["session_key"].eq("")
    base.loc[empty, "session_key"] = base.loc[empty, "date"].dt.date.astype(str)
    return base


def _session_rollup(ex_df: pd.DataFrame) -> pd.DataFrame:
    sessions = (
        ex_df.groupby("session_key", as_index=False)
        .agg(
            date=("date", "max"),
            max_weight=("weight_lbs", "max"),
            max_reps=("reps", "max"),
            avg_rpe=("rpe", "mean"),
            volume=("volume", "sum"),
            est_1rm=("weight_lbs", lambda s: 0.0),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    if sessions.empty:
        return sessions

    e1rm_values = []
    for _, row in sessions.iterrows():
        e1rm_values.append(float(row["max_weight"]) * (1 + (float(row["max_reps"]) / 30.0)))
    sessions["est_1rm"] = e1rm_values
    return sessions


def _likely_reason(last3: pd.DataFrame) -> str:
    if last3.empty:
        return "Limited data"
    if (last3["avg_rpe"] >= 9.0).all():
        return "Repeated high RPE"
    if last3["volume"].iloc[-1] < last3["volume"].iloc[0] * 0.95:
        return "Volume trending downward"
    if last3["est_1rm"].iloc[-1] <= last3["est_1rm"].iloc[0] * 1.01:
        return "Estimated 1RM not improving"
    return "Weight unchanged with no rep improvement"


def _adjustment_from_reason(reason: str) -> str:
    reason_l = str(reason).lower()
    if "high rpe" in reason_l:
        return "Reduce load temporarily and add recovery"
    if "volume" in reason_l:
        return "Change rep range and restore quality volume"
    if "1rm" in reason_l:
        return "Add reps before adding load"
    if "unchanged" in reason_l:
        return "Replace exercise variation or maintain one more session"
    return "Maintain current plan for one more session"


def detect_plateaus(
    workout_log_df: pd.DataFrame,
    min_sessions: int = 3,
) -> Dict:
    log_df = _normalize_log(workout_log_df)
    if log_df.empty:
        return {
            "has_sufficient_history": False,
            "message": "Complete more workouts to improve personalized recommendations.",
            "plateaus": [],
            "by_exercise": {},
        }

    findings: List[Dict] = []
    by_exercise: Dict[str, Dict] = {}

    for exercise, ex_df in log_df.groupby("exercise"):
        sessions = _session_rollup(ex_df)
        if len(sessions) < min_sessions:
            continue

        last3 = sessions.tail(3).reset_index(drop=True)
        unchanged_weight = float(last3["max_weight"].max() - last3["max_weight"].min()) <= 0.01
        no_rep_improvement = float(last3["max_reps"].iloc[-1]) <= float(last3["max_reps"].iloc[0])
        est1rm_flat = float(last3["est_1rm"].iloc[-1]) <= float(last3["est_1rm"].iloc[0] * 1.01)
        volume_down = float(last3["volume"].iloc[-1]) < float(last3["volume"].iloc[0] * 0.95)
        repeated_high_rpe = bool((last3["avg_rpe"] >= 9.0).sum() >= 2)
        missed_target_reps = bool((last3["max_reps"] <= 6).sum() >= 2)

        is_plateau = (
            (unchanged_weight and no_rep_improvement)
            or est1rm_flat
            or volume_down
            or repeated_high_rpe
            or missed_target_reps
        )

        sessions_stalled = int(len(last3)) if is_plateau else 0
        reason = _likely_reason(last3) if is_plateau else "No plateau signal"
        adjustment = _adjustment_from_reason(reason) if is_plateau else "Maintain current progression"

        payload = {
            "exercise": exercise,
            "possible_plateau": bool(is_plateau),
            "sessions_stalled": sessions_stalled,
            "likely_reason": reason,
            "recommended_adjustment": adjustment,
            "supporting_signals": {
                "weight_unchanged_no_rep_improvement": bool(unchanged_weight and no_rep_improvement),
                "estimated_1rm_not_improving": bool(est1rm_flat),
                "volume_trending_down": bool(volume_down),
                "repeated_high_rpe": bool(repeated_high_rpe),
                "missed_target_reps": bool(missed_target_reps),
            },
            "confidence_note": "Possible plateau signal, not a certainty.",
        }
        by_exercise[exercise] = payload
        if is_plateau:
            findings.append(payload)

    return {
        "has_sufficient_history": bool(by_exercise),
        "message": "" if by_exercise else "Complete more workouts to improve personalized recommendations.",
        "plateaus": sorted(findings, key=lambda x: x["exercise"].lower()),
        "by_exercise": by_exercise,
    }
