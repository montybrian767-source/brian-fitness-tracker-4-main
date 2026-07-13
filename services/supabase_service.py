from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import time

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

FEATURE_TABLES = {
    'Workouts': {'table': 'workouts', 'optional': False, 'sql': ''},
    'Cardio Sessions': {'table': 'cardio_sessions', 'optional': True, 'sql': 'supabase/cardio_sessions_schema.sql'},
    'Apple Activity Daily': {'table': 'apple_activity_daily', 'optional': True, 'sql': 'supabase/apple_activity_daily_schema.sql'},
    'Apple Workouts': {'table': 'apple_workouts', 'optional': True, 'sql': 'supabase/apple_workouts_schema.sql'},
    'Daily Readiness': {'table': 'daily_readiness', 'optional': True, 'sql': 'supabase/daily_readiness_schema.sql'},
    'Coaching Feedback': {'table': 'coaching_feedback', 'optional': True, 'sql': 'supabase/coaching_feedback_schema.sql'},
    'Apple Import Jobs': {'table': 'apple_import_jobs', 'optional': True, 'sql': 'supabase/apple_import_jobs_schema.sql'},
}

HEALTH_DEFAULTS: Dict[str, Any] = {
    'ok': False,
    'message': 'Health check returned an invalid result.',
    'latency_ms': None,
    'workouts_ready': False,
    'cardio_ready': False,
    'apple_ready': False,
    'connected': False,
    'status': 'error',
    'workout_count': 0,
    'last_checked': '',
    'error': '',
}


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
        return _create_cached_supabase_client(supabase_url, supabase_key), None
    except Exception as exc:
        return None, str(exc)


@st.cache_resource(show_spinner=False)
def _create_cached_supabase_client(supabase_url: str, supabase_key: str):
    from supabase import create_client
    started = time.perf_counter()
    client = create_client(supabase_url, supabase_key)
    st.session_state['supabase_client_init_ms'] = round((time.perf_counter() - started) * 1000.0, 2)
    return client


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


def get_workouts(days: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return [], err

    cutoff_iso: Optional[str] = None
    if isinstance(days, int) and days > 0:
        cutoff_iso = (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(days))).date().isoformat()

    try:
        try:
            query = client.table('workouts').select(
                'id,created_at,workout_session_id,workout_date,day,exercise,set_number,weight_lbs,reps,rpe,body_feedback_score,body_feedback_notes,volume'
            )
            if cutoff_iso:
                query = query.gte('workout_date', cutoff_iso)
            response = query.order('workout_date', desc=False).order('set_number', desc=False).execute()
            return list(response.data or []), None
        except Exception:
            query = client.table('workouts').select(
                'id,created_at,workout_date,day,exercise,set_number,weight_lbs,reps,rpe,body_feedback_score,body_feedback_notes,volume'
            )
            if cutoff_iso:
                query = query.gte('workout_date', cutoff_iso)
            response = query.order('workout_date', desc=False).order('set_number', desc=False).execute()
            return list(response.data or []), None
    except Exception as exc:
        return [], str(exc)


def get_database_feature_status() -> Tuple[Dict[str, Dict[str, str]], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return {}, str(err)

    status: Dict[str, Dict[str, str]] = {}
    for name, meta in FEATURE_TABLES.items():
        table_name = str(meta.get('table', '')).strip()
        sql_file = str(meta.get('sql', '')).strip()
        optional = bool(meta.get('optional', False))
        try:
            response = client.table(table_name).select('id', count='exact', head=True).execute()
            count = int(response.count or 0)
            status[name] = {
                'state': 'Ready',
                'optional': 'Yes' if optional else 'No',
                'table': table_name,
                'sql': sql_file,
                'details': f'Rows: {count}',
            }
        except Exception as exc:
            status[name] = {
                'state': 'Missing',
                'optional': 'Yes' if optional else 'No',
                'table': table_name,
                'sql': sql_file,
                'details': str(exc),
            }
    return status, None


def delete_workout(row_id: int) -> Tuple[bool, Optional[str]]:
    client, err = connect_supabase()
    if err:
        return False, err

    try:
        client.table('workouts').delete().eq('id', int(row_id)).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


def normalize_health_check_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, BaseException):
        payload = dict(HEALTH_DEFAULTS)
        payload['message'] = 'Health check failed.'
        payload['error'] = str(result)
        payload['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return payload

    if isinstance(result, dict):
        payload = dict(HEALTH_DEFAULTS)
        payload.update({k: v for k, v in result.items() if k in payload})

        connected = bool(result.get('connected', payload.get('connected', False)))
        ok = bool(result.get('ok', connected))
        message = str(result.get('message', '') or result.get('error', '') or payload['message'])
        latency_ms = result.get('latency_ms', payload['latency_ms'])
        workouts_ready = bool(result.get('workouts_ready', connected))
        cardio_ready = bool(result.get('cardio_ready', False))
        apple_ready = bool(result.get('apple_ready', False))

        payload.update({
            'ok': ok,
            'message': message,
            'latency_ms': latency_ms,
            'workouts_ready': workouts_ready,
            'cardio_ready': cardio_ready,
            'apple_ready': apple_ready,
            'connected': connected,
            'status': str(result.get('status', payload.get('status', 'unknown')) or 'unknown'),
            'workout_count': int(result.get('workout_count', payload.get('workout_count', 0)) or 0),
            'last_checked': str(result.get('last_checked', payload.get('last_checked', '')) or ''),
            'error': str(result.get('error', payload.get('error', '')) or ''),
        })
        return payload

    if isinstance(result, (tuple, list)):
        values = list(result) + [None] * 6
        ok = bool(values[0])
        message = str(values[1] or '')
        latency_ms = values[2]
        workouts_ready = bool(values[3])
        cardio_ready = bool(values[4])
        apple_ready = bool(values[5])
        return {
            'ok': ok,
            'message': message,
            'latency_ms': latency_ms,
            'workouts_ready': workouts_ready,
            'cardio_ready': cardio_ready,
            'apple_ready': apple_ready,
            'connected': ok,
            'status': 'healthy' if ok else 'degraded',
            'workout_count': 0,
            'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': '' if ok else message,
        }

    return dict(HEALTH_DEFAULTS)


def safe_health_check() -> Dict[str, Any]:
    try:
        return normalize_health_check_result(health_check())
    except Exception as exc:
        return normalize_health_check_result(exc)


def health_check() -> Dict[str, Any]:
    client, err = connect_supabase()
    started = time.perf_counter()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if err:
        return normalize_health_check_result({
            'ok': False,
            'connected': False,
            'status': 'disconnected',
            'workout_count': 0,
            'latency_ms': None,
            'workouts_ready': False,
            'cardio_ready': False,
            'apple_ready': False,
            'last_checked': now,
            'message': 'SUPABASE_URL / SUPABASE_KEY missing or invalid.',
            'error': err,
        })

    try:
        workouts_response = client.table('workouts').select('*', count='exact', head=True).execute()
        workout_count = int(workouts_response.count or 0)

        workouts_ready = True

        try:
            client.table('cardio_sessions').select('id', count='exact', head=True).execute()
            cardio_ready = True
        except Exception:
            cardio_ready = False

        try:
            client.table('apple_activity_daily').select('id', count='exact', head=True).execute()
            client.table('apple_workouts').select('id', count='exact', head=True).execute()
            apple_ready = True
        except Exception:
            apple_ready = False

        ok = bool(workouts_ready and cardio_ready and apple_ready)
        status = 'healthy' if ok else 'degraded'
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        message = 'Supabase connected' if ok else 'Supabase connected with missing optional tables.'

        return normalize_health_check_result({
            'ok': ok,
            'connected': True,
            'status': status,
            'workout_count': workout_count,
            'latency_ms': latency_ms,
            'workouts_ready': workouts_ready,
            'cardio_ready': cardio_ready,
            'apple_ready': apple_ready,
            'last_checked': now,
            'message': message,
            'error': '',
        })
    except Exception as exc:
        return normalize_health_check_result({
            'ok': False,
            'connected': False,
            'status': 'error',
            'workout_count': 0,
            'latency_ms': round((time.perf_counter() - started) * 1000.0, 2),
            'workouts_ready': False,
            'cardio_ready': False,
            'apple_ready': False,
            'last_checked': now,
            'message': 'Cloud unavailable',
            'error': str(exc),
        })
