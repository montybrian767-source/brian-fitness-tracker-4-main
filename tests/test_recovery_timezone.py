import pandas as pd

from engines.recovery_readiness_engine import calculate_activity_load_score


def test_activity_load_score_handles_naive_and_aware_timestamps():
    apple_daily = pd.DataFrame(
        [
            {
                "activity_date": "2026-07-10",
                "steps": 8200,
                "active_energy_kcal": 520,
                "exercise_minutes": 55,
                "average_heart_rate": 128,
            }
        ]
    )
    apple_workouts = pd.DataFrame(
        [
            {
                "start_time": "2026-07-10 09:00:00",
                "duration_minutes": 35,
                "total_energy_kcal": 260,
                "maximum_heart_rate": 151,
            },
            {
                "start_time": "2026-07-10T18:00:00Z",
                "duration_minutes": 25,
                "total_energy_kcal": 170,
                "maximum_heart_rate": 144,
            },
        ]
    )

    score = calculate_activity_load_score(
        apple_daily_data=apple_daily,
        apple_workouts=apple_workouts,
        target_date="2026-07-10",
        baselines={"baseline_28": {"steps": 8000, "active_energy_kcal": 500, "exercise_minutes": 45}},
    )

    assert score.get("available") is True
    assert score.get("score") is not None
