from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


WORKOUT_COLUMNS = [
    'workout_date',
    'day',
    'exercise',
    'set_number',
    'weight_lbs',
    'reps',
    'rpe',
    'body_feedback_score',
    'body_feedback_notes',
    'volume',
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


def _to_text(value: Any, default: str = '') -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return str(value)


def _normalize_workout_row(row: Dict[str, Any]) -> Dict[str, Any]:
    workout_date = _to_text(row.get('workout_date', row.get('date', '')))
    day = _to_text(row.get('day', ''))
    exercise = _to_text(row.get('exercise', ''))
    set_number = _to_int(row.get('set_number', 1), 1)
    weight_lbs = _to_float(row.get('weight_lbs', 0.0), 0.0)
    reps = _to_int(row.get('reps', 0), 0)
    rpe = _to_float(row.get('rpe', 0.0), 0.0)
    body_feedback_score = _to_int(row.get('body_feedback_score', row.get('pain', 0)), 0)
    body_feedback_notes = _to_text(row.get('body_feedback_notes', row.get('notes', '')))
    volume = _to_float(row.get('volume', weight_lbs * reps), weight_lbs * reps)

    normalized = {
        'workout_date': workout_date,
        'day': day,
        'exercise': exercise,
        'set_number': set_number,
        'weight_lbs': weight_lbs,
        'reps': reps,
        'rpe': rpe,
        'body_feedback_score': body_feedback_score,
        'body_feedback_notes': body_feedback_notes,
        'volume': volume,
    }

    workout_session_id = _to_text(row.get('workout_session_id', ''))
    if workout_session_id:
        normalized['workout_session_id'] = workout_session_id

    return normalized


def _supports_workout_session_id(client: Any) -> bool:
    try:
        client.table('workouts').select('workout_session_id').limit(1).execute()
        return True
    except Exception:
        return False


def _fetch_workout_count(client: Any) -> Tuple[int, Optional[str]]:
    try:
        response = client.table('workouts').select('*', count='exact', head=True).execute()
        return int(response.count or 0), None
    except Exception as exc:
        return 0, str(exc)


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _workout_payload(workout: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in WORKOUT_COLUMNS:
        payload[key] = _clean_value(workout.get(key))
    return payload


def connect_supabase() -> Tuple[Optional[Any], Optional[str]]:
    try:
        supabase_url = str(st.secrets.get('SUPABASE_URL', '')).strip()
        supabase_key = str(st.secrets.get('SUPABASE_KEY', '')).strip()
    except Exception:
        return None, 'missing_credentials'

    if not supabase_url or not supabase_key:
        return None, 'missing_credentials'

    try:
        from supabase import create_client

        return create_client(supabase_url, supabase_key), None
    except Exception as exc:
        return None, str(exc)


def save_workout(workout: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    result = save_workout_set(workout)
    if result.get('ok'):
        return True, None
    errors = result.get('errors', [])
    if errors:
        return False, str(errors[0].get('error', 'unknown_error'))
    return False, 'unknown_error'


def save_workout_set(row: Dict[str, Any]) -> Dict[str, Any]:
    return save_workout_session([row])


def save_workout_session(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    client, err = connect_supabase()
    if err:
        return {
            'ok': False,
            'session_id_supported': False,
            'session_id_used': False,
            'attempted_sets': len(rows),
            'inserted_sets': 0,
            'skipped_duplicates': 0,
            'before_count': 0,
            'after_count': 0,
            'verified_inserted': 0,
            'session_id': _to_text(rows[0].get('workout_session_id', '')) if rows else '',
            'inserted_rows': [],
            'errors': [{'index': -1, 'error': str(err)}],
        }

    if not rows:
        return {
            'ok': True,
            'session_id_supported': False,
            'session_id_used': False,
            'attempted_sets': 0,
            'inserted_sets': 0,
            'skipped_duplicates': 0,
            'before_count': 0,
            'after_count': 0,
            'verified_inserted': 0,
            'session_id': '',
            'inserted_rows': [],
            'errors': [],
        }

    before_count, before_err = _fetch_workout_count(client)
    if before_err:
        return {
            'ok': False,
            'session_id_supported': False,
            'session_id_used': False,
            'attempted_sets': len(rows),
            'inserted_sets': 0,
            'skipped_duplicates': 0,
            'before_count': 0,
            'after_count': 0,
            'verified_inserted': 0,
            'session_id': _to_text(rows[0].get('workout_session_id', '')),
            'inserted_rows': [],
            'errors': [{'index': -1, 'error': str(before_err)}],
        }

    supports_session_id = _supports_workout_session_id(client)
    errors: List[Dict[str, Any]] = []
    inserted_rows: List[Dict[str, Any]] = []
    inserted_sets = 0
    skipped_duplicates = 0

    normalized_rows = [_normalize_workout_row(r) for r in rows]
    session_id = _to_text(normalized_rows[0].get('workout_session_id', '')) if normalized_rows else ''
    session_id_used = bool(supports_session_id and session_id)

    for i, normalized in enumerate(normalized_rows):
        try:
            dedupe_query = (
                client.table('workouts')
                .select('id')
                .eq('workout_date', normalized['workout_date'])
                .eq('day', normalized['day'])
                .eq('exercise', normalized['exercise'])
                .eq('set_number', normalized['set_number'])
            )
            if supports_session_id and normalized.get('workout_session_id'):
                dedupe_query = dedupe_query.eq('workout_session_id', normalized.get('workout_session_id'))
            duplicate_check = dedupe_query.limit(1).execute()
            if duplicate_check.data:
                skipped_duplicates += 1
                continue

            payload = _workout_payload(normalized)
            if supports_session_id and normalized.get('workout_session_id'):
                payload['workout_session_id'] = normalized.get('workout_session_id')

            response = client.table('workouts').insert(payload).execute()
            inserted_sets += 1
            if response.data:
                inserted_rows.extend(list(response.data))
        except Exception as exc:
            errors.append({'index': i, 'error': str(exc), 'row': normalized})

    after_count, after_err = _fetch_workout_count(client)
    if after_err:
        errors.append({'index': -1, 'error': str(after_err)})
        verified_inserted = 0
    else:
        verified_inserted = max(0, after_count - before_count)

    ok = not errors and (verified_inserted >= inserted_sets)

    return {
        'ok': bool(ok),
        'session_id_supported': bool(supports_session_id),
        'session_id_used': bool(session_id_used),
        'attempted_sets': len(rows),
        'inserted_sets': int(inserted_sets),
        'skipped_duplicates': int(skipped_duplicates),
        'before_count': int(before_count),
        'after_count': int(after_count),
        'verified_inserted': int(verified_inserted),
        'session_id': session_id,
        'inserted_rows': inserted_rows,
        'errors': errors,
    }


def get_workouts() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return [], err

    try:
        try:
            response = (
                client.table('workouts')
                .select(
                    'id,created_at,workout_session_id,workout_date,day,exercise,set_number,weight_lbs,reps,rpe,body_feedback_score,body_feedback_notes,volume'
                )
                .order('workout_date', desc=False)
                .order('set_number', desc=False)
                .execute()
            )
            return list(response.data or []), None
        except Exception:
            response = (
                client.table('workouts')
                .select(
                    'id,created_at,workout_date,day,exercise,set_number,weight_lbs,reps,rpe,body_feedback_score,body_feedback_notes,volume'
                )
                .order('workout_date', desc=False)
                .order('set_number', desc=False)
                .execute()
            )
            return list(response.data or []), None
    except Exception as exc:
        return [], str(exc)


def delete_workout(row_id: int) -> Tuple[bool, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return False, err

    try:
        client.table('workouts').delete().eq('id', int(row_id)).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


def health_check() -> Dict[str, Any]:
    client, err = connect_supabase()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if err:
        return {
            'connected': False,
            'status': 'disconnected',
            'workout_count': 0,
            'last_checked': now,
            'message': 'SUPABASE_URL / SUPABASE_KEY missing or invalid.',
            'error': err,
        }

    try:
        response = client.table('workouts').select('*', count='exact', head=True).execute()
        return {
            'connected': True,
            'status': 'healthy',
            'workout_count': int(response.count or 0),
            'last_checked': now,
            'message': 'Connected',
            'error': '',
        }
    except Exception as exc:
        return {
            'connected': False,
            'status': 'error',
            'workout_count': 0,
            'last_checked': now,
            'message': 'Cloud unavailable',
            'error': str(exc),
        }
