from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from services.supabase_service import connect_supabase


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
LOG_PATH = DATA_DIR / "workout_log.csv"

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


def _ensure_log_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        pd.DataFrame(columns=CSV_COLUMNS).to_csv(LOG_PATH, index=False)


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
