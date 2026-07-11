from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from services.supabase_service import connect_supabase


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
LOG_PATH = DATA_DIR / "workout_log.csv"
CARDIO_LOG_PATH = DATA_DIR / "cardio_sessions.csv"

LAST_SAVE_RESULT_KEY = "workout_save_service_last_result"

REQUIRED_FIELDS = [
    "workout_date",
    "day",
    "exercise",
    "set_number",
    "weight_lbs",
    "reps",
    "rpe",
    "body_feedback_score",
    "body_feedback_notes",
    "volume",
    "workout_session_id",
]

CSV_COLUMNS = [
    "date",
    "workout_date",
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
    "workout_session_id",
]

CARDIO_CSV_COLUMNS = [
    "created_at",
    "workout_session_id",
    "activity_date",
    "start_time",
    "end_time",
    "activity_type",
    "category",
    "duration_minutes",
    "distance_value",
    "distance_unit",
    "calories_burned",
    "average_heart_rate",
    "maximum_heart_rate",
    "average_pace",
    "average_speed",
    "incline_percent",
    "resistance_level",
    "laps",
    "pool_length",
    "pool_length_unit",
    "steps",
    "rpe",
    "notes",
    "source",
    "apple_workout_key",
    "verified",
]

CARDIO_DISTANCE_UNITS = {"miles", "kilometers", "meters", "yards"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return str(value)


def _supports_workout_session_id(client: Any) -> bool:
    try:
        client.table("workouts").select("workout_session_id").limit(1).execute()
        return True
    except Exception:
        return False


def _count_workouts(client: Any) -> int:
    response = client.table("workouts").select("*", count="exact", head=True).execute()
    return int(response.count or 0)


def _count_cardio_sessions(client: Any) -> int:
    response = client.table("cardio_sessions").select("*", count="exact", head=True).execute()
    return int(response.count or 0)


def _ensure_log_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        pd.DataFrame(columns=CSV_COLUMNS).to_csv(LOG_PATH, index=False)


def _ensure_cardio_log_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CARDIO_LOG_PATH.exists():
        pd.DataFrame(columns=CARDIO_CSV_COLUMNS).to_csv(CARDIO_LOG_PATH, index=False)


def _append_backup_rows(rows: List[Dict[str, Any]]) -> tuple[bool, str, int]:
    if not rows:
        return True, "", 0

    try:
        _ensure_log_file()
        try:
            old_df = pd.read_csv(LOG_PATH)
        except Exception:
            old_df = pd.DataFrame(columns=CSV_COLUMNS)

        new_df = pd.DataFrame([_to_csv_row(r) for r in rows])
        for col in CSV_COLUMNS:
            if col not in old_df.columns:
                old_df[col] = ""
            if col not in new_df.columns:
                new_df[col] = ""

        out = pd.concat([old_df[CSV_COLUMNS], new_df[CSV_COLUMNS]], ignore_index=True)
        out.to_csv(LOG_PATH, index=False)
        return True, "", int(len(new_df))
    except Exception as exc:
        return False, str(exc), 0


def _to_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": _to_text(row.get("workout_date", row.get("date", str(date.today()))), str(date.today())),
        "workout_date": _to_text(row.get("workout_date", row.get("date", str(date.today()))), str(date.today())),
        "day": _to_text(row.get("day", "")),
        "exercise": _to_text(row.get("exercise", "")),
        "set_number": _to_int(row.get("set_number", 1), 1),
        "weight_lbs": _to_float(row.get("weight_lbs", 0.0), 0.0),
        "reps": _to_int(row.get("reps", 0), 0),
        "rpe": _to_float(row.get("rpe", 0.0), 0.0),
        "pain": _to_int(row.get("body_feedback_score", row.get("pain", 0)), 0),
        "body_feedback_score": _to_int(row.get("body_feedback_score", row.get("pain", 0)), 0),
        "notes": _to_text(row.get("body_feedback_notes", row.get("notes", ""))),
        "body_feedback_notes": _to_text(row.get("body_feedback_notes", row.get("notes", ""))),
        "volume": _to_float(row.get("volume", 0.0), 0.0),
        "workout_session_id": _to_text(row.get("workout_session_id", "")),
    }


def _to_cardio_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "created_at": _to_text(row.get("created_at", datetime.now().isoformat())),
        "workout_session_id": _to_text(row.get("workout_session_id", "")),
        "activity_date": _to_text(row.get("activity_date", str(date.today()))),
        "start_time": _to_text(row.get("start_time", "")),
        "end_time": _to_text(row.get("end_time", "")),
        "activity_type": _to_text(row.get("activity_type", "Other Cardio")),
        "category": _to_text(row.get("category", "cardio"), "cardio"),
        "duration_minutes": _to_float(row.get("duration_minutes", 0.0), 0.0),
        "distance_value": _to_float(row.get("distance_value", 0.0), 0.0),
        "distance_unit": _to_text(row.get("distance_unit", "")),
        "calories_burned": _to_float(row.get("calories_burned", 0.0), 0.0),
        "average_heart_rate": _to_float(row.get("average_heart_rate", 0.0), 0.0),
        "maximum_heart_rate": _to_float(row.get("maximum_heart_rate", 0.0), 0.0),
        "average_pace": _to_text(row.get("average_pace", "")),
        "average_speed": _to_float(row.get("average_speed", 0.0), 0.0),
        "incline_percent": _to_float(row.get("incline_percent", 0.0), 0.0),
        "resistance_level": _to_float(row.get("resistance_level", 0.0), 0.0),
        "laps": _to_float(row.get("laps", 0.0), 0.0),
        "pool_length": _to_float(row.get("pool_length", 0.0), 0.0),
        "pool_length_unit": _to_text(row.get("pool_length_unit", "")),
        "steps": _to_float(row.get("steps", 0.0), 0.0),
        "rpe": _to_float(row.get("rpe", 0.0), 0.0),
        "notes": _to_text(row.get("notes", "")),
        "source": _to_text(row.get("source", "Brian Fit"), "Brian Fit"),
        "apple_workout_key": _to_text(row.get("apple_workout_key", "")),
        "verified": bool(row.get("verified", False)),
    }


def _append_cardio_backup_rows(rows: List[Dict[str, Any]]) -> tuple[bool, str, int]:
    if not rows:
        return True, "", 0

    try:
        _ensure_cardio_log_file()
        try:
            old_df = pd.read_csv(CARDIO_LOG_PATH)
        except Exception:
            old_df = pd.DataFrame(columns=CARDIO_CSV_COLUMNS)

        new_df = pd.DataFrame([_to_cardio_csv_row(r) for r in rows])
        for col in CARDIO_CSV_COLUMNS:
            if col not in old_df.columns:
                old_df[col] = ""
            if col not in new_df.columns:
                new_df[col] = ""

        out = pd.concat([old_df[CARDIO_CSV_COLUMNS], new_df[CARDIO_CSV_COLUMNS]], ignore_index=True)
        out.to_csv(CARDIO_LOG_PATH, index=False)
        return True, "", int(len(new_df))
    except Exception as exc:
        return False, str(exc), 0


def build_workout_session_id() -> str:
    return f"ws_{date.today().strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S%f')}"


def validate_workout_set(set_data: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []

    workout_date = _to_text(set_data.get("workout_date", set_data.get("date", str(date.today()))), str(date.today())).strip()
    day = _to_text(set_data.get("day", "")).strip()
    exercise = _to_text(set_data.get("exercise", "")).strip()
    set_number = _to_int(set_data.get("set_number", 1), 1)
    weight_lbs = _to_float(set_data.get("weight_lbs", set_data.get("weight", 0.0)), 0.0)
    reps = _to_int(set_data.get("reps", 0), 0)
    rpe = _to_float(set_data.get("rpe", 0.0), 0.0)
    body_feedback_score = _to_int(set_data.get("body_feedback_score", set_data.get("pain", 0)), 0)
    body_feedback_notes = _to_text(set_data.get("body_feedback_notes", set_data.get("notes", ""))).strip()
    workout_session_id = _to_text(set_data.get("workout_session_id", "")).strip()

    if not workout_date:
        errors.append("workout_date is required")
    if not day:
        errors.append("day is required")
    if not exercise:
        errors.append("exercise is required")
    if set_number <= 0:
        errors.append("set_number must be >= 1")
    if weight_lbs < 0:
        errors.append("weight_lbs must be >= 0")
    if reps < 0:
        errors.append("reps must be >= 0")
    if rpe < 0 or rpe > 10:
        errors.append("rpe must be between 0 and 10")
    if body_feedback_score < 0 or body_feedback_score > 10:
        errors.append("body_feedback_score must be between 0 and 10")

    normalized = {
        "workout_date": workout_date,
        "day": day,
        "exercise": exercise,
        "set_number": int(set_number),
        "weight_lbs": float(weight_lbs),
        "reps": int(reps),
        "rpe": float(rpe),
        "body_feedback_score": int(body_feedback_score),
        "body_feedback_notes": body_feedback_notes,
        "volume": float(weight_lbs * reps),
        "workout_session_id": workout_session_id,
    }

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "normalized": normalized,
    }


def _is_duplicate(client: Any, row: Dict[str, Any], session_id_supported: bool) -> bool:
    q = (
        client.table("workouts")
        .select("id")
        .eq("workout_date", row["workout_date"])
        .eq("day", row["day"])
        .eq("exercise", row["exercise"])
        .eq("set_number", row["set_number"])
    )
    if session_id_supported and row.get("workout_session_id"):
        q = q.eq("workout_session_id", row["workout_session_id"])
    return bool((q.limit(1).execute().data or []))


def _verify_inserted(client: Any, row: Dict[str, Any], session_id_supported: bool) -> bool:
    q = (
        client.table("workouts")
        .select("id")
        .eq("workout_date", row["workout_date"])
        .eq("day", row["day"])
        .eq("exercise", row["exercise"])
        .eq("set_number", row["set_number"])
    )
    if session_id_supported and row.get("workout_session_id"):
        q = q.eq("workout_session_id", row["workout_session_id"])
    return bool((q.limit(1).execute().data or []))


def _supports_cardio_sessions_table(client: Any) -> bool:
    try:
        client.table("cardio_sessions").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _is_missing_cardio_table_error(message: str) -> bool:
    text = _to_text(message).lower()
    return "cardio_sessions" in text and (
        "does not exist" in text
        or "relation" in text
        or "undefined" in text
        or "42p01" in text
    )


def validate_cardio_session(cardio_data: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []

    activity_date = _to_text(cardio_data.get("activity_date", cardio_data.get("date", str(date.today()))), str(date.today())).strip()
    activity_type = _to_text(cardio_data.get("activity_type", "")).strip()
    category = _to_text(cardio_data.get("category", "cardio"), "cardio").strip().lower() or "cardio"
    duration_minutes = _to_float(cardio_data.get("duration_minutes", 0.0), 0.0)
    rpe = _to_float(cardio_data.get("rpe", 0.0), 0.0)
    distance_value = _to_float(cardio_data.get("distance_value", 0.0), 0.0)
    distance_unit = _to_text(cardio_data.get("distance_unit", "")).strip().lower()
    calories_burned = _to_float(cardio_data.get("calories_burned", 0.0), 0.0)
    average_heart_rate = _to_float(cardio_data.get("average_heart_rate", 0.0), 0.0)
    maximum_heart_rate = _to_float(cardio_data.get("maximum_heart_rate", 0.0), 0.0)
    average_pace = _to_text(cardio_data.get("average_pace", "")).strip()
    average_speed = _to_float(cardio_data.get("average_speed", 0.0), 0.0)
    incline_percent = _to_float(cardio_data.get("incline_percent", 0.0), 0.0)
    resistance_level = _to_float(cardio_data.get("resistance_level", 0.0), 0.0)
    laps = _to_float(cardio_data.get("laps", 0.0), 0.0)
    pool_length = _to_float(cardio_data.get("pool_length", 0.0), 0.0)
    pool_length_unit = _to_text(cardio_data.get("pool_length_unit", "")).strip().lower()
    steps = _to_float(cardio_data.get("steps", 0.0), 0.0)
    notes = _to_text(cardio_data.get("notes", "")).strip()
    source = _to_text(cardio_data.get("source", "Brian Fit"), "Brian Fit").strip() or "Brian Fit"
    apple_workout_key = _to_text(cardio_data.get("apple_workout_key", "")).strip()
    workout_session_id = _to_text(cardio_data.get("workout_session_id", "")).strip()
    start_time = _to_text(cardio_data.get("start_time", "")).strip() or None
    end_time = _to_text(cardio_data.get("end_time", "")).strip() or None

    if not activity_date:
        errors.append("activity_date is required")
    if not activity_type:
        errors.append("activity_type is required")
    if duration_minutes <= 0:
        errors.append("duration_minutes must be > 0")
    if rpe <= 0 or rpe > 10:
        errors.append("rpe must be between 1 and 10")
    if distance_value > 0 and distance_unit and distance_unit not in CARDIO_DISTANCE_UNITS:
        errors.append("distance_unit must be miles, kilometers, meters, or yards")
    if category not in {"cardio", "sport"}:
        errors.append("category must be cardio or sport")
    if any(v < 0 for v in [distance_value, calories_burned, average_heart_rate, maximum_heart_rate, average_speed, incline_percent, resistance_level, laps, pool_length, steps]):
        errors.append("numeric cardio fields must be >= 0")

    normalized = {
        "created_at": datetime.now().isoformat(),
        "workout_session_id": workout_session_id,
        "activity_date": activity_date,
        "start_time": start_time,
        "end_time": end_time,
        "activity_type": activity_type,
        "category": category,
        "duration_minutes": float(duration_minutes),
        "distance_value": float(distance_value) if distance_value > 0 else None,
        "distance_unit": distance_unit if distance_value > 0 and distance_unit else None,
        "calories_burned": float(calories_burned) if calories_burned > 0 else None,
        "average_heart_rate": float(average_heart_rate) if average_heart_rate > 0 else None,
        "maximum_heart_rate": float(maximum_heart_rate) if maximum_heart_rate > 0 else None,
        "average_pace": average_pace if average_pace else None,
        "average_speed": float(average_speed) if average_speed > 0 else None,
        "incline_percent": float(incline_percent) if incline_percent > 0 else None,
        "resistance_level": float(resistance_level) if resistance_level > 0 else None,
        "laps": float(laps) if laps > 0 else None,
        "pool_length": float(pool_length) if pool_length > 0 else None,
        "pool_length_unit": pool_length_unit if pool_length > 0 and pool_length_unit else None,
        "steps": float(steps) if steps > 0 else None,
        "rpe": float(rpe),
        "notes": notes,
        "source": source,
        "apple_workout_key": apple_workout_key or None,
        "verified": False,
    }

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "normalized": normalized,
    }


def _is_cardio_duplicate(client: Any, row: Dict[str, Any]) -> bool:
    query = (
        client.table("cardio_sessions")
        .select("id")
        .eq("workout_session_id", row.get("workout_session_id", ""))
        .eq("activity_type", row["activity_type"])
        .eq("activity_date", row["activity_date"])
        .limit(1)
    )
    response = query.execute()
    return bool(response.data or [])


def _verify_cardio_inserted(client: Any, row: Dict[str, Any]) -> bool:
    query = (
        client.table("cardio_sessions")
        .select("id")
        .eq("workout_session_id", row.get("workout_session_id", ""))
        .eq("activity_type", row["activity_type"])
        .eq("activity_date", row["activity_date"])
        .limit(1)
    )
    response = query.execute()
    return bool(response.data or [])


def _cardio_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "workout_session_id",
        "activity_date",
        "start_time",
        "end_time",
        "activity_type",
        "category",
        "duration_minutes",
        "distance_value",
        "distance_unit",
        "calories_burned",
        "average_heart_rate",
        "maximum_heart_rate",
        "average_pace",
        "average_speed",
        "incline_percent",
        "resistance_level",
        "laps",
        "pool_length",
        "pool_length_unit",
        "steps",
        "rpe",
        "notes",
        "source",
        "apple_workout_key",
        "verified",
    ]
    payload = {k: row.get(k) for k in keys}
    return payload


def _load_cardio_local_rows(days: Optional[int] = 90, activity_type: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        _ensure_cardio_log_file()
        df = pd.read_csv(CARDIO_LOG_PATH)
    except Exception:
        return []

    if df.empty:
        return []

    if "activity_date" in df.columns:
        df["activity_date"] = pd.to_datetime(df["activity_date"], errors="coerce").dt.date.astype(str)
    else:
        df["activity_date"] = ""

    if isinstance(days, int) and days > 0:
        cutoff = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(days))).date().isoformat()
        df = df[df["activity_date"].astype(str) >= cutoff]

    if activity_type and str(activity_type).strip().lower() not in {"all", ""}:
        df = df[df.get("activity_type", "").astype(str).str.lower() == str(activity_type).strip().lower()]

    for col in CARDIO_CSV_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[CARDIO_CSV_COLUMNS].to_dict("records")


def _set_last_save_result(result: Dict[str, Any]) -> Dict[str, Any]:
    st.session_state[LAST_SAVE_RESULT_KEY] = result
    return result


def get_last_save_result() -> Dict[str, Any]:
    value = st.session_state.get(LAST_SAVE_RESULT_KEY, {})
    return value if isinstance(value, dict) else {}


def save_completed_set(set_data: Dict[str, Any]) -> Dict[str, Any]:
    return save_workout_session({}, [set_data])


def save_workout_session(session_data: Dict[str, Any], completed_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
    session_data = session_data or {}
    completed_sets = completed_sets or []

    if not completed_sets:
        return _set_last_save_result(
            {
                "ok": True,
                "status": "no_sets",
                "cloud": "Supabase",
                "history_source": "none",
                "session_id": _to_text(session_data.get("session_id", "")),
                "session_id_supported": False,
                "sets_attempted": 0,
                "sets_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "exercises_saved": 0,
                "cloud_error": "",
                "csv_backup_ok": True,
                "csv_backup_error": "",
                "csv_rows_written": 0,
                "errors": [],
                "already_saved": False,
            }
        )

    normalized_rows: List[Dict[str, Any]] = []
    validation_errors: List[Dict[str, Any]] = []
    incoming_session_id = _to_text(session_data.get("session_id", session_data.get("workout_session_id", ""))).strip()
    if not incoming_session_id:
        incoming_session_id = build_workout_session_id()

    for i, raw in enumerate(completed_sets):
        merged = dict(raw or {})
        if not _to_text(merged.get("workout_session_id", "")).strip():
            merged["workout_session_id"] = incoming_session_id
        result = validate_workout_set(merged)
        if not result["ok"]:
            validation_errors.append({"index": i, "errors": result["errors"]})
            continue
        normalized_rows.append(result["normalized"])

    if validation_errors:
        return _set_last_save_result(
            {
                "ok": False,
                "status": "validation_error",
                "cloud": "Supabase",
                "history_source": "none",
                "session_id": incoming_session_id,
                "session_id_supported": False,
                "sets_attempted": len(completed_sets),
                "sets_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "exercises_saved": 0,
                "cloud_error": "Validation failed",
                "csv_backup_ok": False,
                "csv_backup_error": "Validation failed before persistence",
                "csv_rows_written": 0,
                "errors": validation_errors,
                "already_saved": False,
            }
        )

    client, conn_err = connect_supabase()
    if conn_err or client is None:
        csv_ok, csv_error, csv_rows = _append_backup_rows(normalized_rows)
        return _set_last_save_result(
            {
                "ok": False,
                "status": "backup_only",
                "cloud": "Supabase",
                "history_source": "Local CSV Backup",
                "session_id": incoming_session_id,
                "session_id_supported": False,
                "sets_attempted": len(normalized_rows),
                "sets_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "exercises_saved": len({str(r.get('exercise', '')).strip().lower() for r in normalized_rows if str(r.get('exercise', '')).strip()}),
                "cloud_error": _to_text(conn_err, "Cloud unavailable"),
                "csv_backup_ok": bool(csv_ok),
                "csv_backup_error": _to_text(csv_error),
                "csv_rows_written": int(csv_rows),
                "errors": [{"index": -1, "error": _to_text(conn_err, "Cloud unavailable")}],
                "already_saved": False,
            }
        )

    session_id_supported = _supports_workout_session_id(client)
    before_count = 0
    try:
        before_count = _count_workouts(client)
    except Exception:
        before_count = 0

    inserted_rows: List[Dict[str, Any]] = []
    backup_rows: List[Dict[str, Any]] = []
    cloud_errors: List[Dict[str, Any]] = []
    duplicates_skipped = 0
    verified_rows = 0

    for idx, row in enumerate(normalized_rows):
        try:
            if _is_duplicate(client, row, session_id_supported):
                duplicates_skipped += 1
                continue

            payload = {
                "workout_date": row["workout_date"],
                "day": row["day"],
                "exercise": row["exercise"],
                "set_number": row["set_number"],
                "weight_lbs": row["weight_lbs"],
                "reps": row["reps"],
                "rpe": row["rpe"],
                "body_feedback_score": row["body_feedback_score"],
                "body_feedback_notes": row["body_feedback_notes"],
                "volume": row["volume"],
            }
            if session_id_supported and row.get("workout_session_id"):
                payload["workout_session_id"] = row["workout_session_id"]

            client.table("workouts").insert(payload).execute()

            if _verify_inserted(client, row, session_id_supported):
                verified_rows += 1
                inserted_rows.append(row)
                backup_rows.append(row)
            else:
                cloud_errors.append({"index": idx, "error": "Insert verification failed", "row": row})
        except Exception as exc:
            cloud_errors.append({"index": idx, "error": str(exc), "row": row})

    sets_inserted = len(inserted_rows)
    after_count = before_count
    try:
        after_count = _count_workouts(client)
    except Exception:
        pass

    if cloud_errors:
        # If cloud flow has errors, write any not-yet-backed-up rows to CSV as fallback.
        fallback_rows = []
        inserted_keys = {
            (r["workout_date"], r["day"], r["exercise"], r["set_number"], r.get("workout_session_id", ""))
            for r in backup_rows
        }
        for r in normalized_rows:
            key = (r["workout_date"], r["day"], r["exercise"], r["set_number"], r.get("workout_session_id", ""))
            if key not in inserted_keys:
                fallback_rows.append(r)
        csv_ok, csv_error, csv_rows = _append_backup_rows(fallback_rows)
        return _set_last_save_result(
            {
                "ok": False,
                "status": "partial_backup_only",
                "cloud": "Supabase",
                "history_source": "Local CSV Backup",
                "session_id": incoming_session_id,
                "session_id_supported": bool(session_id_supported),
                "sets_attempted": len(normalized_rows),
                "sets_inserted": int(sets_inserted),
                "duplicates_skipped": int(duplicates_skipped),
                "verified_rows": int(verified_rows),
                "exercises_saved": len({str(r.get('exercise', '')).strip().lower() for r in normalized_rows if str(r.get('exercise', '')).strip()}),
                "cloud_error": "; ".join([_to_text(e.get("error", "")) for e in cloud_errors if e.get("error")]).strip(),
                "csv_backup_ok": bool(csv_ok),
                "csv_backup_error": _to_text(csv_error),
                "csv_rows_written": int(csv_rows),
                "before_count": int(before_count),
                "after_count": int(after_count),
                "errors": cloud_errors,
                "already_saved": False,
            }
        )

    csv_ok, csv_error, csv_rows = _append_backup_rows(backup_rows)
    already_saved = duplicates_skipped > 0 and sets_inserted == 0

    return _set_last_save_result(
        {
            "ok": True,
            "status": "already_saved" if already_saved else "saved",
            "cloud": "Supabase",
            "history_source": "Supabase Cloud",
            "session_id": incoming_session_id,
            "session_id_supported": bool(session_id_supported),
            "sets_attempted": len(normalized_rows),
            "sets_inserted": int(sets_inserted),
            "duplicates_skipped": int(duplicates_skipped),
            "verified_rows": int(verified_rows),
            "exercises_saved": len({str(r.get('exercise', '')).strip().lower() for r in normalized_rows if str(r.get('exercise', '')).strip()}),
            "cloud_error": "",
            "csv_backup_ok": bool(csv_ok),
            "csv_backup_error": _to_text(csv_error),
            "csv_rows_written": int(csv_rows),
            "before_count": int(before_count),
            "after_count": int(after_count),
            "errors": [],
            "already_saved": bool(already_saved),
        }
    )


def save_cardio_sessions(session_data: Dict[str, Any], cardio_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    session_data = session_data or {}
    cardio_sessions = cardio_sessions or []

    incoming_session_id = _to_text(session_data.get("session_id", session_data.get("workout_session_id", ""))).strip()
    if not incoming_session_id:
        incoming_session_id = build_workout_session_id()

    if not cardio_sessions:
        return _set_last_save_result(
            {
                "ok": True,
                "status": "no_cardio",
                "cloud": "Supabase",
                "history_source": "none",
                "session_id": incoming_session_id,
                "cardio_attempted": 0,
                "cardio_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "cloud_error": "",
                "csv_backup_ok": True,
                "csv_backup_error": "",
                "csv_rows_written": 0,
                "setup_warning": "",
                "errors": [],
            }
        )

    normalized_rows: List[Dict[str, Any]] = []
    validation_errors: List[Dict[str, Any]] = []
    for i, raw in enumerate(cardio_sessions):
        merged = dict(raw or {})
        if not _to_text(merged.get("workout_session_id", "")).strip():
            merged["workout_session_id"] = incoming_session_id
        result = validate_cardio_session(merged)
        if not result["ok"]:
            validation_errors.append({"index": i, "errors": result["errors"]})
            continue
        normalized_rows.append(result["normalized"])

    if validation_errors:
        return _set_last_save_result(
            {
                "ok": False,
                "status": "cardio_validation_error",
                "cloud": "Supabase",
                "history_source": "none",
                "session_id": incoming_session_id,
                "cardio_attempted": len(cardio_sessions),
                "cardio_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "cloud_error": "Validation failed",
                "csv_backup_ok": False,
                "csv_backup_error": "Validation failed before persistence",
                "csv_rows_written": 0,
                "setup_warning": "",
                "errors": validation_errors,
            }
        )

    client, conn_err = connect_supabase()
    if conn_err or client is None:
        csv_ok, csv_error, csv_rows = _append_cardio_backup_rows(normalized_rows)
        return _set_last_save_result(
            {
                "ok": False,
                "status": "cardio_backup_only",
                "cloud": "Supabase",
                "history_source": "Local CSV Backup",
                "session_id": incoming_session_id,
                "cardio_attempted": len(normalized_rows),
                "cardio_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "cloud_error": _to_text(conn_err, "Cloud unavailable"),
                "csv_backup_ok": bool(csv_ok),
                "csv_backup_error": _to_text(csv_error),
                "csv_rows_written": int(csv_rows),
                "setup_warning": "",
                "errors": [{"index": -1, "error": _to_text(conn_err, "Cloud unavailable")}],
            }
        )

    if not _supports_cardio_sessions_table(client):
        csv_ok, csv_error, csv_rows = _append_cardio_backup_rows(normalized_rows)
        setup_warning = "Supabase table public.cardio_sessions is not available. Run supabase/cardio_sessions_schema.sql"
        return _set_last_save_result(
            {
                "ok": False,
                "status": "cardio_setup_required",
                "cloud": "Supabase",
                "history_source": "Local CSV Backup",
                "session_id": incoming_session_id,
                "cardio_attempted": len(normalized_rows),
                "cardio_inserted": 0,
                "duplicates_skipped": 0,
                "verified_rows": 0,
                "cloud_error": "cardio_sessions table missing",
                "csv_backup_ok": bool(csv_ok),
                "csv_backup_error": _to_text(csv_error),
                "csv_rows_written": int(csv_rows),
                "setup_warning": setup_warning,
                "errors": [{"index": -1, "error": setup_warning}],
            }
        )

    before_count = 0
    try:
        before_count = _count_cardio_sessions(client)
    except Exception:
        before_count = 0

    inserted_rows: List[Dict[str, Any]] = []
    backup_rows: List[Dict[str, Any]] = []
    cloud_errors: List[Dict[str, Any]] = []
    duplicates_skipped = 0
    verified_rows = 0
    setup_warning = ""

    for idx, row in enumerate(normalized_rows):
        try:
            if _is_cardio_duplicate(client, row):
                duplicates_skipped += 1
                continue
            payload = _cardio_payload(row)
            client.table("cardio_sessions").insert(payload).execute()
            if _verify_cardio_inserted(client, row):
                verified_rows += 1
                inserted_rows.append(row)
                backup_rows.append(row)
            else:
                cloud_errors.append({"index": idx, "error": "Insert verification failed", "row": row})
        except Exception as exc:
            err_txt = str(exc)
            cloud_errors.append({"index": idx, "error": err_txt, "row": row})
            if _is_missing_cardio_table_error(err_txt):
                setup_warning = "Supabase table public.cardio_sessions is not available. Run supabase/cardio_sessions_schema.sql"

    inserted_count = len(inserted_rows)
    after_count = before_count
    try:
        after_count = _count_cardio_sessions(client)
    except Exception:
        pass

    if cloud_errors:
        fallback_rows = []
        inserted_keys = {
            (r.get("workout_session_id", ""), r["activity_type"], r["activity_date"])
            for r in backup_rows
        }
        for r in normalized_rows:
            key = (r.get("workout_session_id", ""), r["activity_type"], r["activity_date"])
            if key not in inserted_keys:
                fallback_rows.append(r)
        csv_ok, csv_error, csv_rows = _append_cardio_backup_rows(fallback_rows)
        return _set_last_save_result(
            {
                "ok": False,
                "status": "cardio_partial_backup_only",
                "cloud": "Supabase",
                "history_source": "Local CSV Backup",
                "session_id": incoming_session_id,
                "cardio_attempted": len(normalized_rows),
                "cardio_inserted": int(inserted_count),
                "duplicates_skipped": int(duplicates_skipped),
                "verified_rows": int(verified_rows),
                "cloud_error": "; ".join([_to_text(e.get("error", "")) for e in cloud_errors if e.get("error")]).strip(),
                "csv_backup_ok": bool(csv_ok),
                "csv_backup_error": _to_text(csv_error),
                "csv_rows_written": int(csv_rows),
                "before_count": int(before_count),
                "after_count": int(after_count),
                "setup_warning": setup_warning,
                "errors": cloud_errors,
            }
        )

    csv_ok, csv_error, csv_rows = _append_cardio_backup_rows(backup_rows)
    already_saved = duplicates_skipped > 0 and inserted_count == 0
    return _set_last_save_result(
        {
            "ok": True,
            "status": "already_saved" if already_saved else "saved",
            "cloud": "Supabase",
            "history_source": "Supabase Cloud",
            "session_id": incoming_session_id,
            "cardio_attempted": len(normalized_rows),
            "cardio_inserted": int(inserted_count),
            "duplicates_skipped": int(duplicates_skipped),
            "verified_rows": int(verified_rows),
            "cloud_error": "",
            "csv_backup_ok": bool(csv_ok),
            "csv_backup_error": _to_text(csv_error),
            "csv_rows_written": int(csv_rows),
            "before_count": int(before_count),
            "after_count": int(after_count),
            "setup_warning": "",
            "errors": [],
            "already_saved": bool(already_saved),
        }
    )


def save_cardio_session(cardio_data: Dict[str, Any]) -> Dict[str, Any]:
    return save_cardio_sessions({}, [cardio_data])


def save_mixed_workout(strength_sets: List[Dict[str, Any]], cardio_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    strength_sets = strength_sets or []
    cardio_sessions = cardio_sessions or []

    session_id = ""
    if strength_sets:
        session_id = _to_text((strength_sets[0] or {}).get("workout_session_id", "")).strip()
    if not session_id and cardio_sessions:
        session_id = _to_text((cardio_sessions[0] or {}).get("workout_session_id", "")).strip()
    if not session_id:
        session_id = build_workout_session_id()

    strength_result = save_workout_session(
        session_data={"session_id": session_id, "workout_session_id": session_id},
        completed_sets=[{**(row or {}), "workout_session_id": _to_text((row or {}).get("workout_session_id", session_id)).strip() or session_id} for row in strength_sets],
    )

    cardio_rows = []
    for row in cardio_sessions:
        merged = dict(row or {})
        if not _to_text(merged.get("workout_session_id", "")).strip():
            merged["workout_session_id"] = session_id
        cardio_rows.append(merged)
    cardio_result = save_cardio_sessions(
        session_data={"session_id": session_id, "workout_session_id": session_id},
        cardio_sessions=cardio_rows,
    )

    mixed_ok = bool(strength_result.get("ok", False)) and bool(cardio_result.get("ok", False))
    return _set_last_save_result(
        {
            "ok": mixed_ok,
            "status": "mixed_saved" if mixed_ok else "mixed_partial",
            "session_id": session_id,
            "strength": strength_result,
            "cardio": cardio_result,
            "verified_rows": int(strength_result.get("verified_rows", 0)) + int(cardio_result.get("verified_rows", 0)),
            "cloud_error": "; ".join([
                _to_text(strength_result.get("cloud_error", "")).strip(),
                _to_text(cardio_result.get("cloud_error", "")).strip(),
            ]).strip("; "),
            "setup_warning": _to_text(cardio_result.get("setup_warning", "")),
        }
    )


def save_unified_workout(
    workout_session_id: str,
    strength_sets: Optional[List[Dict[str, Any]]] = None,
    cardio_sessions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    strength_sets = list(strength_sets or [])
    cardio_sessions = list(cardio_sessions or [])
    session_id = _to_text(workout_session_id, "").strip() or build_workout_session_id()

    patched_strength = []
    for row in strength_sets:
        patched = dict(row or {})
        if not _to_text(patched.get("workout_session_id", "")).strip():
            patched["workout_session_id"] = session_id
        patched_strength.append(patched)

    patched_cardio = []
    for row in cardio_sessions:
        patched = dict(row or {})
        if not _to_text(patched.get("workout_session_id", "")).strip():
            patched["workout_session_id"] = session_id
        patched_cardio.append(patched)

    if patched_strength and patched_cardio:
        return save_mixed_workout(patched_strength, patched_cardio)
    if patched_strength:
        return save_workout_session({"session_id": session_id, "workout_session_id": session_id}, patched_strength)
    if patched_cardio:
        return save_cardio_sessions({"session_id": session_id, "workout_session_id": session_id}, patched_cardio)

    return _set_last_save_result(
        {
            "ok": True,
            "status": "no_rows",
            "session_id": session_id,
            "verified_rows": 0,
            "cloud_error": "",
            "setup_warning": "",
        }
    )


def get_cardio_sessions(days: Optional[int] = 90, activity_type: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    client, conn_err = connect_supabase()
    if conn_err or client is None:
        return _load_cardio_local_rows(days=days, activity_type=activity_type), _to_text(conn_err, "Cloud unavailable"), None

    if not _supports_cardio_sessions_table(client):
        setup_warning = "Supabase table public.cardio_sessions is not available. Run supabase/cardio_sessions_schema.sql"
        return _load_cardio_local_rows(days=days, activity_type=activity_type), None, setup_warning

    cutoff_iso: Optional[str] = None
    if isinstance(days, int) and days > 0:
        cutoff_iso = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(days))).date().isoformat()

    try:
        query = client.table("cardio_sessions").select("*")
        if cutoff_iso:
            query = query.gte("activity_date", cutoff_iso)
        if activity_type and str(activity_type).strip().lower() not in {"", "all"}:
            query = query.eq("activity_type", str(activity_type).strip())
        response = query.order("activity_date", desc=True).order("created_at", desc=True).execute()
        return list(response.data or []), None, None
    except Exception as exc:
        err_txt = str(exc)
        setup_warning = None
        if _is_missing_cardio_table_error(err_txt):
            setup_warning = "Supabase table public.cardio_sessions is not available. Run supabase/cardio_sessions_schema.sql"
        return _load_cardio_local_rows(days=days, activity_type=activity_type), err_txt, setup_warning
