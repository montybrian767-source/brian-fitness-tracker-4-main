from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

from engines.muscle_readiness_engine import build_muscle_readiness_snapshot


@dataclass
class AICoachBrief:
    readiness_summary: str
    workout_intensity_recommendation: str
    nutrition_recommendation: str
    hydration_recommendation: str
    body_composition_insight: str
    recovery_warning: str
    next_best_action: str
    recovery_status: str
    training_recommendation: str
    nutrition_status: str
    body_trend: str
    weekly_coaching_notes: str
    muscle_recovery_focus: str
    avoid_muscles: str


def _safe_read(path: Path, columns: List[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _latest_recovery(recovery_df: pd.DataFrame) -> Dict:
    if recovery_df.empty:
        return {}
    row = recovery_df.iloc[-1].to_dict()
    row["recovery_pct"] = int(pd.to_numeric(pd.Series([row.get("recovery_pct", 0)]), errors="coerce").fillna(0).iloc[0])
    return row


def _today_focus(workouts_df: pd.DataFrame) -> str:
    if workouts_df.empty or "day" not in workouts_df.columns:
        return "Workout plan unavailable"
    today = date.today().strftime("%A")
    d = workouts_df[workouts_df["day"].astype(str) == today]
    if d.empty:
        return "Recovery / Rest"
    if "muscle_group" in d.columns and not d["muscle_group"].empty:
        return str(d.iloc[0].get("muscle_group", "Recovery / Rest"))
    return "Recovery / Rest"


def _body_trends(body_df: pd.DataFrame) -> Dict[str, str]:
    if body_df.empty:
        return {
            "latest_weight": "-",
            "body_fat_trend": "-",
            "muscle_mass_trend": "-",
            "summary": "No body data yet. Log body stats or import smart scale data.",
        }

    d = body_df.copy()
    d["date"] = pd.to_datetime(d.get("date"), errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date")
    if d.empty:
        return {
            "latest_weight": "-",
            "body_fat_trend": "-",
            "muscle_mass_trend": "-",
            "summary": "Body data dates invalid. Add new body entries.",
        }

    lw = _to_num(pd.Series([d.iloc[-1].get("body_weight_lbs")])).iloc[0]
    latest_weight = "-" if pd.isna(lw) else f"{lw:.1f} lbs"

    def trend(col: str, unit: str):
        s = _to_num(d.get(col, pd.Series(dtype=float))).dropna()
        if len(s) < 2:
            return "-", "stable"
        delta = float(s.iloc[-1] - s.iloc[0])
        if abs(delta) < 0.05:
            return f"0{unit}", "stable"
        return f"{delta:+.1f}{unit}", "up" if delta > 0 else "down"

    bf, bf_dir = trend("body_fat_pct", "%")
    mm, mm_dir = trend("muscle_mass_lbs", " lbs")

    bf_line = "Body fat stable" if bf_dir == "stable" else ("Body fat decreasing" if bf_dir == "down" else "Body fat increasing")
    mm_line = "muscle stable" if mm_dir == "stable" else ("muscle mass increasing" if mm_dir == "up" else "muscle mass decreasing")

    return {
        "latest_weight": latest_weight,
        "body_fat_trend": bf,
        "muscle_mass_trend": mm,
        "summary": f"{bf_line}; {mm_line}.",
    }


def _nutrition_status(nut_df: pd.DataFrame) -> Dict[str, str]:
    if nut_df.empty:
        return {
            "calories": "0",
            "protein": "0g",
            "water": "0 oz",
            "protein_progress": "No nutrition log yet",
            "hydration_progress": "No hydration log yet",
            "nutrition_recommendation": "Log meals today to unlock precise coaching.",
            "hydration_recommendation": "Start with 16-24 oz water this morning.",
            "nutrition_status": "Nutrition data missing",
        }

    today_s = str(date.today())
    d = nut_df[nut_df["date"].astype(str) == today_s].copy() if "date" in nut_df.columns else pd.DataFrame()

    cal = int(_to_num(d.get("calories", pd.Series(dtype=float))).fillna(0).sum()) if not d.empty else 0
    protein = int(_to_num(d.get("protein_g", pd.Series(dtype=float))).fillna(0).sum()) if not d.empty else 0
    water = int(_to_num(d.get("water_oz", pd.Series(dtype=float))).fillna(0).sum()) if not d.empty else 0

    protein_goal = 160
    water_goal = 100
    protein_delta = protein_goal - protein
    water_delta = water_goal - water

    protein_progress = (
        f"{protein}g / {protein_goal}g"
        if protein > 0
        else "No protein logged yet"
    )
    hydration_progress = (
        f"{water} oz / {water_goal} oz"
        if water > 0
        else "No hydration logged yet"
    )

    if protein_delta > 0:
        nut_rec = f"Protein is {protein_delta}g below goal. Add a protein-focused meal or shake."
        nut_status = "Below protein target"
    else:
        nut_rec = "Protein target reached. Keep meal timing consistent around training."
        nut_status = "Protein on track"

    if water_delta > 0:
        hyd_rec = f"Hydration is {water_delta} oz below target. Increase water intake steadily today."
    else:
        hyd_rec = "Hydration target reached. Maintain electrolyte balance if training hard."

    return {
        "calories": str(cal),
        "protein": f"{protein}g",
        "water": f"{water} oz",
        "protein_progress": protein_progress,
        "hydration_progress": hydration_progress,
        "nutrition_recommendation": nut_rec,
        "hydration_recommendation": hyd_rec,
        "nutrition_status": nut_status,
    }


def _supplement_completion(sup_df: pd.DataFrame) -> str:
    if sup_df.empty:
        return "No supplement log yet"

    today_s = str(date.today())
    today = sup_df[sup_df["date"].astype(str) == today_s] if "date" in sup_df.columns else pd.DataFrame()
    if today.empty:
        return "Supplements not logged today"

    row = today.iloc[-1]
    fields = [
        "creatine", "protein_powder", "multivitamin", "fish_oil",
        "pre_workout", "magnesium", "vitamin_d", "electrolytes",
    ]
    done = 0
    for f in fields:
        if str(row.get(f, "")).lower() in ["true", "1", "yes"]:
            done += 1
    return f"{done}/8 supplements completed today"


def _workout_metrics(log_df: pd.DataFrame) -> Dict[str, str]:
    if log_df.empty:
        return {
            "weekly_volume": "0",
            "session_count": "0",
            "prs": "No PR data yet",
            "intensity": "Light Session",
            "training_recommendation": "Log your first workout to unlock training guidance.",
            "recovery_warning": "",
            "weekly_notes": "No weekly training trend available yet.",
        }

    d = log_df.copy()
    d["date"] = pd.to_datetime(d.get("date"), errors="coerce")
    d = d.dropna(subset=["date"])
    for col in ["volume", "rpe", "pain", "pain_score", "body_feedback_score", "weight_lbs", "reps"]:
        d[col] = _to_num(d.get(col, pd.Series(dtype=float))).fillna(0)

    week_cut = pd.Timestamp.today() - pd.Timedelta(days=7)
    w = d[d["date"] >= week_cut]

    weekly_volume = int(w["volume"].sum()) if not w.empty else 0
    session_count = int(w["date"].dt.strftime("%Y-%m-%d").nunique()) if not w.empty else 0
    avg_rpe = float(w["rpe"].mean()) if not w.empty else 0.0
    if "body_feedback_score" in w.columns:
        avg_body_feedback = float(w["body_feedback_score"].mean()) if not w.empty else 0.0
    elif "pain_score" in w.columns:
        avg_body_feedback = float(w["pain_score"].mean()) if not w.empty else 0.0
    else:
        avg_body_feedback = float(w["pain"].mean()) if not w.empty else 0.0

    prs = "No PR data yet"
    if "exercise" in d.columns and not d.empty:
        pr_count = d.groupby("exercise")["weight_lbs"].max().dropna().shape[0]
        prs = f"{pr_count} exercises with PR history"

    if avg_body_feedback >= 4:
        intensity = "Recovery Day"
        train_rec = "Body feedback trend is elevated. Reduce load and prioritize movement quality and recovery."
        warning = "Readiness note: body feedback indicators are elevated."
    elif avg_rpe >= 8.5:
        intensity = "Light Session"
        train_rec = "Recent effort is high. Keep today moderate and extend rest between sets."
        warning = ""
    elif weekly_volume > 12000 and session_count >= 4:
        intensity = "Train Normal"
        train_rec = "Momentum is strong. Train as planned with controlled progression."
        warning = ""
    else:
        intensity = "Train Normal"
        train_rec = "Build consistency today with clean reps and full logging."
        warning = ""

    weekly_notes = f"Weekly volume: {weekly_volume:,} lbs across {session_count} sessions. Avg RPE {avg_rpe:.1f}."
    return {
        "weekly_volume": f"{weekly_volume:,}",
        "session_count": str(session_count),
        "prs": prs,
        "intensity": intensity,
        "training_recommendation": train_rec,
        "recovery_warning": warning,
        "weekly_notes": weekly_notes,
    }


def build_daily_brief(
    workouts_df: pd.DataFrame,
    recovery_df: pd.DataFrame,
    body_df: pd.DataFrame,
    nutrition_df: pd.DataFrame,
    supplements_df: pd.DataFrame,
    workout_log_df: pd.DataFrame,
) -> AICoachBrief:
    focus = _today_focus(workouts_df)
    recovery = _latest_recovery(recovery_df)
    body = _body_trends(body_df)
    nutrition = _nutrition_status(nutrition_df)
    supplements = _supplement_completion(supplements_df)
    workouts = _workout_metrics(workout_log_df)
    muscle_snapshot = build_muscle_readiness_snapshot(
        workout_log_df=workout_log_df,
        recovery_df=recovery_df,
        body_df=body_df,
    )

    top_ready = muscle_snapshot.get("top_ready", []) or []
    top_fatigued = muscle_snapshot.get("top_fatigued", []) or []
    focus = str(muscle_snapshot.get("recommended_workout", "Moderate full-body technique session"))
    avoid_list = [str(m.get("muscle", "")).title() for m in top_fatigued if str(m.get("status", "")) == "Red"]
    avoid_text = ", ".join(avoid_list[:3]) if avoid_list else "None"

    recovery_pct = int(recovery.get("recovery_pct", 0)) if recovery else 0
    recovery_status = recovery.get("recovery_status", workouts["intensity"]) if recovery else workouts["intensity"]
    recovery_rec = str(recovery.get("recommendation", "No recovery recommendation yet. Compute in Recovery Center."))

    if any(str(m.get("status", "")) == "Red" for m in top_fatigued[:2]):
        train_mode = "reduce volume"
    elif recovery_pct >= 85 and any(str(m.get("status", "")) == "Green" for m in top_ready[:3]):
        train_mode = "train heavy"
    elif any(str(m.get("status", "")) == "Green" for m in top_ready[:2]):
        train_mode = "train normal"
    else:
        train_mode = "train normal"

    readiness = (
        f"Today focus: {focus}. Recovery {recovery_pct}% ({recovery_status}). "
        f"Supplements: {supplements}."
    )

    if train_mode == "train heavy":
        muscle_guidance = f"Muscle readiness supports heavy work. Focus on {focus}."
    elif train_mode == "reduce volume":
        muscle_guidance = f"Legs or target muscles need additional recovery. Reduce volume today and focus on {focus}."
    else:
        muscle_guidance = f"Train normal with quality reps. Focus on {focus}."

    if avoid_list:
        muscle_guidance += f" Avoid: {avoid_text}."

    if top_ready:
        muscle_guidance += f" {str(top_ready[0].get('muscle', '')).title()} is fully recovered."
    if top_fatigued:
        low = top_fatigued[0]
        if str(low.get("status", "")) in {"Red", "Orange"}:
            muscle_guidance += f" {str(low.get('muscle', '')).title()} needs additional recovery."

    focus_lower = focus.lower()
    if "pull" in focus_lower:
        muscle_guidance += " Train Pull today."
    elif "push" in focus_lower:
        muscle_guidance += " Train Push today."
    elif "leg" in focus_lower:
        muscle_guidance += " Train Legs today."

    training_recommendation = f"{workouts['training_recommendation']} Recovery note: {recovery_rec}"
    if train_mode == "train heavy":
        training_recommendation = f"Train heavy today. {training_recommendation}"
    elif train_mode == "reduce volume":
        training_recommendation = f"Reduce volume today. {training_recommendation}"
    else:
        training_recommendation = f"Train normal today. {training_recommendation}"

    if avoid_list:
        training_recommendation += f" Avoid fatigued muscles: {avoid_text}."
    workout_intensity_recommendation = f"{muscle_guidance} {recovery_rec}"

    body_trend = f"Weight {body['latest_weight']} | BF trend {body['body_fat_trend']} | Muscle trend {body['muscle_mass_trend']}"

    next_best_action = ""
    if train_mode == "reduce volume":
        next_best_action = f"Scale back total sets and avoid {avoid_text if avoid_list else 'fatigued muscle groups'} today."
    elif recovery_status in ["Recovery Day", "Light Session"]:
        next_best_action = "Run a lighter session today, then prioritize hydration and sleep."
    elif "Below protein target" in nutrition["nutrition_status"]:
        next_best_action = "Finish your workout and close your protein gap with your next meal."
    elif "No nutrition" in nutrition["nutrition_status"]:
        next_best_action = "Log your first meal and hydration entry, then start your planned workout."
    else:
        next_best_action = "Train as planned and log every working set to sharpen tomorrow's coaching."

    weekly_notes = (
        f"{workouts['weekly_notes']} "
        f"PRs: {workouts['prs']}. "
        f"Nutrition today: {nutrition['protein_progress']}, {nutrition['hydration_progress']}. "
        f"Muscle readiness mode: {train_mode}; focus: {focus}."
    )

    return AICoachBrief(
        readiness_summary=readiness,
        workout_intensity_recommendation=workout_intensity_recommendation,
        nutrition_recommendation=nutrition["nutrition_recommendation"],
        hydration_recommendation=nutrition["hydration_recommendation"],
        body_composition_insight=body["summary"],
        recovery_warning=workouts["recovery_warning"],
        next_best_action=next_best_action,
        recovery_status=f"{recovery_pct}% - {recovery_status}" if recovery else "Recovery not logged",
        training_recommendation=workouts["training_recommendation"],
        nutrition_status=nutrition["nutrition_status"],
        body_trend=body_trend,
        weekly_coaching_notes=weekly_notes,
        muscle_recovery_focus=focus,
        avoid_muscles=avoid_text,
    )
