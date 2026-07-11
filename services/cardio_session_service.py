from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from services.supabase_service import connect_supabase
from services.workout_save_service import (
    get_cardio_sessions as get_cardio_sessions_core,
    save_cardio_session as save_cardio_session_core,
)


SPORT_TYPES = {
    "pickleball",
    "tennis",
    "basketball",
    "soccer",
    "golf",
    "other sport",
}


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


def _to_timestamp(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def _normalize_activity_type(activity_type: str) -> str:
    text = _to_text(activity_type, "Other Cardio").strip().lower()
    mapping = {
        "outdoor cycling": "Outdoor Cycling",
        "cycling": "Outdoor Cycling",
        "stationary bike": "Stationary Bike",
        "bike": "Stationary Bike",
        "other sport": "Other Sport",
        "other cardio": "Other Cardio",
    }
    if text in mapping:
        return mapping[text]
    if not text:
        return "Other Cardio"
    return " ".join([w.capitalize() for w in text.split()])


def _setup_warning() -> str:
    return "Supabase table public.cardio_sessions is not available. Run supabase/cardio_sessions_schema.sql"


def _is_missing_table_error(message: str) -> bool:
    text = _to_text(message).lower()
    return "cardio_sessions" in text and (
        "does not exist" in text
        or "relation" in text
        or "undefined" in text
        or "42p01" in text
    )


@st.cache_data(ttl=60)
def get_cardio_sessions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    activity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    client, conn_err = connect_supabase()
    normalized_type = _normalize_activity_type(activity_type) if activity_type else None

    if conn_err or client is None:
        core_rows, core_error, core_warning = get_cardio_sessions_core(days=90, activity_type=normalized_type)
        return {
            "ok": False,
            "rows": list(core_rows or []),
            "error": _to_text(conn_err, _to_text(core_error, "Cloud unavailable")),
            "setup_warning": _to_text(core_warning),
            "source": "csv_fallback",
            "count": int(len(core_rows or [])),
        }

    try:
        query = client.table("cardio_sessions").select("*")
        if date_from:
            query = query.gte("activity_date", str(date_from))
        if date_to:
            query = query.lte("activity_date", str(date_to))
        if normalized_type and normalized_type.lower() not in {"", "all"}:
            query = query.eq("activity_type", normalized_type)
        query = query.order("activity_date", desc=True).order("created_at", desc=True)
        if int(limit) > 0:
            start = max(0, int(offset))
            end = start + max(1, int(limit)) - 1
            query = query.range(start, end)
        response = query.execute()
        return {
            "ok": True,
            "rows": list(response.data or []),
            "error": "",
            "setup_warning": "",
            "source": "cloud",
            "count": int(len(response.data or [])),
        }
    except Exception as exc:
        err_txt = str(exc)
        core_rows, core_error, core_warning = get_cardio_sessions_core(days=90, activity_type=normalized_type)
        warning = _setup_warning() if _is_missing_table_error(err_txt) else _to_text(core_warning)
        return {
            "ok": False,
            "rows": list(core_rows or []),
            "error": err_txt if err_txt else _to_text(core_error, "Cardio read failed"),
            "setup_warning": warning,
            "source": "csv_fallback",
            "count": int(len(core_rows or [])),
        }


def save_cardio_session(cardio_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(cardio_data or {})
    payload["activity_type"] = _normalize_activity_type(_to_text(payload.get("activity_type", "Other Cardio")))
    if not _to_text(payload.get("category", "")).strip():
        payload["category"] = "sport" if payload["activity_type"].strip().lower() in SPORT_TYPES else "cardio"

    result = save_cardio_session_core(payload)
    ok = bool(result.get("ok")) and int(result.get("verified_rows", 0)) > 0
    if ok:
        get_cardio_sessions.clear()

    return {
        "ok": bool(result.get("ok")),
        "verified": bool(ok),
        "row": dict(payload),
        "session_id": _to_text(result.get("session_id")),
        "error": _to_text(result.get("cloud_error")),
        "setup_warning": _to_text(result.get("setup_warning")),
        "status": _to_text(result.get("status")),
        "duplicates_skipped": int(result.get("duplicates_skipped", 0) or 0),
        "verified_rows": int(result.get("verified_rows", 0) or 0),
        "csv_backup_ok": bool(result.get("csv_backup_ok", False)),
        "raw": result,
    }


def verify_cardio_session(
    workout_session_id: str,
    activity_type: str,
    activity_date: str,
) -> Dict[str, Any]:
    client, conn_err = connect_supabase()
    normalized_type = _normalize_activity_type(activity_type)

    if conn_err or client is None:
        return {
            "ok": False,
            "verified": False,
            "rows": [],
            "error": _to_text(conn_err, "Cloud unavailable"),
            "setup_warning": "",
        }

    try:
        response = (
            client.table("cardio_sessions")
            .select("*")
            .eq("workout_session_id", _to_text(workout_session_id).strip())
            .eq("activity_type", normalized_type)
            .eq("activity_date", _to_text(activity_date, str(date.today())).strip())
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        return {
            "ok": True,
            "verified": bool(rows),
            "rows": rows,
            "error": "",
            "setup_warning": "",
        }
    except Exception as exc:
        err_txt = str(exc)
        return {
            "ok": False,
            "verified": False,
            "rows": [],
            "error": err_txt,
            "setup_warning": _setup_warning() if _is_missing_table_error(err_txt) else "",
        }


def update_cardio_session(cardio_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    client, conn_err = connect_supabase()
    if conn_err or client is None:
        return {
            "ok": False,
            "row": {},
            "error": _to_text(conn_err, "Cloud unavailable"),
            "setup_warning": "",
        }

    payload = dict(updates or {})
    if "activity_type" in payload:
        payload["activity_type"] = _normalize_activity_type(_to_text(payload.get("activity_type")))

    try:
        response = (
            client.table("cardio_sessions")
            .update(payload)
            .eq("id", int(cardio_id))
            .execute()
        )
        rows = list(response.data or [])
        if rows:
            get_cardio_sessions.clear()
        return {
            "ok": bool(rows),
            "row": rows[0] if rows else {},
            "error": "" if rows else "No row updated",
            "setup_warning": "",
        }
    except Exception as exc:
        err_txt = str(exc)
        return {
            "ok": False,
            "row": {},
            "error": err_txt,
            "setup_warning": _setup_warning() if _is_missing_table_error(err_txt) else "",
        }


def match_apple_workout(cardio_session: Dict[str, Any], apple_workouts: Any) -> Dict[str, Any]:
    if apple_workouts is None:
        return {"ok": False, "matched": False, "reason": "No Apple workouts supplied", "candidate": None, "candidates": []}

    if isinstance(apple_workouts, pd.DataFrame):
        df = apple_workouts.copy()
    else:
        df = pd.DataFrame(list(apple_workouts or []))

    if df.empty:
        return {"ok": True, "matched": False, "reason": "No Apple sessions available", "candidate": None, "candidates": []}

    activity_type = _normalize_activity_type(_to_text((cardio_session or {}).get("activity_type", "Other Cardio")))
    date_value = _to_text((cardio_session or {}).get("activity_date", "")).strip()
    start_time = _to_timestamp((cardio_session or {}).get("start_time"))
    duration = _to_float((cardio_session or {}).get("duration_minutes", 0.0), 0.0)
    cardio_distance = _to_float((cardio_session or {}).get("distance_value", 0.0), 0.0)

    if "workout_type" not in df.columns:
        df["workout_type"] = ""
    if "start_time" not in df.columns:
        df["start_time"] = pd.NaT
    if "duration_minutes" not in df.columns:
        df["duration_minutes"] = 0.0
    if "total_distance_miles" not in df.columns:
        df["total_distance_miles"] = 0.0

    df["workout_type"] = df["workout_type"].astype(str)
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(0)
    df["total_distance_miles"] = pd.to_numeric(df["total_distance_miles"], errors="coerce").fillna(0)

    if date_value:
        target_date = pd.to_datetime(date_value, errors="coerce").date()
        df = df[df["start_time"].dt.date == target_date]

    if df.empty:
        return {"ok": True, "matched": False, "reason": "No Apple sessions for the selected date", "candidate": None, "candidates": []}

    normalized_workout_type = df["workout_type"].str.strip().str.lower()
    type_match = normalized_workout_type.eq(activity_type.lower())
    if not type_match.any() and activity_type in {"Outdoor Cycling", "Stationary Bike"}:
        type_match = normalized_workout_type.eq("cycling")
    df = df[type_match] if type_match.any() else df

    if start_time is not pd.NaT and not pd.isna(start_time):
        df["start_diff_hours"] = (df["start_time"] - start_time).abs().dt.total_seconds().div(3600.0)
        df = df[df["start_diff_hours"] <= 3.0]
    else:
        df["start_diff_hours"] = 0.0

    if duration > 0:
        df["duration_ratio"] = ((df["duration_minutes"] - duration).abs() / duration).fillna(99)
        df = df[df["duration_ratio"] <= 0.30]
    else:
        df["duration_ratio"] = 0.0

    if cardio_distance > 0 and "total_distance_miles" in df.columns:
        target_miles = cardio_distance
        df["distance_ratio"] = ((df["total_distance_miles"] - target_miles).abs() / max(target_miles, 0.1)).fillna(99)
    else:
        df["distance_ratio"] = 0.0

    if df.empty:
        return {"ok": True, "matched": False, "reason": "No Apple session met match criteria", "candidate": None, "candidates": []}

    df = df.sort_values(["duration_ratio", "start_diff_hours", "distance_ratio"], ascending=[True, True, True])
    candidates = df.head(10).to_dict("records")
    candidate = candidates[0] if candidates else None

    return {
        "ok": True,
        "matched": bool(candidate),
        "reason": "Matched by activity/date/start-window/duration tolerance",
        "candidate": candidate,
        "candidates": candidates,
    }
