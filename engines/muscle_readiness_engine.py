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
    "forearms",
    "core",
    "glutes",
    "quads",
    "hamstrings",
    "calves",
]


MUSCLE_ALIASES = {
    "chest": ["chest", "pec", "pectoral"],
    "back": ["back", "lat", "rhomboid", "trap", "trapezius", "erector"],
    "shoulders": ["shoulder", "deltoid", "rear delt", "front delt", "lateral delt"],
    "biceps": ["bicep", "biceps", "brachialis"],
    "triceps": ["tricep", "triceps"],
    "forearms": ["forearm", "brachioradialis", "wrist"],
    "core": ["core", "abs", "abdominal", "oblique", "transverse"],
    "glutes": ["glute", "glutes", "abductor"],
    "quads": ["quad", "quadriceps", "quadricep"],
    "hamstrings": ["hamstring"],
    "calves": ["calf", "calves", "soleus", "gastrocnemius"],
}


STATUS_COLOR = {
    "Green": "#22c55e",
    "Yellow": "#facc15",
    "Orange": "#f97316",
    "Red": "#ef4444",
}


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def normalize_muscle_name(name: str) -> Optional[str]:
    text = str(name or "").strip().lower()
    if not text:
        return None
    for canonical, aliases in MUSCLE_ALIASES.items():
        if any(token in text for token in aliases):
            return canonical
    return None


def _status_from_percent(value: float) -> str:
    if value >= 78:
        return "Green"
    if value >= 62:
        return "Yellow"
    if value >= 42:
        return "Orange"
    return "Red"


def _status_label(status: str) -> str:
    return {
        "Green": "Ready",
        "Yellow": "Moderate",
        "Orange": "Recovering",
        "Red": "Fatigued",
    }.get(status, "Moderate")


def _default_action(status: str) -> str:
    if status == "Green":
        return "Train normally or heavy with clean form and full range."
    if status == "Yellow":
        return "Train normally with controlled volume and strict execution."
    if status == "Orange":
        return "Keep load moderate and reduce total volume by 20-30%."
    return "Avoid heavy loading and prioritize recovery or alternate focus."


def _extract_profile_muscles(profile: Dict) -> Set[str]:
    candidates: List[str] = []
    candidates.extend(profile.get("primary_muscles", []) or [])
    candidates.extend(profile.get("secondary_muscles", []) or [])
    candidates.extend(profile.get("stabilizers", []) or [])
    if profile.get("muscle_group"):
        candidates.extend(str(profile.get("muscle_group")).replace("+", " ").split())

    out: Set[str] = set()
    for item in candidates:
        canonical = normalize_muscle_name(str(item))
        if canonical:
            out.add(canonical)
    return out


def _resolve_body_feedback_score(log_df: pd.DataFrame) -> pd.Series:
    if log_df is None or log_df.empty:
        return pd.Series(dtype=float)
    if "body_feedback_score" in log_df.columns:
        return _to_num(log_df["body_feedback_score"]).fillna(0)
    if "pain_score" in log_df.columns:
        return _to_num(log_df["pain_score"]).fillna(0)
    if "pain" in log_df.columns:
        return _to_num(log_df["pain"]).fillna(0)
    return pd.Series([0] * len(log_df), index=log_df.index, dtype=float)


def _safe_recovery_inputs(recovery_df: pd.DataFrame) -> Dict[str, float]:
    if recovery_df is None or recovery_df.empty:
        return {"recovery_pct": 68.0, "soreness": 0.0}

    latest = recovery_df.iloc[-1]
    recovery_pct = float(_to_num(pd.Series([latest.get("recovery_pct", 68)])).fillna(68).iloc[0])
    soreness = float(_to_num(pd.Series([latest.get("muscle_soreness", 0)])).fillna(0).iloc[0])
    return {
        "recovery_pct": _clamp(recovery_pct, 0.0, 100.0),
        "soreness": _clamp(soreness, 0.0, 10.0),
    }


def _body_comp_adjustment(body_df: pd.DataFrame) -> float:
    if body_df is None or body_df.empty or "date" not in body_df.columns:
        return 0.0

    d = body_df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date")
    if d.empty:
        return 0.0

    weight = _to_num(d.get("body_weight_lbs", pd.Series(dtype=float))).dropna()
    body_fat = _to_num(d.get("body_fat_pct", pd.Series(dtype=float))).dropna()

    adjustment = 0.0
    if len(weight) >= 2:
        delta = float(weight.iloc[-1] - weight.iloc[0])
        if delta <= -2.0:
            adjustment -= 2.5
        elif abs(delta) < 1.0:
            adjustment += 0.8

    if len(body_fat) >= 2:
        bf_delta = float(body_fat.iloc[-1] - body_fat.iloc[0])
        if bf_delta <= -0.3:
            adjustment += 1.0
        elif bf_delta >= 0.5:
            adjustment -= 1.0

    return adjustment


def _recommended_exercises_for_muscle(muscle: str, intel: ExerciseIntelligence, limit: int = 5) -> List[str]:
    df = intel.get_library_dataframe()
    if df.empty or "exercise" not in df.columns:
        return []

    picks: List[str] = []
    for _, row in df.iterrows():
        ex_name = str(row.get("exercise", "")).strip()
        if not ex_name:
            continue
        profile = intel.get_profile(ex_name)
        muscles = _extract_profile_muscles(profile)
        if muscle in muscles:
            picks.append(ex_name)
        if len(picks) >= limit:
            break
    return picks


def build_muscle_readiness_snapshot(
    workout_log_df: pd.DataFrame,
    recovery_df: pd.DataFrame,
    body_df: Optional[pd.DataFrame] = None,
    manual_soreness: Optional[Dict[str, float]] = None,
) -> Dict:
    today = pd.Timestamp(datetime.now().date())
    base = _safe_recovery_inputs(recovery_df)
    base_recovery = float(base["recovery_pct"])
    global_soreness = float(base["soreness"])
    body_adj = _body_comp_adjustment(body_df if body_df is not None else pd.DataFrame())

    intel = ExerciseIntelligence()
    cache: Dict[str, Set[str]] = {}

    per_muscle = {
        muscle: {
            "weekly_volume": 0.0,
            "last_trained": None,
            "sessions": set(),
            "avg_body_feedback": 0.0,
            "feedback_count": 0,
        }
        for muscle in TARGET_MUSCLES
    }

    log_df = workout_log_df.copy() if workout_log_df is not None else pd.DataFrame()
    if not log_df.empty and "date" in log_df.columns and "exercise" in log_df.columns:
        log_df["date"] = pd.to_datetime(log_df["date"], errors="coerce")
        log_df = log_df.dropna(subset=["date"])
        log_df["volume"] = _to_num(log_df.get("volume", pd.Series(dtype=float))).fillna(0)
        feedback = _resolve_body_feedback_score(log_df)

        week_cut = today - pd.Timedelta(days=7)
        for idx, row in log_df.iterrows():
            ex_name = str(row.get("exercise", "")).strip()
            if not ex_name:
                continue

            if ex_name not in cache:
                profile = intel.get_profile(ex_name)
                cache[ex_name] = _extract_profile_muscles(profile)
            muscles = cache.get(ex_name, set())
            if not muscles:
                continue

            row_date = pd.Timestamp(row["date"]).normalize()
            volume = float(row.get("volume", 0.0) or 0.0)
            feedback_value = float(feedback.get(idx, 0.0)) if idx in feedback.index else 0.0

            for muscle in muscles:
                current = per_muscle[muscle]
                current["last_trained"] = row_date if current["last_trained"] is None else max(current["last_trained"], row_date)
                if row_date >= week_cut:
                    current["weekly_volume"] += max(0.0, volume)
                    current["sessions"].add(str(row_date.date()))
                current["avg_body_feedback"] += feedback_value
                current["feedback_count"] += 1

    rows = []
    for muscle in TARGET_MUSCLES:
        item = per_muscle[muscle]
        last_trained = item["last_trained"]
        days_since = 99 if last_trained is None else int((today - last_trained).days)
        weekly_volume = float(item["weekly_volume"])
        sessions = len(item["sessions"])

        avg_feedback = 0.0
        if item["feedback_count"] > 0:
            avg_feedback = item["avg_body_feedback"] / item["feedback_count"]

        soreness_override = None
        if manual_soreness and muscle in manual_soreness:
            try:
                soreness_override = float(manual_soreness[muscle])
            except Exception:
                soreness_override = None

        soreness_value = global_soreness if soreness_override is None else _clamp(soreness_override, 0.0, 10.0)

        if last_trained is None:
            score = _clamp(base_recovery + 14.0 + body_adj, 25.0, 100.0)
            reason = "No recent training logged for this muscle."
        else:
            freshness_bonus = min(24.0, days_since * 4.6)
            volume_penalty = min(30.0, sessions * 6.0 + (weekly_volume / 1700.0) * 8.0)
            soreness_penalty = soreness_value * 2.0
            feedback_penalty = avg_feedback * 2.0
            acute_penalty = 0.0
            if days_since <= 0:
                acute_penalty = 14.0
            elif days_since == 1:
                acute_penalty = 9.0
            elif days_since == 2:
                acute_penalty = 5.0

            score = _clamp(base_recovery + freshness_bonus - volume_penalty - soreness_penalty - feedback_penalty - acute_penalty + body_adj, 5.0, 100.0)
            reason = f"{days_since}d since trained, {int(weekly_volume):,} weekly volume, body feedback {avg_feedback:.1f}/10."

        status = _status_from_percent(score)
        recommended = _default_action(status)
        rec_exercises = _recommended_exercises_for_muscle(muscle, intel)
        if rec_exercises:
            ai_rec = f"{_status_label(status)} for {muscle.title()}. Suggested: {', '.join(rec_exercises[:3])}."
        else:
            ai_rec = f"{_status_label(status)} for {muscle.title()}. Use movement quality and moderate progression."

        rows.append(
            {
                "muscle": muscle,
                "readiness_percent": int(round(score)),
                "status": status,
                "status_label": _status_label(status),
                "status_color": STATUS_COLOR.get(status, "#facc15"),
                "last_trained": None if last_trained is None else str(last_trained.date()),
                "weekly_volume": int(round(weekly_volume)),
                "recommended_action": recommended,
                "reason": reason,
                "recommended_exercises": rec_exercises,
                "ai_recommendation": ai_rec,
            }
        )

    readiness_df = pd.DataFrame(rows)
    if readiness_df.empty:
        readiness_df = pd.DataFrame(
            [
                {
                    "muscle": m,
                    "readiness_percent": 60,
                    "status": "Yellow",
                    "status_label": "Moderate",
                    "status_color": STATUS_COLOR["Yellow"],
                    "last_trained": None,
                    "weekly_volume": 0,
                    "recommended_action": "Log training and recovery data to unlock precision guidance.",
                    "reason": "Missing training data.",
                    "recommended_exercises": [],
                    "ai_recommendation": "Train moderate with strict form.",
                }
                for m in TARGET_MUSCLES
            ]
        )

    sorted_rows = readiness_df.sort_values("readiness_percent", ascending=False)
    top_ready = sorted_rows.head(3).to_dict("records")
    top_fatigued = sorted_rows.sort_values("readiness_percent", ascending=True).head(3).to_dict("records")

    ready_names = [r["muscle"] for r in top_ready if r.get("status") in {"Green", "Yellow"}]
    red_names = [r["muscle"] for r in top_fatigued if r.get("status") == "Red"]

    if len(red_names) >= 2:
        recommended_workout = "Active recovery or upper-body/light accessory session"
    elif any(m in ready_names for m in ["back", "biceps", "forearms"]):
        recommended_workout = "Pull"
    elif any(m in ready_names for m in ["chest", "shoulders", "triceps"]):
        recommended_workout = "Push"
    elif any(m in ready_names for m in ["quads", "hamstrings", "glutes", "calves"]):
        recommended_workout = "Legs"
    else:
        recommended_workout = "Moderate full-body technique session"

    return {
        "rows": readiness_df,
        "muscles": {r["muscle"]: r for r in rows},
        "top_ready": top_ready,
        "top_fatigued": top_fatigued,
        "recommended_workout": recommended_workout,
        "fallback_message": "Add workout and recovery logs for sharper readiness predictions.",
    }


def get_readiness_for_muscle(snapshot: Dict, muscle_name: str) -> Optional[Dict]:
    canonical = normalize_muscle_name(muscle_name)
    if not canonical:
        return None
    return (snapshot or {}).get("muscles", {}).get(canonical)


def get_readiness_for_muscle_list(snapshot: Dict, muscle_names: List[str]) -> List[Dict]:
    out: List[Dict] = []
    seen: Set[str] = set()
    for name in muscle_names or []:
        item = get_readiness_for_muscle(snapshot, str(name))
        if not item:
            continue
        muscle = str(item.get("muscle", ""))
        if muscle in seen:
            continue
        seen.add(muscle)
        out.append(item)
    return out
