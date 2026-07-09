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
    client, err = connect_supabase()
    if err:
        return False, err

    try:
        payload = _workout_payload(workout)
        client.table('workouts').insert(payload).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


def get_workouts() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    client, err = connect_supabase()
    if err:
        return [], err

    try:
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
