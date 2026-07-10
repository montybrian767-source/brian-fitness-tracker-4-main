#!/usr/bin/env python
from __future__ import annotations

from datetime import date

import pandas as pd

from engines.recovery_readiness_engine import calculate_activity_load_score, calculate_daily_readiness


def _baseline() -> dict:
    return {
        'baseline_28': {
            'steps': 8000,
            'active_energy_kcal': 500,
            'exercise_minutes': 35,
        }
    }


def _apple_daily() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'activity_date': '2026-07-10',
                'sleep_hours': 7.5,
                'resting_heart_rate': 57,
                'heart_rate_variability_ms': 52,
                'active_energy_kcal': 520,
                'exercise_minutes': 41,
                'steps': 9100,
                'average_heart_rate': 116,
            }
        ]
    )


def test_activity_load_with_utc_workout_and_naive_target_date() -> None:
    workouts = pd.DataFrame(
        [
            {
                'start_time': '2026-07-10T14:30:00Z',
                'end_time': '2026-07-10T15:10:00Z',
                'duration_minutes': 40,
                'total_energy_kcal': 320,
                'maximum_heart_rate': 161,
            }
        ]
    )
    result = calculate_activity_load_score(
        apple_daily_data=_apple_daily(),
        apple_workouts=workouts,
        target_date=date(2026, 7, 10),
        baselines=_baseline(),
    )
    assert result['available'] is True
    assert result['score'] is not None


def test_activity_load_with_aware_target_date() -> None:
    workouts = pd.DataFrame(
        [
            {
                'start_time': '2026-07-10T23:15:00+00:00',
                'duration_minutes': 30,
                'total_energy_kcal': 240,
                'maximum_heart_rate': 150,
            }
        ]
    )
    target = pd.Timestamp('2026-07-10T18:30:00-05:00')
    result = calculate_activity_load_score(
        apple_daily_data=_apple_daily(),
        apple_workouts=workouts,
        target_date=target,
        baselines=_baseline(),
    )
    assert result['available'] is True
    assert result['score'] is not None


def test_activity_load_with_invalid_and_mixed_timestamps() -> None:
    workouts = pd.DataFrame(
        [
            {'start_time': 'not-a-date', 'duration_minutes': 20, 'total_energy_kcal': 100, 'maximum_heart_rate': 130},
            {'start_time': '2026-07-10 09:00:00', 'duration_minutes': 35, 'total_energy_kcal': 280, 'maximum_heart_rate': 152},
            {'start_time': '2026-07-10T17:00:00Z', 'duration_minutes': 25, 'total_energy_kcal': 170, 'maximum_heart_rate': 146},
            {'start_time': None, 'duration_minutes': 10, 'total_energy_kcal': 50, 'maximum_heart_rate': 120},
        ]
    )
    result = calculate_activity_load_score(
        apple_daily_data=_apple_daily(),
        apple_workouts=workouts,
        target_date='2026-07-10',
        baselines=_baseline(),
    )
    assert result['score'] is not None
    assert result['available'] is True


def test_activity_load_with_empty_workouts() -> None:
    workouts = pd.DataFrame(columns=['start_time', 'duration_minutes', 'total_energy_kcal', 'maximum_heart_rate'])
    result = calculate_activity_load_score(
        apple_daily_data=_apple_daily(),
        apple_workouts=workouts,
        target_date='2026-07-10',
        baselines=_baseline(),
    )
    assert result['score'] is not None


def test_daily_readiness_fallback_does_not_crash_on_bad_apple_payload() -> None:
    # Mixed invalid timestamps and missing start_time should not crash readiness.
    apple_workouts = pd.DataFrame(
        [
            {'start_time': 'bad', 'duration_minutes': 30},
            {'start_time': None, 'duration_minutes': 10},
            {'start_time': '2026-07-10T11:00:00Z', 'duration_minutes': 25, 'total_energy_kcal': 150},
        ]
    )
    result = calculate_daily_readiness(
        apple_daily_data=pd.DataFrame(columns=['activity_date']),
        apple_workouts=apple_workouts,
        strength_workouts=pd.DataFrame(columns=['date', 'exercise', 'day', 'volume', 'rpe', 'set_number', 'reps', 'weight_lbs']),
        target_date=pd.Timestamp('2026-07-10T12:00:00-04:00'),
    )
    assert isinstance(result, dict)
    assert 'readiness_score' in result
    assert 'recovery_status' in result


def run_all() -> None:
    tests = [
        test_activity_load_with_utc_workout_and_naive_target_date,
        test_activity_load_with_aware_target_date,
        test_activity_load_with_invalid_and_mixed_timestamps,
        test_activity_load_with_empty_workouts,
        test_daily_readiness_fallback_does_not_crash_on_bad_apple_payload,
    ]
    for test in tests:
        test()
        print(f'PASS: {test.__name__}')


if __name__ == '__main__':
    run_all()
    print('All recovery/readiness timezone regression tests passed.')
