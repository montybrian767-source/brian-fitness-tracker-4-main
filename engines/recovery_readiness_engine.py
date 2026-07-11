from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


MUSCLE_GROUPS = [
    'Chest',
    'Back',
    'Shoulders',
    'Biceps',
    'Triceps',
    'Quads',
    'Hamstrings',
    'Glutes',
    'Calves',
    'Core',
]

MUSCLE_KEYWORDS = {
    'Chest': ['chest', 'bench', 'press', 'fly', 'pec'],
    'Back': ['back', 'row', 'pull', 'pulldown', 'lat'],
    'Shoulders': ['shoulder', 'overhead', 'lateral raise', 'rear delt', 'front raise'],
    'Biceps': ['bicep', 'curl', 'hammer curl'],
    'Triceps': ['tricep', 'pushdown', 'skull', 'dip'],
    'Quads': ['quad', 'squat', 'leg press', 'lunge', 'split squat'],
    'Hamstrings': ['hamstring', 'rdl', 'deadlift', 'leg curl', 'good morning'],
    'Glutes': ['glute', 'hip thrust', 'bridge', 'abductor'],
    'Calves': ['calf'],
    'Core': ['core', 'ab', 'plank', 'crunch', 'sit-up', 'oblique'],
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, value)))


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce')


def _to_date(target_date: Any) -> date:
    if isinstance(target_date, datetime):
        return pd.Timestamp(target_date, tz='UTC').date() if target_date.tzinfo is None else pd.Timestamp(target_date).tz_convert('UTC').date()
    if isinstance(target_date, date):
        return target_date
    parsed = pd.to_datetime(target_date, errors='coerce', utc=True)
    if pd.isna(parsed):
        return date.today()
    return parsed.date()


def to_utc_series(series):
    return pd.to_datetime(series, errors='coerce', utc=True)


def to_utc_day_bounds(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize('UTC')
    else:
        ts = ts.tz_convert('UTC')
    start = ts.normalize()
    return start, start + pd.Timedelta(days=1)


def _normalize_apple_daily(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    required = [
        'activity_date',
        'sleep_hours',
        'resting_heart_rate',
        'heart_rate_variability_ms',
        'active_energy_kcal',
        'exercise_minutes',
        'stand_hours',
        'steps',
        'walking_running_distance_miles',
        'average_heart_rate',
        'maximum_heart_rate',
    ]
    for col in required:
        if col not in base.columns:
            base[col] = pd.NA
    base['activity_date'] = to_utc_series(base['activity_date']).dt.normalize()
    base = base.dropna(subset=['activity_date']).sort_values('activity_date')
    for col in required:
        if col != 'activity_date':
            base[col] = _to_numeric(base[col])
    return base


def _normalize_apple_workouts(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    required = [
        'start_time',
        'end_time',
        'duration_minutes',
        'total_energy_kcal',
        'average_heart_rate',
        'maximum_heart_rate',
        'workout_type',
    ]
    for col in required:
        if col not in base.columns:
            base[col] = pd.NA
    base['start_time'] = to_utc_series(base['start_time'])
    if 'end_time' in base.columns:
        base['end_time'] = to_utc_series(base['end_time'])
    base = base.dropna(subset=['start_time']).sort_values('start_time')
    for col in ['duration_minutes', 'total_energy_kcal', 'average_heart_rate', 'maximum_heart_rate']:
        base[col] = _to_numeric(base[col])
    return base


def _normalize_strength_workouts(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    required = ['date', 'exercise', 'day', 'volume', 'rpe', 'set_number', 'reps', 'weight_lbs']
    for col in required:
        if col not in base.columns:
            base[col] = pd.NA

    base['date'] = pd.to_datetime(base['date'], errors='coerce', utc=True)
    base = base.dropna(subset=['date']).sort_values('date')
    for col in ['volume', 'rpe', 'set_number', 'reps', 'weight_lbs']:
        base[col] = _to_numeric(base[col]).fillna(0)

    if (base['volume'] <= 0).all():
        base['volume'] = (base['weight_lbs'] * base['reps']).fillna(0)

    base['exercise'] = base['exercise'].astype(str)
    return base


def _latest_row_on_or_before(df: pd.DataFrame, date_col: str, target: date) -> Optional[pd.Series]:
    if df.empty:
        return None
    if date_col not in df.columns:
        return None

    # Force both sides to UTC-aware timestamps before comparison.
    series = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    cutoff, _ = to_utc_day_bounds(target)
    filtered = df[series <= cutoff]
    if filtered.empty:
        return None
    return filtered.sort_values(date_col).iloc[-1]


def _safe_mean(series: pd.Series) -> Optional[float]:
    s = _to_numeric(series).dropna()
    if s.empty:
        return None
    return float(s.mean())


def _coverage_ratio(series: pd.Series, total_days: int) -> float:
    if total_days <= 0:
        return 0.0
    valid = _to_numeric(series).dropna().shape[0]
    return float(valid / total_days)


def calculate_personal_baselines(
    apple_daily_data: Optional[pd.DataFrame],
    strength_workouts: Optional[pd.DataFrame],
    target_date: Any,
) -> Dict[str, Any]:
    target = _to_date(target_date)
    target_start, _ = to_utc_day_bounds(target_date)
    apple = _normalize_apple_daily(apple_daily_data)
    strength = _normalize_strength_workouts(strength_workouts)

    apple_window = apple[apple['activity_date'] <= target_start].copy()
    target_start_ts, _ = to_utc_day_bounds(target)
    strength_window = strength[strength['date'] <= target_start_ts].copy()

    recent7 = apple_window[apple_window['activity_date'] >= (target_start - pd.Timedelta(days=6))]
    base28 = apple_window[apple_window['activity_date'] >= (target_start - pd.Timedelta(days=27))]

    strength_7 = strength_window[strength_window['date'] >= (target_start_ts - pd.Timedelta(days=6))]
    strength_28 = strength_window[strength_window['date'] >= (target_start_ts - pd.Timedelta(days=27))]

    weekly_volume_7 = float(strength_7.groupby(strength_7['date'].dt.date)['volume'].sum().sum()) if not strength_7.empty else None
    weekly_volume_28 = float(strength_28.groupby(strength_28['date'].dt.date)['volume'].sum().sum()) if not strength_28.empty else None

    baseline = {
        'days_of_apple_data': int(base28['activity_date'].dt.date.nunique()) if not base28.empty else 0,
        'days_of_strength_data': int(strength_28['date'].dt.date.nunique()) if not strength_28.empty else 0,
        'recent_7': {
            'resting_heart_rate': _safe_mean(recent7['resting_heart_rate']) if not recent7.empty else None,
            'heart_rate_variability_ms': _safe_mean(recent7['heart_rate_variability_ms']) if not recent7.empty else None,
            'sleep_hours': _safe_mean(recent7['sleep_hours']) if not recent7.empty else None,
            'steps': _safe_mean(recent7['steps']) if not recent7.empty else None,
            'active_energy_kcal': _safe_mean(recent7['active_energy_kcal']) if not recent7.empty else None,
            'exercise_minutes': _safe_mean(recent7['exercise_minutes']) if not recent7.empty else None,
            'weekly_strength_volume': weekly_volume_7,
            'average_rpe': _safe_mean(strength_7['rpe']) if not strength_7.empty else None,
            'workout_frequency': float(strength_7['date'].dt.date.nunique()) if not strength_7.empty else None,
        },
        'baseline_28': {
            'resting_heart_rate': _safe_mean(base28['resting_heart_rate']) if not base28.empty else None,
            'heart_rate_variability_ms': _safe_mean(base28['heart_rate_variability_ms']) if not base28.empty else None,
            'sleep_hours': _safe_mean(base28['sleep_hours']) if not base28.empty else None,
            'steps': _safe_mean(base28['steps']) if not base28.empty else None,
            'active_energy_kcal': _safe_mean(base28['active_energy_kcal']) if not base28.empty else None,
            'exercise_minutes': _safe_mean(base28['exercise_minutes']) if not base28.empty else None,
            'weekly_strength_volume': weekly_volume_28,
            'average_rpe': _safe_mean(strength_28['rpe']) if not strength_28.empty else None,
            'workout_frequency': float(strength_28['date'].dt.date.nunique()) if not strength_28.empty else None,
        },
        'history_notes': [],
        'coverage': {
            'sleep': _coverage_ratio(base28['sleep_hours'], int(base28['activity_date'].dt.date.nunique()) or 1) if not base28.empty else 0.0,
            'hrv': _coverage_ratio(base28['heart_rate_variability_ms'], int(base28['activity_date'].dt.date.nunique()) or 1) if not base28.empty else 0.0,
            'resting_hr': _coverage_ratio(base28['resting_heart_rate'], int(base28['activity_date'].dt.date.nunique()) or 1) if not base28.empty else 0.0,
        },
    }

    if baseline['days_of_apple_data'] < 7:
        baseline['history_notes'].append('Limited Apple history (<7 days). Confidence reduced and conservative defaults applied.')
    elif baseline['days_of_apple_data'] < 28:
        baseline['history_notes'].append('Apple history is between 7 and 27 days. 7-day trends are weighted more than long baseline.')

    if baseline['days_of_strength_data'] < 7:
        baseline['history_notes'].append('Limited Brian Fit workout history (<7 days). Strength load confidence is reduced.')

    return baseline


def calculate_sleep_score(current_sleep: Optional[float], baseline_sleep: Optional[float], days_of_history: int) -> Dict[str, Any]:
    if current_sleep is None or pd.isna(current_sleep):
        return {'available': False, 'score': None, 'reason': 'Sleep data missing for target date.'}

    current = float(current_sleep)
    baseline = float(baseline_sleep) if baseline_sleep is not None and not pd.isna(baseline_sleep) else None

    if baseline is None:
        score = _clamp(62.0 + ((current - 7.0) * 9.0))
        return {
            'available': True,
            'score': score,
            'reason': 'Sleep scored with conservative default baseline due to limited history.',
        }

    delta = current - baseline
    score = _clamp(70.0 + (delta * 12.0))
    if delta < -1.0:
        reason = 'Sleep materially below personal baseline.'
    elif delta > 0.8:
        reason = 'Sleep above personal baseline.'
    else:
        reason = 'Sleep near personal baseline.'

    if days_of_history < 7:
        score = _clamp(score - 4.0)

    return {'available': True, 'score': score, 'reason': reason}


def calculate_hrv_score(current_hrv: Optional[float], baseline_hrv: Optional[float], days_of_history: int) -> Dict[str, Any]:
    if current_hrv is None or pd.isna(current_hrv):
        return {'available': False, 'score': None, 'reason': 'HRV data missing for target date.'}

    current = float(current_hrv)
    baseline = float(baseline_hrv) if baseline_hrv is not None and not pd.isna(baseline_hrv) else None

    if baseline is None or baseline <= 0:
        score = _clamp(60.0 + ((current - 40.0) * 0.6))
        return {
            'available': True,
            'score': score,
            'reason': 'HRV scored with conservative default baseline due to limited history.',
        }

    delta_pct = (current - baseline) / baseline
    score = _clamp(70.0 + (delta_pct * 85.0))
    if delta_pct <= -0.08:
        reason = 'HRV below personal baseline.'
    elif delta_pct >= 0.08:
        reason = 'HRV above personal baseline.'
    else:
        reason = 'HRV near personal baseline.'

    if days_of_history < 7:
        score = _clamp(score - 4.0)

    return {'available': True, 'score': score, 'reason': reason}


def calculate_resting_hr_score(current_rhr: Optional[float], baseline_rhr: Optional[float], days_of_history: int) -> Dict[str, Any]:
    if current_rhr is None or pd.isna(current_rhr):
        return {'available': False, 'score': None, 'reason': 'Resting heart-rate data missing for target date.'}

    current = float(current_rhr)
    baseline = float(baseline_rhr) if baseline_rhr is not None and not pd.isna(baseline_rhr) else None

    if baseline is None or baseline <= 0:
        score = _clamp(62.0 + ((60.0 - current) * 1.8))
        return {
            'available': True,
            'score': score,
            'reason': 'Resting heart-rate scored with conservative default baseline due to limited history.',
        }

    delta = current - baseline
    score = _clamp(72.0 - (delta * 7.5))
    if delta >= 5.0:
        reason = 'Resting heart-rate meaningfully above baseline.'
    elif delta <= -2.0:
        reason = 'Resting heart-rate below baseline.'
    else:
        reason = 'Resting heart-rate near baseline.'

    if days_of_history < 7:
        score = _clamp(score - 3.0)

    return {'available': True, 'score': score, 'reason': reason}


def calculate_activity_load_score(
    apple_daily_data: Optional[pd.DataFrame],
    apple_workouts: Optional[pd.DataFrame],
    target_date: Any,
    baselines: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        target = _to_date(target_date)
        daily = _normalize_apple_daily(apple_daily_data)
        workouts = _normalize_apple_workouts(apple_workouts)

        workouts = workouts.copy()
        # Normalize workout timestamps to UTC before all day-window comparisons.
        workouts['start_time'] = pd.to_datetime(
            workouts['start_time'],
            errors='coerce',
            utc=True,
        )
        if 'end_time' in workouts.columns:
            workouts['end_time'] = pd.to_datetime(
                workouts['end_time'],
                errors='coerce',
                utc=True,
            )
        workouts = workouts.dropna(subset=['start_time'])

        day_start, day_end = to_utc_day_bounds(target_date)

        latest_daily = _latest_row_on_or_before(daily, 'activity_date', target)
        if latest_daily is None and workouts.empty:
            return {'available': False, 'score': None, 'reason': 'Apple activity load data missing.'}

        base = baselines.get('baseline_28', {})
        base_steps = base.get('steps')
        base_energy = base.get('active_energy_kcal')
        base_minutes = base.get('exercise_minutes')

        day_score = 70.0
        details = []

        if latest_daily is not None:
            steps = float(latest_daily.get('steps') or 0.0)
            energy = float(latest_daily.get('active_energy_kcal') or 0.0)
            minutes = float(latest_daily.get('exercise_minutes') or 0.0)
            avg_hr = float(latest_daily.get('average_heart_rate') or 0.0)

            if base_steps and base_steps > 0:
                step_ratio = steps / float(base_steps)
                day_score += (1.0 - min(1.7, step_ratio)) * 6.0
            if base_energy and base_energy > 0:
                energy_ratio = energy / float(base_energy)
                day_score += (1.0 - min(1.8, energy_ratio)) * 8.0
            if base_minutes and base_minutes > 0:
                min_ratio = minutes / float(base_minutes)
                day_score += (1.0 - min(1.8, min_ratio)) * 8.0

            if avg_hr >= 150:
                day_score -= 5.0
            elif 0 < avg_hr <= 120:
                day_score += 2.0

            details.append(f'Steps {int(steps):,}, active calories {int(energy):,}, exercise minutes {int(minutes)}.')

        day_workouts = workouts[
            (workouts['start_time'] >= day_start)
            & (workouts['start_time'] < day_end)
        ].copy()

        if not day_workouts.empty:
            total_duration = float(day_workouts['duration_minutes'].fillna(0).sum())
            total_energy = float(day_workouts['total_energy_kcal'].fillna(0).sum())
            max_hr = float(day_workouts['maximum_heart_rate'].fillna(0).max())

            workout_load_index = (total_duration / 60.0) + (total_energy / 600.0)
            if max_hr > 0:
                workout_load_index += max(0.0, (max_hr - 145.0) / 25.0)

            day_score -= min(16.0, workout_load_index * 7.5)
            details.append(f'Apple workouts duration {int(total_duration)} min and calories {int(total_energy)} kcal.')

        day_score = _clamp(day_score)
        return {
            'available': True,
            'score': day_score,
            'reason': ' '.join(details) if details else 'Activity load available with partial signals.',
        }
    except Exception:
        return {
            'available': False,
            'score': None,
            'reason': 'Apple activity load unavailable due to timestamp parsing issues. Limited-data readiness applied.',
        }


def _strength_daily_aggregate(strength: pd.DataFrame) -> pd.DataFrame:
    if strength.empty:
        return pd.DataFrame(columns=['date', 'volume', 'sets', 'avg_rpe', 'exercise_count'])

    grouped = strength.groupby(strength['date'].dt.normalize(), as_index=False).agg(
        volume=('volume', 'sum'),
        sets=('set_number', 'count'),
        avg_rpe=('rpe', 'mean'),
        exercise_count=('exercise', 'nunique'),
    )
    return grouped.sort_values('date')


def _consecutive_training_days(strength_daily: pd.DataFrame, target: date) -> int:
    if strength_daily.empty:
        return 0

    days = set(strength_daily['date'].dt.date.tolist())
    count = 0
    check = target
    while check in days:
        count += 1
        check = check - timedelta(days=1)
    return count


def calculate_strength_load_score(
    strength_workouts: Optional[pd.DataFrame],
    target_date: Any,
    baselines: Dict[str, Any],
) -> Dict[str, Any]:
    target = _to_date(target_date)
    strength = _normalize_strength_workouts(strength_workouts)
    if strength.empty:
        return {'available': False, 'score': None, 'reason': 'No Brian Fit workout history available.'}

    target_start_ts, _ = to_utc_day_bounds(target)
    strength = strength[strength['date'] <= target_start_ts]
    daily = _strength_daily_aggregate(strength)
    if daily.empty:
        return {'available': False, 'score': None, 'reason': 'No Brian Fit workout history before target date.'}

    recent3 = daily[daily['date'] >= (target_start_ts - pd.Timedelta(days=2))]
    recent7 = daily[daily['date'] >= (target_start_ts - pd.Timedelta(days=6))]

    recent_volume_3 = float(recent3['volume'].sum()) if not recent3.empty else 0.0
    recent_volume_7 = float(recent7['volume'].sum()) if not recent7.empty else 0.0
    recent_avg_rpe = float(recent3['avg_rpe'].mean()) if not recent3.empty else 0.0
    weekly_baseline = baselines.get('baseline_28', {}).get('weekly_strength_volume')

    consecutive_days = _consecutive_training_days(daily, target)

    score = 72.0
    details = []

    if weekly_baseline and weekly_baseline > 0:
        weekly_ratio = recent_volume_7 / float(weekly_baseline)
        if weekly_ratio > 1.25:
            score -= min(20.0, (weekly_ratio - 1.25) * 34.0)
        elif weekly_ratio < 0.75:
            score += 6.0

    if recent_avg_rpe >= 8.8:
        score -= 16.0
        details.append('Recent RPE is high.')
    elif recent_avg_rpe >= 8.0:
        score -= 8.0
    elif 0 < recent_avg_rpe <= 6.8:
        score += 4.0

    if consecutive_days >= 4:
        score -= 14.0
        details.append(f'{consecutive_days} consecutive training days.')
    elif consecutive_days == 3:
        score -= 8.0
    elif consecutive_days <= 1:
        score += 4.0

    if recent_volume_3 > 0:
        details.append(f'3-day strength volume {int(recent_volume_3):,} lbs.')

    score = _clamp(score)
    return {
        'available': True,
        'score': score,
        'reason': ' '.join(details) if details else 'Strength load within normal range.',
        'details': {
            'recent_volume_3': recent_volume_3,
            'recent_volume_7': recent_volume_7,
            'recent_avg_rpe': recent_avg_rpe,
            'consecutive_training_days': consecutive_days,
            'weekly_baseline_volume': weekly_baseline,
        },
    }


def calculate_recovery_balance(
    strength_workouts: Optional[pd.DataFrame],
    target_date: Any,
) -> Dict[str, Any]:
    target = _to_date(target_date)
    strength = _normalize_strength_workouts(strength_workouts)

    if strength.empty:
        return {'available': True, 'score': 58.0, 'reason': 'No recent strength sessions; neutral recovery balance with low confidence.', 'details': {'days_since_last_workout': None}}

    target_start_ts, _ = to_utc_day_bounds(target)
    strength = strength[strength['date'] <= target_start_ts]
    if strength.empty:
        return {'available': True, 'score': 58.0, 'reason': 'No recent strength sessions before target date.', 'details': {'days_since_last_workout': None}}

    last_date = strength['date'].max().date()
    days_since_last = max(0, (target - last_date).days)

    score = 65.0 + (days_since_last * 8.0)
    if days_since_last == 0:
        score -= 12.0
    elif days_since_last == 1:
        score -= 5.0
    elif days_since_last >= 4:
        score += 6.0

    score = _clamp(score)
    reason = f'{days_since_last} day(s) since last strength workout.'
    return {
        'available': True,
        'score': score,
        'reason': reason,
        'details': {'days_since_last_workout': days_since_last, 'last_workout_date': str(last_date)},
    }


def calculate_activity_load_score_wrapper(*args, **kwargs) -> Dict[str, Any]:
    return calculate_activity_load_score(*args, **kwargs)


def _metric_label(metric_key: str) -> str:
    labels = {
        'sleep_score': 'Sleep',
        'hrv_score': 'HRV',
        'resting_hr_score': 'Resting HR',
        'activity_load_score': 'Apple activity load',
        'strength_load_score': 'Strength load',
        'recovery_balance_score': 'Recovery balance',
    }
    return labels.get(metric_key, metric_key)


def _status_from_score(score: float) -> str:
    if score >= 85:
        return 'Ready'
    if score >= 70:
        return 'Good'
    if score >= 50:
        return 'Moderate'
    if score >= 30:
        return 'Low'
    return 'Recovery Day'


def _coarse_confidence_label(confidence: float) -> str:
    if confidence >= 80:
        return 'High confidence'
    if confidence >= 55:
        return 'Moderate confidence'
    return 'Limited data'


def build_muscle_recovery_cards(
    strength_workouts: Optional[pd.DataFrame],
    apple_daily_data: Optional[pd.DataFrame],
    target_date: Any,
) -> List[Dict[str, Any]]:
    target = _to_date(target_date)
    strength = _normalize_strength_workouts(strength_workouts)
    apple = _normalize_apple_daily(apple_daily_data)

    latest_apple = _latest_row_on_or_before(apple, 'activity_date', target)
    secondary_load = 0.0
    if latest_apple is not None:
        secondary_load = float(latest_apple.get('active_energy_kcal') or 0.0) / 1200.0
        secondary_load += float(latest_apple.get('exercise_minutes') or 0.0) / 180.0

    cards: List[Dict[str, Any]] = []
    target_start_ts, _ = to_utc_day_bounds(target)
    recent_7 = strength[strength['date'] >= (target_start_ts - pd.Timedelta(days=6))]

    for muscle in MUSCLE_GROUPS:
        keywords = MUSCLE_KEYWORDS[muscle]
        mask = pd.Series(False, index=strength.index)
        if not strength.empty:
            ex_text = strength['exercise'].astype(str).str.lower()
            for key in keywords:
                mask = mask | ex_text.str.contains(key, na=False)

        muscle_rows = strength[mask] if not strength.empty else pd.DataFrame(columns=strength.columns)
        muscle_rows_7 = recent_7[mask.loc[recent_7.index]] if not recent_7.empty and not mask.empty else pd.DataFrame(columns=strength.columns)

        if muscle_rows.empty:
            recovery_pct = 86.0
            status = 'Ready'
            cards.append({
                'muscle': muscle,
                'recovery_percentage': int(round(recovery_pct)),
                'status': status,
                'last_trained': 'No history',
                'sets_last_7_days': 0,
                'recent_volume': 0,
                'average_recent_rpe': None,
                'suggested_next_training_day': str(target),
            })
            continue

        last_trained_date = muscle_rows['date'].max().date()
        days_since = max(0, (target - last_trained_date).days)
        sets_7 = int(muscle_rows_7.shape[0]) if not muscle_rows_7.empty else 0
        volume_7 = float(muscle_rows_7['volume'].sum()) if not muscle_rows_7.empty else 0.0
        avg_rpe_7 = float(muscle_rows_7['rpe'].mean()) if not muscle_rows_7.empty else None

        recovery_pct = 58.0 + min(34.0, days_since * 11.0)
        recovery_pct -= min(26.0, sets_7 * 1.9)
        recovery_pct -= min(18.0, volume_7 / 2200.0)
        if avg_rpe_7 is not None:
            recovery_pct -= max(0.0, (avg_rpe_7 - 7.2) * 8.0)

        recovery_pct -= min(8.0, secondary_load * 6.0)
        recovery_pct = _clamp(recovery_pct)

        if recovery_pct >= 80:
            status = 'Ready'
            next_day = target
        elif recovery_pct >= 65:
            status = 'Moderate'
            next_day = target + timedelta(days=1)
        elif recovery_pct >= 45:
            status = 'Recovering'
            next_day = target + timedelta(days=2)
        else:
            status = 'Fatigued'
            next_day = target + timedelta(days=3)

        cards.append({
            'muscle': muscle,
            'recovery_percentage': int(round(recovery_pct)),
            'status': status,
            'last_trained': str(last_trained_date),
            'sets_last_7_days': sets_7,
            'recent_volume': int(round(volume_7)),
            'average_recent_rpe': round(avg_rpe_7, 1) if avg_rpe_7 is not None and not pd.isna(avg_rpe_7) else None,
            'suggested_next_training_day': str(next_day),
        })

    return cards


def build_readiness_recommendation(
    readiness_score: float,
    recovery_status: str,
    component_scores: Dict[str, Optional[float]],
    muscle_cards: List[Dict[str, Any]],
    strength_details: Dict[str, Any],
) -> Dict[str, Any]:
    status = recovery_status

    ready_muscles = [m['muscle'] for m in muscle_cards if m.get('status') == 'Ready']
    avoid_muscles = [m['muscle'] for m in muscle_cards if m.get('status') in {'Fatigued', 'Recovering'}]

    if status == 'Ready':
        primary = 'Train Heavy'
        intensity_pct = '85-95%'
        duration = '60-75 minutes'
        volume_adjustment = 'Keep planned volume'
        rpe_ceiling = '8.5'
    elif status == 'Good':
        primary = 'Train Normally'
        intensity_pct = '75-88%'
        duration = '50-65 minutes'
        volume_adjustment = 'Keep volume, optional +5% on top sets'
        rpe_ceiling = '8.0'
    elif status == 'Moderate':
        primary = 'Moderate Session'
        intensity_pct = '65-78%'
        duration = '45-55 minutes'
        volume_adjustment = 'Reduce total volume by 20%'
        rpe_ceiling = '7.0'
    elif status == 'Low':
        primary = 'Technique / Mobility'
        intensity_pct = '50-65%'
        duration = '35-50 minutes'
        volume_adjustment = 'Reduce total volume by 30-40%'
        rpe_ceiling = '6.5'
    else:
        primary = 'Recovery Day'
        intensity_pct = '40-55% or rest'
        duration = '20-40 minutes mobility/walk'
        volume_adjustment = 'No heavy strength work'
        rpe_ceiling = '6.0'

    reasons = []
    sleep_score = component_scores.get('sleep_score')
    hrv_score = component_scores.get('hrv_score')
    resting_hr_score = component_scores.get('resting_hr_score')
    strength_score = component_scores.get('strength_load_score')

    if sleep_score is not None and sleep_score < 55:
        reasons.append('Sleep is below baseline.')
    if hrv_score is not None and hrv_score < 55:
        reasons.append('HRV is below baseline.')
    if resting_hr_score is not None and resting_hr_score < 55:
        reasons.append('Resting heart-rate is elevated versus baseline.')
    if strength_score is not None and strength_score < 55:
        reasons.append('Recent strength load and RPE suggest accumulated fatigue.')

    if not reasons:
        reasons.append('Current recovery signals support planned training.')

    coaching_reason = ' '.join(reasons)

    return {
        'primary_recommendation': primary,
        'recommended_intensity_percentage': intensity_pct,
        'suggested_duration': duration,
        'suggested_volume_adjustment': volume_adjustment,
        'suggested_rpe_ceiling': rpe_ceiling,
        'recommended_muscle_groups': ready_muscles[:4] if ready_muscles else ['Upper Body Pull', 'Core'],
        'reduce_or_avoid_muscle_groups': avoid_muscles[:4],
        'hydration_note': 'Target 80-120 oz water based on session duration and sweat rate.',
        'sleep_target': '7.5-9.0 hours',
        'coaching_reason': coaching_reason,
        'readiness_impact': f'{primary} selected from a {int(round(readiness_score))}/100 readiness score.',
    }


def _build_strength_source_dates(strength: pd.DataFrame) -> Dict[str, Any]:
    if strength.empty:
        return {'latest_strength_date': None, 'strength_days_used': 0}
    dates = strength['date'].dt.date
    return {
        'latest_strength_date': str(dates.max()),
        'strength_days_used': int(dates.nunique()),
    }


def _build_apple_source_dates(apple_daily: pd.DataFrame, apple_workouts: pd.DataFrame) -> Dict[str, Any]:
    out = {
        'latest_apple_activity_date': None,
        'apple_days_used': 0,
        'latest_apple_workout_start': None,
        'apple_workouts_used': 0,
    }
    if not apple_daily.empty:
        out['latest_apple_activity_date'] = str(apple_daily['activity_date'].dt.date.max())
        out['apple_days_used'] = int(apple_daily['activity_date'].dt.date.nunique())
    if not apple_workouts.empty:
        out['latest_apple_workout_start'] = str(apple_workouts['start_time'].max())
        out['apple_workouts_used'] = int(apple_workouts.shape[0])
    return out


def calculate_daily_readiness(
    apple_daily_data: Optional[pd.DataFrame],
    apple_workouts: Optional[pd.DataFrame],
    strength_workouts: Optional[pd.DataFrame],
    target_date: Any,
) -> Dict[str, Any]:
    try:
        target = _to_date(target_date)
        apple_daily = _normalize_apple_daily(apple_daily_data)
        apple_w = _normalize_apple_workouts(apple_workouts)
        strength = _normalize_strength_workouts(strength_workouts)

        baselines = calculate_personal_baselines(apple_daily, strength, target_date)

        latest_daily = _latest_row_on_or_before(apple_daily, 'activity_date', target)

        sleep_score_obj = calculate_sleep_score(
            current_sleep=float(latest_daily.get('sleep_hours')) if latest_daily is not None and not pd.isna(latest_daily.get('sleep_hours')) else None,
            baseline_sleep=baselines.get('baseline_28', {}).get('sleep_hours'),
            days_of_history=int(baselines.get('days_of_apple_data', 0)),
        )
        hrv_score_obj = calculate_hrv_score(
            current_hrv=float(latest_daily.get('heart_rate_variability_ms')) if latest_daily is not None and not pd.isna(latest_daily.get('heart_rate_variability_ms')) else None,
            baseline_hrv=baselines.get('baseline_28', {}).get('heart_rate_variability_ms'),
            days_of_history=int(baselines.get('days_of_apple_data', 0)),
        )
        resting_hr_score_obj = calculate_resting_hr_score(
            current_rhr=float(latest_daily.get('resting_heart_rate')) if latest_daily is not None and not pd.isna(latest_daily.get('resting_heart_rate')) else None,
            baseline_rhr=baselines.get('baseline_28', {}).get('resting_heart_rate'),
            days_of_history=int(baselines.get('days_of_apple_data', 0)),
        )

        activity_load_obj = calculate_activity_load_score(
            apple_daily_data=apple_daily,
            apple_workouts=apple_w,
            target_date=target_date,
            baselines=baselines,
        )
        strength_load_obj = calculate_strength_load_score(
            strength_workouts=strength,
            target_date=target,
            baselines=baselines,
        )
        recovery_balance_obj = calculate_recovery_balance(
            strength_workouts=strength,
            target_date=target,
        )

        component_objs = {
            'sleep_score': sleep_score_obj,
            'hrv_score': hrv_score_obj,
            'resting_hr_score': resting_hr_score_obj,
            'activity_load_score': activity_load_obj,
            'strength_load_score': strength_load_obj,
            'recovery_balance_score': recovery_balance_obj,
        }

        base_weights = {
            'sleep_score': 0.25,
            'hrv_score': 0.20,
            'resting_hr_score': 0.15,
            'activity_load_score': 0.10,
            'strength_load_score': 0.20,
            'recovery_balance_score': 0.10,
        }

        available_keys = [k for k, v in component_objs.items() if bool(v.get('available')) and v.get('score') is not None]
        weight_sum = sum(base_weights[k] for k in available_keys)

        redistributed_weights: Dict[str, float] = {}
        for key in base_weights:
            redistributed_weights[key] = (base_weights[key] / weight_sum) if key in available_keys and weight_sum > 0 else 0.0

        if weight_sum > 0:
            readiness_score = sum((float(component_objs[k]['score']) * redistributed_weights[k]) for k in available_keys)
        else:
            readiness_score = 50.0

        readiness_score = _clamp(readiness_score)
        recovery_status = _status_from_score(readiness_score)

        strength_details = strength_load_obj.get('details', {}) if strength_load_obj else {}
        muscle_cards = build_muscle_recovery_cards(strength, apple_daily, target)

        component_scores = {k: (float(v['score']) if v.get('score') is not None else None) for k, v in component_objs.items()}
        recommendation = build_readiness_recommendation(
            readiness_score=readiness_score,
            recovery_status=recovery_status,
            component_scores=component_scores,
            muscle_cards=muscle_cards,
            strength_details=strength_details,
        )

        positives: List[str] = []
        limiting: List[str] = []
        for key, obj in component_objs.items():
            score = obj.get('score')
            if score is None:
                continue
            label = _metric_label(key)
            reason = str(obj.get('reason', '')).strip()
            if float(score) >= 72:
                positives.append(f'{label}: {reason}')
            elif float(score) <= 58:
                limiting.append(f'{label}: {reason}')

        if not positives:
            positives.append('No strong positive signals today.')
        if not limiting:
            limiting.append('No major limiting factor detected from available data.')

        apple_days = int(baselines.get('days_of_apple_data', 0))
        strength_days = int(baselines.get('days_of_strength_data', 0))

        key_missing = [k for k in ['sleep_score', 'hrv_score', 'resting_hr_score'] if component_scores.get(k) is None]
        missing_inputs = [
            _metric_label(k) for k in key_missing
        ]

        confidence = 42.0
        confidence += min(18.0, apple_days * 0.9)
        confidence += min(16.0, strength_days * 0.7)
        confidence += len(available_keys) * 3.0
        if key_missing:
            confidence -= min(20.0, len(key_missing) * 7.0)
        if apple_days < 7:
            confidence -= 10.0
        confidence_score = _clamp(confidence)

        data_quality = {
            'apple_data_days_available': apple_days,
            'sleep_coverage': round(float(baselines.get('coverage', {}).get('sleep', 0.0)) * 100.0, 1),
            'hrv_coverage': round(float(baselines.get('coverage', {}).get('hrv', 0.0)) * 100.0, 1),
            'resting_hr_coverage': round(float(baselines.get('coverage', {}).get('resting_hr', 0.0)) * 100.0, 1),
            'strength_history_days': strength_days,
            'readiness_confidence': round(confidence_score, 1),
            'confidence_label': _coarse_confidence_label(confidence_score),
            'missing_inputs': missing_inputs,
            'limited_history': bool(apple_days < 7 or strength_days < 7),
            'history_notes': list(baselines.get('history_notes', [])),
        }

        source_dates = {
            **_build_apple_source_dates(apple_daily, apple_w),
            **_build_strength_source_dates(strength),
            'target_date': str(target),
        }

        last_strength_load = float(strength_details.get('recent_volume_3') or 0.0)

        today_row = _latest_row_on_or_before(apple_daily, 'activity_date', target)

        result = {
            'readiness_score': int(round(readiness_score)),
            'recovery_status': recovery_status,
            'confidence_score': round(confidence_score, 1),
            'sleep_score': round(component_scores['sleep_score'], 1) if component_scores['sleep_score'] is not None else None,
            'hrv_score': round(component_scores['hrv_score'], 1) if component_scores['hrv_score'] is not None else None,
            'resting_hr_score': round(component_scores['resting_hr_score'], 1) if component_scores['resting_hr_score'] is not None else None,
            'activity_load_score': round(component_scores['activity_load_score'], 1) if component_scores['activity_load_score'] is not None else None,
            'strength_load_score': round(component_scores['strength_load_score'], 1) if component_scores['strength_load_score'] is not None else None,
            'recovery_balance_score': round(component_scores['recovery_balance_score'], 1) if component_scores['recovery_balance_score'] is not None else None,
            'recommendation': recommendation,
            'limiting_factors': limiting,
            'positive_factors': positives,
            'data_quality': data_quality,
            'source_dates': source_dates,
            'weight_distribution': redistributed_weights,
            'component_reasons': {k: str(v.get('reason', '')) for k, v in component_objs.items()},
            'last_updated': datetime.now().isoformat(timespec='seconds'),
            'data_sources_used': [
                source
                for source, used in [
                    ('Brian Fit strength history', not strength.empty),
                    ('Apple activity daily', not apple_daily.empty),
                    ('Apple workouts', not apple_w.empty),
                ]
                if used
            ],
            'muscle_recovery_cards': muscle_cards,
            'activity_context': {
                'sleep_hours': float(today_row.get('sleep_hours')) if today_row is not None and not pd.isna(today_row.get('sleep_hours')) else None,
                'resting_heart_rate': float(today_row.get('resting_heart_rate')) if today_row is not None and not pd.isna(today_row.get('resting_heart_rate')) else None,
                'heart_rate_variability_ms': float(today_row.get('heart_rate_variability_ms')) if today_row is not None and not pd.isna(today_row.get('heart_rate_variability_ms')) else None,
            },
            'last_workout_load': int(round(last_strength_load)),
        }

        return result
    except Exception as exc:
        # Keep dashboard/recovery pages up even if upstream timestamps are malformed.
        return {
            'readiness_score': 50,
            'recovery_status': 'Moderate',
            'confidence_score': 30.0,
            'sleep_score': None,
            'hrv_score': None,
            'resting_hr_score': None,
            'activity_load_score': None,
            'strength_load_score': None,
            'recovery_balance_score': None,
            'recommendation': {
                'primary_recommendation': 'Moderate Session',
                'recommended_intensity_percentage': '65-75%',
                'suggested_duration': '35-50 minutes',
                'suggested_volume_adjustment': 'Reduce volume by 20%',
                'suggested_rpe_ceiling': '7.0',
                'recommended_muscle_groups': ['Core', 'Mobility'],
                'reduce_or_avoid_muscle_groups': [],
                'hydration_note': 'Target 80-120 oz water based on session duration and sweat rate.',
                'sleep_target': '7.5-9.0 hours',
                'coaching_reason': 'Limited data mode: timestamp parsing failed on one or more Apple inputs.',
                'readiness_impact': 'Fallback recommendation used due to data quality issues.',
            },
            'limiting_factors': ['Limited data mode enabled due to timestamp parsing errors.'],
            'positive_factors': ['Dashboard remained available with fallback readiness output.'],
            'data_quality': {
                'apple_data_days_available': 0,
                'sleep_coverage': 0.0,
                'hrv_coverage': 0.0,
                'resting_hr_coverage': 0.0,
                'strength_history_days': 0,
                'readiness_confidence': 30.0,
                'confidence_label': 'Limited data',
                'missing_inputs': ['Sleep', 'HRV', 'Resting HR'],
                'limited_history': True,
                'history_notes': [f'Limited-data fallback: {str(exc)}'],
            },
            'source_dates': {
                'latest_apple_activity_date': None,
                'apple_days_used': 0,
                'latest_apple_workout_start': None,
                'apple_workouts_used': 0,
                'latest_strength_date': None,
                'strength_days_used': 0,
                'target_date': str(_to_date(target_date)),
            },
            'weight_distribution': {
                'sleep_score': 0.0,
                'hrv_score': 0.0,
                'resting_hr_score': 0.0,
                'activity_load_score': 0.0,
                'strength_load_score': 0.0,
                'recovery_balance_score': 0.0,
            },
            'component_reasons': {
                'sleep_score': 'Unavailable in fallback mode.',
                'hrv_score': 'Unavailable in fallback mode.',
                'resting_hr_score': 'Unavailable in fallback mode.',
                'activity_load_score': 'Unavailable in fallback mode.',
                'strength_load_score': 'Unavailable in fallback mode.',
                'recovery_balance_score': 'Unavailable in fallback mode.',
            },
            'last_updated': datetime.now().isoformat(timespec='seconds'),
            'data_sources_used': [],
            'muscle_recovery_cards': [],
            'activity_context': {
                'sleep_hours': None,
                'resting_heart_rate': None,
                'heart_rate_variability_ms': None,
            },
            'last_workout_load': 0,
        }


def estimate_recovery_impact_from_session(
    session_sets: List[Dict[str, Any]],
    readiness_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    rows = pd.DataFrame(session_sets or [])
    if rows.empty:
        return {
            'session_load': 'Low',
            'muscle_groups_affected': [],
            'estimated_recovery_window': '12-24 hours',
            'tomorrow_readiness_impact': 'Minimal',
            'suggested_next_training_day': str(date.today() + timedelta(days=1)),
            'note': 'Estimate based on limited session data. Not a medical assessment.',
        }

    for col in ['weight_lbs', 'reps', 'rpe', 'volume']:
        if col not in rows.columns:
            rows[col] = 0
        rows[col] = _to_numeric(rows[col]).fillna(0)

    if (rows['volume'] <= 0).all():
        rows['volume'] = rows['weight_lbs'] * rows['reps']

    total_volume = float(rows['volume'].sum())
    avg_rpe = float(rows['rpe'].mean()) if not rows.empty else 0.0
    set_count = int(rows.shape[0])

    load_index = (total_volume / 2500.0) + (avg_rpe / 2.4) + (set_count / 9.0)
    if load_index >= 7.0:
        session_load = 'High'
        window = '48-72 hours'
        impact = 'Likely lower readiness tomorrow'
        next_day = date.today() + timedelta(days=2)
    elif load_index >= 4.5:
        session_load = 'Moderate'
        window = '24-48 hours'
        impact = 'Moderate readiness impact tomorrow'
        next_day = date.today() + timedelta(days=1)
    else:
        session_load = 'Low'
        window = '12-24 hours'
        impact = 'Minimal readiness impact tomorrow'
        next_day = date.today() + timedelta(days=1)

    affected: List[str] = []
    for ex in rows.get('exercise', pd.Series(dtype=str)).astype(str).tolist():
        low = ex.lower()
        for muscle, keys in MUSCLE_KEYWORDS.items():
            if any(k in low for k in keys) and muscle not in affected:
                affected.append(muscle)

    current_score = None
    if isinstance(readiness_result, dict):
        val = readiness_result.get('readiness_score')
        if val is not None:
            try:
                current_score = float(val)
            except Exception:
                current_score = None

    note = 'Session impact estimate from Brian Fit set volume and intensity. Not a medical assessment.'
    if current_score is not None and session_load == 'High':
        note += f' Current readiness {int(round(current_score))}/100 suggests conservative progression tomorrow.'

    return {
        'session_load': session_load,
        'muscle_groups_affected': affected[:6],
        'estimated_recovery_window': window,
        'tomorrow_readiness_impact': impact,
        'suggested_next_training_day': str(next_day),
        'note': note,
    }
