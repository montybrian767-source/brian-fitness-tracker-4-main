from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

import pandas as pd


BODY_COLUMNS = [
    "date",
    "body_weight_lbs",
    "goal_weight_lbs",
    "waist_in",
    "body_fat_pct",
    "muscle_mass_lbs",
    "bmi",
    "water_pct",
    "protein_pct",
    "bone_mass_lbs",
    "bmr_cal",
    "metabolic_age",
    "visceral_fat",
    "lean_body_mass_lbs",
    "notes",
    "import_source",
]

CANONICAL_IMPORT_FIELDS = [
    "date",
    "body_weight_lbs",
    "body_fat_pct",
    "muscle_mass_lbs",
    "bmi",
    "water_pct",
    "protein_pct",
    "bone_mass_lbs",
    "bmr_cal",
    "visceral_fat",
    "metabolic_age",
    "lean_body_mass_lbs",
]

FIELD_LABELS = {
    "date": "Date",
    "body_weight_lbs": "Weight",
    "body_fat_pct": "Body Fat %",
    "muscle_mass_lbs": "Muscle Mass",
    "bmi": "BMI",
    "water_pct": "Water %",
    "protein_pct": "Protein %",
    "bone_mass_lbs": "Bone Mass",
    "bmr_cal": "BMR",
    "visceral_fat": "Visceral Fat",
    "metabolic_age": "Metabolic Age",
    "lean_body_mass_lbs": "Lean Body Mass",
}

ALIASES = {
    "date": ["date", "weigh in date", "measurement date", "timestamp", "time"],
    "body_weight_lbs": ["weight", "body weight", "weight lb", "weight lbs", "weight (lb)", "weight (lbs)", "weight(lb)"],
    "body_fat_pct": ["body fat", "body fat %", "fat %", "fat percentage", "bodyfat", "body fat(%)"],
    "muscle_mass_lbs": ["muscle mass", "muscle", "skeletal muscle", "muscle mass lb", "muscle mass(lb)"],
    "bmi": ["bmi", "body mass index"],
    "water_pct": ["water", "water %", "body water", "body water %", "hydration", "body water(%)"],
    "protein_pct": ["protein", "protein %", "protein ratio", "protein (%)"],
    "bone_mass_lbs": ["bone mass", "bone", "bone mass lb", "bone mass(lb)"],
    "bmr_cal": ["bmr", "bmr cal", "basal metabolic rate", "metabolism", "kcal", "bmr(kcal)"],
    "visceral_fat": ["visceral fat", "visceral", "vf"],
    "metabolic_age": ["metabolic age", "body age"],
    "lean_body_mass_lbs": ["lean body mass", "lbm", "fat free mass", "lean mass"],
}


@dataclass
class ImportPreview:
    records_found: int
    date_range: str
    duplicate_entries: int
    new_entries: int
    invalid_rows: int
    source_columns: List[str]
    auto_mapping: Dict[str, str]
    unmapped_columns: List[str]
    preview_df: pd.DataFrame
    candidates_df: pd.DataFrame


def _normalize(name: str) -> str:
    s = str(name).strip().lower()
    for ch in ["%", "(", ")", "[", "]", "-", "_"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def read_uploaded_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(file_bytes))

    # Normalize headers/values from vendor exports before mapping.
    df.columns = [str(c).strip() for c in df.columns]
    df = df.replace({"--": pd.NA, " -- ": pd.NA})

    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA})

    return df


def infer_column_mapping(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    normalized = {c: _normalize(c) for c in columns}
    mapping: Dict[str, str] = {}

    for canonical, alias_list in ALIASES.items():
        for src, src_norm in normalized.items():
            if canonical in mapping:
                break
            if src_norm == _normalize(canonical) or src_norm in [_normalize(a) for a in alias_list]:
                mapping[canonical] = src

    used_sources = set(mapping.values())
    unmapped = [c for c in columns if c not in used_sources]
    return mapping, unmapped


def _build_standardized(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    out = pd.DataFrame(columns=BODY_COLUMNS)
    out["goal_weight_lbs"] = ""
    out["waist_in"] = ""
    out["notes"] = ""
    out["import_source"] = "CSV Import"

    for canonical in CANONICAL_IMPORT_FIELDS:
        src = mapping.get(canonical)
        if src and src in df.columns:
            out[canonical] = df[src]
        elif canonical not in out.columns:
            out[canonical] = ""

    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    numeric_cols = [
        "body_weight_lbs",
        "body_fat_pct",
        "muscle_mass_lbs",
        "bmi",
        "water_pct",
        "protein_pct",
        "bone_mass_lbs",
        "bmr_cal",
        "visceral_fat",
        "metabolic_age",
        "lean_body_mass_lbs",
    ]
    for col in numeric_cols:
        out[col] = _to_numeric(out[col])

    out = out[BODY_COLUMNS]
    return out


def analyze_import(df_import_raw: pd.DataFrame, df_existing: pd.DataFrame, mapping: Dict[str, str], import_source: str = "CSV Import") -> ImportPreview:
    standardized = _build_standardized(df_import_raw, mapping)
    standardized["import_source"] = str(import_source or "Unknown")

    records_found = len(standardized)

    invalid_date = standardized["date"].isna() | (standardized["date"].astype(str).str.strip() == "")
    metric_cols = [
        c
        for c in standardized.columns
        if c not in ["date", "goal_weight_lbs", "waist_in", "notes", "import_source"]
    ]
    no_numeric = standardized[metric_cols].isna().all(axis=1)
    invalid_rows_mask = invalid_date | no_numeric
    invalid_rows = int(invalid_rows_mask.sum())

    valid = standardized.loc[~invalid_rows_mask].copy()
    valid["date"] = valid["date"].astype(str)

    existing_dates = set()
    if not df_existing.empty and "date" in df_existing.columns:
        existing_dates = set(df_existing["date"].astype(str).dropna())

    duplicate_mask = valid["date"].isin(existing_dates)
    duplicate_entries = int(duplicate_mask.sum())

    deduped = valid.loc[~duplicate_mask].drop_duplicates(subset=["date"], keep="last").copy()
    new_entries = len(deduped)

    date_values = pd.to_datetime(valid["date"], errors="coerce").dropna().sort_values()
    if date_values.empty:
        date_range = "N/A"
    else:
        date_range = f"{date_values.iloc[0].strftime('%Y-%m-%d')} to {date_values.iloc[-1].strftime('%Y-%m-%d')}"

    preview_df = deduped.head(10).copy()
    auto_mapping, unmapped_columns = infer_column_mapping(list(df_import_raw.columns))

    return ImportPreview(
        records_found=records_found,
        date_range=date_range,
        duplicate_entries=duplicate_entries,
        new_entries=new_entries,
        invalid_rows=invalid_rows,
        source_columns=list(df_import_raw.columns),
        auto_mapping=auto_mapping,
        unmapped_columns=unmapped_columns,
        preview_df=preview_df,
        candidates_df=deduped,
    )


def apply_import(df_existing: pd.DataFrame, candidates_df: pd.DataFrame) -> pd.DataFrame:
    if df_existing.empty:
        base = pd.DataFrame(columns=BODY_COLUMNS)
    else:
        base = df_existing.copy()
        for col in BODY_COLUMNS:
            if col not in base.columns:
                base[col] = ""
        if "import_source" in base.columns:
            src = base["import_source"].astype(str)
            missing = src.str.strip().eq("") | src.str.lower().eq("nan")
            if missing.any():
                base.loc[missing, "import_source"] = "Manual"
        base = base[BODY_COLUMNS]

    if "import_source" not in candidates_df.columns:
        candidates_df = candidates_df.copy()
        candidates_df["import_source"] = "Unknown"

    out = pd.concat([base, candidates_df[BODY_COLUMNS]], ignore_index=True)
    out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return out


def dashboard_body_metrics(df_body: pd.DataFrame) -> Dict[str, str]:
    if df_body.empty:
        return {
            "latest_weight": "-",
            "weekly_weight_change": "-",
            "body_fat_trend": "-",
            "muscle_mass_trend": "-",
            "last_weigh_in_date": "-",
            "ai_summary": "No smart scale data imported yet.",
        }

    d = df_body.copy()
    d["date"] = pd.to_datetime(d.get("date"), errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date")
    if d.empty:
        return {
            "latest_weight": "-",
            "weekly_weight_change": "-",
            "body_fat_trend": "-",
            "muscle_mass_trend": "-",
            "last_weigh_in_date": "-",
            "ai_summary": "No valid body dates available.",
        }

    source_norm = d.get("import_source", pd.Series("", index=d.index)).astype(str).str.strip().str.upper()
    preferred_sources = {"RENPHO", "CSV IMPORT"}
    preferred_rows = d[source_norm.isin(preferred_sources)].copy()

    def _filter_scale_outliers(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        w = pd.to_numeric(df.get("body_weight_lbs", pd.Series(dtype=float)), errors="coerce")
        valid = w.notna() & (w > 0)
        if valid.sum() < 3:
            return df.loc[valid].copy() if valid.any() else df

        median_weight = float(w.loc[valid].median())
        max_deviation = max(40.0, median_weight * 0.15)
        non_outlier = valid & ((w - median_weight).abs() <= max_deviation)
        filtered = df.loc[non_outlier].copy()

        # If filtering is too aggressive, keep original valid rows.
        if filtered.empty:
            return df.loc[valid].copy()
        return filtered

    # If valid smart-scale rows exist, use them for latest weight and trends.
    if not preferred_rows.empty:
        filtered_scale_rows = _filter_scale_outliers(preferred_rows)
        working = filtered_scale_rows if not filtered_scale_rows.empty else preferred_rows
    else:
        working = d

    weights = pd.to_numeric(working.get("body_weight_lbs", pd.Series(dtype=float)), errors="coerce")
    valid_weight_mask = weights.notna() & (weights > 0)
    latest = working.loc[valid_weight_mask].iloc[-1] if valid_weight_mask.any() else working.iloc[-1]
    last_date = latest["date"].strftime("%Y-%m-%d")

    def _trend(col: str, suffix: str = ""):
        s = pd.to_numeric(working.get(col, pd.Series(dtype=float)), errors="coerce").dropna()
        if len(s) < 2:
            return "-", "→"
        delta = float(s.iloc[-1] - s.iloc[0])
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        if abs(delta) < 0.01:
            return f"0{suffix}", arrow
        return f"{delta:+.1f}{suffix}", arrow

    latest_weight = pd.to_numeric(pd.Series([latest.get("body_weight_lbs")]), errors="coerce").iloc[0]
    latest_weight_text = "-" if pd.isna(latest_weight) else f"{latest_weight:.1f} lbs"

    week_cut = latest["date"] - pd.Timedelta(days=7)
    w = working[working["date"] >= week_cut].copy()
    if len(w) >= 2:
        ws = pd.to_numeric(w.get("body_weight_lbs", pd.Series(dtype=float)), errors="coerce").dropna()
        weekly_change = "-" if len(ws) < 2 else f"{(ws.iloc[-1] - ws.iloc[0]):+.1f} lbs"
    else:
        weekly_change = "-"

    month_cut = latest["date"] - pd.Timedelta(days=30)
    m = working[working["date"] >= month_cut].copy()
    if len(m) >= 2:
        ms = pd.to_numeric(m.get("body_weight_lbs", pd.Series(dtype=float)), errors="coerce").dropna()
        monthly_change = "-" if len(ms) < 2 else f"{(ms.iloc[-1] - ms.iloc[0]):+.1f} lbs"
    else:
        monthly_change = "-"

    bf_change, bf_arrow = _trend("body_fat_pct", "%")
    mm_change, mm_arrow = _trend("muscle_mass_lbs", " lbs")

    hydration = pd.to_numeric(working.get("water_pct", pd.Series(dtype=float)), errors="coerce").dropna()
    hydration_note = "Hydration trend unavailable."
    if len(hydration) >= 2:
        delta = hydration.iloc[-1] - hydration.iloc[0]
        if delta > 0.2:
            hydration_note = "Hydration trend is improving."
        elif delta < -0.2:
            hydration_note = "Hydration trend is declining."
        else:
            hydration_note = "Hydration trend is stable."

    observations = []
    if weekly_change != "-":
        if weekly_change.startswith("+"):
            observations.append("Weight is increasing this week.")
        elif weekly_change.startswith("-"):
            observations.append("Weight is decreasing this week.")
        else:
            observations.append("Weight is stable this week.")
    if monthly_change != "-":
        if monthly_change.startswith("+"):
            observations.append("Weight is increasing this month.")
        elif monthly_change.startswith("-"):
            observations.append("Weight is decreasing this month.")
        else:
            observations.append("Weight is stable this month.")
    if bf_change != "-":
        observations.append("Body fat is decreasing." if bf_arrow == "↓" else "Body fat is increasing." if bf_arrow == "↑" else "Body fat is stable.")
    if mm_change != "-":
        observations.append("Muscle mass is increasing." if mm_arrow == "↑" else "Muscle mass is decreasing." if mm_arrow == "↓" else "Muscle mass is stable.")
    observations.append(hydration_note)

    ai_summary = " ".join(observations[:4])

    return {
        "latest_weight": latest_weight_text,
        "weekly_weight_change": weekly_change,
        "monthly_weight_change": monthly_change,
        "body_fat_trend": bf_change,
        "muscle_mass_trend": mm_change,
        "last_weigh_in_date": last_date,
        "ai_summary": ai_summary,
    }
