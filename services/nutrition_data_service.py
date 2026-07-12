from __future__ import annotations

from pathlib import Path

import pandas as pd


NUTRITION_COLUMNS = ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes']


def load_nutrition_log(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=NUTRITION_COLUMNS)
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=NUTRITION_COLUMNS)
