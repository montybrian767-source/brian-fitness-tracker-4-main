from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Set

import pandas as pd

from engines.exercise_intelligence import ExerciseIntelligence


TARGET_MUSCLES = [
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "quads",
    "hamstrings",
    "glutes",
    "calves",
    "core",
]


_MUSCLE_ALIASES = {
    "chest": ["chest", "pec", "pectoral"],
    "back": ["back", "lat", "rhomboid", "trapezius", "trap", "erector"],
    "shoulders": ["shoulder", "deltoid", "rear delt", "front delt", "lateral delt"],
    "biceps": ["bicep", "biceps", "brachialis", "forearm", "brachioradialis"],
    "triceps": ["tricep", "triceps"],
    "quads": ["quad", "quadricep", "quadriceps"],
    "hamstrings": ["hamstring"],
    "glutes": ["glute", "glutes", "abductor"],
    "calves": ["calf", "calves", "soleus", "gastrocnemius"],
    "core": ["core", "abs", "abdominal", "oblique", "transverse"],
}


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def normalize_muscle_name(name: str) -> Optional[str]:
    text = str(name or "").strip().lower()
    if not text:
        return None
    for canonical, aliases in _MUSCLE_ALIASES.items():
        if any(token in text for token in aliases):
            return canonical
    return None


def _safe_latest_recovery_inputs(recovery_df: pd.DataFrame) -> Dict[str, float]:
    if recovery_df is None or recovery_df.empty:
        return {"recovery_pct": 68.0, "soreness": 0.0}

    row = recovery_df.iloc[-1]
    recovery_pct = float(_to_num(pd.Series([row.get("recovery_pct", 68)])).fillna(68).iloc[0])
    soreness = float(_to_num(pd.Series([row.get("muscle_soreness", 0)])).fillna(0).iloc[0])
    return {
        "recovery_pct": _clamp(recovery_pct, 0.0, 100.0),
        "soreness": _clamp(soreness, 0.0, 10.0),
    }


def _body_adjustment(body_df: pd.DataFrame) -> float:
    if body_df is None or body_df.empty or "date" not in body_df.columns:
        return 0.0
    d = body_df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date")
    if d.empty:
        return 0.0

    w = _to_num(d.get("body_weight_lbs", pd.Series(dtype=float))).dropna()
    if len(w) < 2:
        return 0.0
    delta = float(w.iloc[-1] - w.iloc[0])
    if delta <= -2.0:
        return -3.0
    if delta >= 2.0:
        return -1.0
    return 1.0


def _extract_profile_muscles(profile: Dict) -> Set[str]:
    candidates: List[str] = []
    candidates.extend(profile.get("primary_muscles", []) or [])
    candidates.extend(profile.get("secondary_muscles", []) or [])
    candidates.extend(profile.get("stabilizers", []) or [])
    if profile.get("muscle_group"):
        candidates.extend(str(profile.get("muscle_group")).replace("+", " ").split())

    normalized: Set[str] = set()
    for item in candidates:
        canonical = normalize_muscle_name(str(item))
        if canonical:
            normalized.add(canonical)
    return normalized


def _status_for_score(score: float) -> str:
    if score >= 78:
        return "Ready"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Fatigued"
    return "Recover"


def _action_for_status(status: str) -> str:
    if status == "Ready":
        return "Train this muscle normally or heavy with clean form."
    if status == "Moderate":
        return "Train this muscle with normal load and controlled volume."
    if status == "Fatigued":
        return "Reduce volume 20-30% and keep effort submaximal."
    return "Avoid heavy loading. Prioritize mobility, blood flow, and recovery work."


def build_muscle_recovery_snapshot(
    recovery_df: pd.DataFrame,
    workout_log_df: pd.DataFrame,
    body_df: Optional[pd.DataFrame] = None,
) -> Dict:
    latest_inputs = _safe_latest_recovery_inputs(recovery_df)
    base_recovery = latest_inputs["recovery_pct"]
    soreness = latest_inputs["soreness"]
    body_adj = _body_adjustment(body_df if body_df is not None else pd.DataFrame())
    today = pd.Timestamp(datetime.now().date())

    metrics = {
        m: {
            "weekly_volume": 0.0,
            "session_dates": set(),
            "last_trained": None,
        }
        for m in TARGET_MUSCLES
    }

    intel = ExerciseIntelligence()
    exercise_cache: Dict[str, Set[str]] = {}

    log_df = workout_log_df.copy() if workout_log_df is not None else pd.DataFrame()
    if not log_df.empty and "date" in log_df.columns and "exercise" in log_df.columns:
        log_df["date"] = pd.to_datetime(log_df["date"], errors="coerce")
        log_df = log_df.dropna(subset=["date"])
        log_df["volume"] = _to_num(log_df.get("volume", pd.Series(dtype=float))).fillna(0)

        week_cut = today - pd.Timedelta(days=7)
        for _, row in log_df.iterrows():
            ex_name = str(row.get("exercise", "")).strip()
            if not ex_name:
                continue

            if ex_name not in exercise_cache:
                profile = intel.get_profile(ex_name)
                exercise_cache[ex_name] = _extract_profile_muscles(profile)
            muscles = exercise_cache.get(ex_name, set())
            if not muscles:
                continue

            row_date = pd.Timestamp(row["date"]).normalize()
            volume = float(row.get("volume", 0.0) or 0.0)
            for muscle in muscles:
                metrics[muscle]["last_trained"] = row_date if metrics[muscle]["last_trained"] is None else max(metrics[muscle]["last_trained"], row_date)
                if row_date >= week_cut:
                    metrics[muscle]["weekly_volume"] += max(0.0, volume)
                    metrics[muscle]["session_dates"].add(str(row_date.date()))

    muscle_output: Dict[str, Dict] = {}
    for muscle in TARGET_MUSCLES:
        item = metrics[muscle]
        last_trained = item["last_trained"]
        days_since = 99 if last_trained is None else int((today - last_trained).days)
        weekly_volume = float(item["weekly_volume"])
        sessions = len(item["session_dates"])

        if last_trained is None:
            score = _clamp(base_recovery + 16.0 + body_adj, 20.0, 100.0)
            reason = "No recent logged training for this muscle."
        else:
            workload_penalty = min(34.0, sessions * 7.0 + (weekly_volume / 1800.0) * 8.0)
            freshness_bonus = min(24.0, days_since * 4.8)
            soreness_penalty = soreness * 2.2
            acute_penalty = 0.0
            if days_since <= 0:
                acute_penalty = 16.0
            elif days_since == 1:
                acute_penalty = 10.0
            elif days_since == 2:
                acute_penalty = 6.0

            score = _clamp(base_recovery + freshness_bonus - workload_penalty - soreness_penalty - acute_penalty + body_adj, 5.0, 100.0)
            reason = f"{days_since}d since trained, weekly volume {int(weekly_volume):,}, soreness {soreness:.1f}/10."

        status = _status_for_score(score)
        muscle_output[muscle] = {
            "muscle": muscle,
            "recovery_pct": int(round(score)),
            "status": status,
            "reason": reason,
            "recommended_action": _action_for_status(status),
            "weekly_volume": int(round(weekly_volume)),
            "days_since_last_trained": None if days_since == 99 else days_since,
            "last_trained": None if last_trained is None else str(last_trained.date()),
        }

    ordered = sorted(muscle_output.values(), key=lambda x: x["recovery_pct"], reverse=True)
    top_ready = [m for m in ordered if m["status"] in {"Ready", "Moderate"}][:3]
    top_fatigued = [m for m in reversed(ordered) if m["status"] in {"Fatigued", "Recover"}][:3]

    focus = ", ".join([m["muscle"].title() for m in top_ready[:2]]) if top_ready else "Mobility + light cardio"
    avoid = [m["muscle"] for m in top_fatigued if m["status"] == "Recover"]

    if base_recovery >= 80 and len(avoid) == 0:
        train_mode = "train heavy"
    elif base_recovery < 55 or len(top_fatigued) >= 3:
        train_mode = "reduce volume"
    elif len(avoid) > 0:
        train_mode = "train normal"
    else:
        train_mode = "train normal"

    if len(avoid) > 0:
        coach_action = f"{train_mode}; avoid {', '.join(m.title() for m in avoid[:3])}; focus on {focus}."
    else:
        coach_action = f"{train_mode}; focus on {focus}."

    return {
        "muscles": muscle_output,
        "top_ready": top_ready,
        "top_fatigued": top_fatigued,
        "recommended_focus": focus,
        "avoid_muscles": avoid,
        "train_mode": train_mode,
        "coach_action": coach_action,
        "fallback_message": "Recovery recommendations are best with consistent workout + recovery logging.",
    }


def get_recovery_for_muscle(snapshot: Dict, muscle_name: str) -> Optional[Dict]:
    canonical = normalize_muscle_name(muscle_name)
    if not canonical:
        return None
    muscles = (snapshot or {}).get("muscles", {})
    return muscles.get(canonical)


def get_recovery_for_muscle_list(snapshot: Dict, muscle_names: List[str]) -> List[Dict]:
    seen = set()
    result: List[Dict] = []
    for name in muscle_names or []:
        item = get_recovery_for_muscle(snapshot, str(name))
        if not item:
            continue
        key = item.get("muscle")
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result