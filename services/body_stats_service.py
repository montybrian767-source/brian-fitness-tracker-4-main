from __future__ import annotations

from pathlib import Path

import pandas as pd


BODY_COLUMNS = ['date','body_weight_lbs','goal_weight_lbs','waist_in','body_fat_pct','muscle_mass_lbs','bmi','water_pct','protein_pct','bone_mass_lbs','bmr_cal','metabolic_age','visceral_fat','lean_body_mass_lbs','notes']


def load_body_stats(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=BODY_COLUMNS)
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=BODY_COLUMNS)
