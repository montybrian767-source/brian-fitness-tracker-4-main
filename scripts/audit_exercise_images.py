from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.exercise_media_utils import (
    APP_DIR,
    ASSETS_DIR,
    FALLBACK_IMAGE,
    exercise_key,
    get_image_status,
    image_exists,
    load_image_map,
    resolve_exercise_media,
)


REPORT_DIR = APP_DIR / "reports"
REPORT_PATH = REPORT_DIR / "exercise_image_audit.csv"
SUMMARY_PATH = REPORT_DIR / "exercise_image_summary.json"
DATA_DIR = APP_DIR / "data"


def _safe_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _collect_exercises() -> pd.DataFrame:
    rows: List[Dict[str, str]] = []

    db = _safe_csv(DATA_DIR / "exercise_database.csv")
    if not db.empty:
        for _, row in db.iterrows():
            rows.append(
                {
                    "exercise_name": str(row.get("exercise", "") or "").strip(),
                    "primary_muscle": str(row.get("muscle_group", "") or "").split("+")[0].strip(),
                    "equipment": str(row.get("equipment", "") or "").strip(),
                    "movement_pattern": str(row.get("movement_pattern", "") or "").strip().lower(),
                    "hint_image": str(row.get("image_file", "") or "").strip(),
                }
            )

    workouts = _safe_csv(DATA_DIR / "workouts.csv")
    if not workouts.empty:
        for _, row in workouts.iterrows():
            rows.append(
                {
                    "exercise_name": str(row.get("exercise", "") or "").strip(),
                    "primary_muscle": str(row.get("muscle_group", "") or "").split("+")[0].strip(),
                    "equipment": "",
                    "movement_pattern": "",
                    "hint_image": str(row.get("image_file", "") or "").strip(),
                }
            )

    map_df = load_image_map()
    if not map_df.empty:
        for _, row in map_df.iterrows():
            rows.append(
                {
                    "exercise_name": str(row.get("exercise_name", "") or "").strip(),
                    "primary_muscle": "",
                    "equipment": "",
                    "movement_pattern": "",
                    "hint_image": str(row.get("primary_image", "") or "").strip(),
                }
            )

    unique: Dict[str, Dict[str, str]] = {}
    for item in rows:
        name = item["exercise_name"]
        if not name:
            continue
        key = exercise_key(name)
        if key not in unique:
            unique[key] = item
            continue
        if not unique[key].get("primary_muscle") and item.get("primary_muscle"):
            unique[key]["primary_muscle"] = item["primary_muscle"]
        if not unique[key].get("equipment") and item.get("equipment"):
            unique[key]["equipment"] = item["equipment"]
        if not unique[key].get("movement_pattern") and item.get("movement_pattern"):
            unique[key]["movement_pattern"] = item["movement_pattern"]
        if not unique[key].get("hint_image") and item.get("hint_image"):
            unique[key]["hint_image"] = item["hint_image"]

    return pd.DataFrame(unique.values())


def _image_stats(path: Path) -> Tuple[int, int, float, float]:
    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        return 0, 0, 0.0, 0.0

    size_kb = round(path.stat().st_size / 1024.0, 2)
    ratio = round(width / height, 4) if height else 0.0
    return width, height, size_kb, ratio


def _file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _status_from_flags(exists: bool, configured_status: str, is_fallback: bool) -> str:
    if not exists:
        return "missing"
    if configured_status == "rejected":
        return "rejected"
    if is_fallback:
        return "fallback"
    if configured_status == "approved":
        return "approved"
    return "needs_review"


def _recommended_action(image_status: str, duplicate_count: int, low_resolution: bool, crop_risk: bool) -> str:
    if image_status == "missing":
        return "add_image"
    if image_status == "rejected":
        return "replace_image"
    if image_status == "fallback":
        return "replace_fallback_with_specific"
    if duplicate_count > 1:
        return "review_duplicate_usage"
    if low_resolution:
        return "upgrade_resolution"
    if crop_risk:
        return "replace_with_wider_composition"
    if image_status == "needs_review":
        return "review_and_approve"
    return "keep"


def build_audit() -> pd.DataFrame:
    ex_df = _collect_exercises()
    if ex_df.empty:
        return pd.DataFrame(
            columns=[
                "exercise_name",
                "canonical_exercise_key",
                "primary_muscle",
                "equipment",
                "movement_pattern",
                "current_image_path",
                "image_exists",
                "width",
                "height",
                "aspect_ratio",
                "file_size_kb",
                "extension",
                "duplicate_hash",
                "duplicate_group",
                "low_resolution",
                "extreme_aspect_ratio",
                "likely_mobile_crop_risk",
                "image_status",
                "recommended_action",
            ]
        )

    records: List[Dict[str, object]] = []
    for _, row in ex_df.iterrows():
        exercise_name = str(row.get("exercise_name", "") or "").strip()
        hint_image = str(row.get("hint_image", "") or "").strip()
        primary_muscle = str(row.get("primary_muscle", "") or "").strip()
        equipment = str(row.get("equipment", "") or "").strip()
        movement_pattern = str(row.get("movement_pattern", "") or "").strip().lower()

        resolved = resolve_exercise_media(exercise_name)
        image_name = hint_image if hint_image and image_exists(hint_image) else str(resolved.get("primary_image", "") or "")
        if not image_name:
            image_name = FALLBACK_IMAGE
        image_path = ASSETS_DIR / image_name
        exists = image_path.exists()

        width, height, size_kb, ratio = _image_stats(image_path) if exists else (0, 0, 0.0, 0.0)
        configured_status = get_image_status(exercise_name)
        fallback_level = str(resolved.get("fallback_level", "") or "")
        is_fallback = image_name == FALLBACK_IMAGE or fallback_level in {"movement_pattern", "primary_muscle", "neutral", "canonical_variation"}

        duplicate_hash = _file_hash(image_path) if exists else ""
        low_resolution = bool(exists and (width < 800 or height < 500))
        extreme_ratio = bool(ratio and (ratio < 1.1 or ratio > 2.2))
        crop_risk = bool(ratio and ratio < 1.1)
        image_status = _status_from_flags(exists, configured_status, is_fallback)

        records.append(
            {
                "exercise_name": exercise_name,
                "canonical_exercise_key": exercise_key(exercise_name),
                "primary_muscle": primary_muscle,
                "equipment": equipment,
                "movement_pattern": movement_pattern,
                "current_image_path": str(Path("assets") / "exercises" / image_name),
                "image_exists": bool(exists),
                "width": int(width),
                "height": int(height),
                "aspect_ratio": float(ratio),
                "file_size_kb": float(size_kb),
                "extension": image_path.suffix.lower().replace(".", "") if exists else "",
                "duplicate_hash": duplicate_hash,
                "low_resolution": low_resolution,
                "extreme_aspect_ratio": extreme_ratio,
                "likely_mobile_crop_risk": crop_risk,
                "image_status": image_status,
            }
        )

    out = pd.DataFrame(records)

    counts = out["duplicate_hash"].value_counts().to_dict()
    out["duplicate_group"] = [
        f"sha256:{digest[:12]}" if str(digest).strip() and int(counts.get(str(digest), 0)) > 1 else ""
        for digest in out["duplicate_hash"].tolist()
    ]

    out["recommended_action"] = [
        _recommended_action(
            str(row["image_status"]),
            int(counts.get(str(row["duplicate_hash"]), 0)),
            bool(row["low_resolution"]),
            bool(row["likely_mobile_crop_risk"]),
        )
        for _, row in out.iterrows()
    ]

    out = out[
        [
            "exercise_name",
            "canonical_exercise_key",
            "primary_muscle",
            "equipment",
            "movement_pattern",
            "current_image_path",
            "image_exists",
            "width",
            "height",
            "aspect_ratio",
            "file_size_kb",
            "extension",
            "duplicate_hash",
            "duplicate_group",
            "low_resolution",
            "extreme_aspect_ratio",
            "likely_mobile_crop_risk",
            "image_status",
            "recommended_action",
        ]
    ].sort_values("exercise_name")

    return out


def _build_summary(audit_df: pd.DataFrame) -> Dict[str, object]:
    if audit_df is None or audit_df.empty:
        return {
            "total_exercises": 0,
            "approved": 0,
            "needs_review": 0,
            "missing": 0,
            "fallback": 0,
            "duplicates": 0,
            "low_resolution": 0,
            "crop_risk": 0,
        }

    status_series = audit_df["image_status"].astype(str).str.lower()
    return {
        "total_exercises": int(len(audit_df)),
        "approved": int((status_series == "approved").sum()),
        "needs_review": int((status_series == "needs_review").sum()),
        "missing": int((status_series == "missing").sum()),
        "fallback": int((status_series == "fallback").sum()),
        "duplicates": int((audit_df["duplicate_group"].astype(str).str.strip() != "").sum()),
        "low_resolution": int(audit_df["low_resolution"].astype(bool).sum()),
        "crop_risk": int(audit_df["likely_mobile_crop_risk"].astype(bool).sum()),
    }


def _duplicate_report(audit_df: pd.DataFrame) -> List[Dict[str, object]]:
    if audit_df is None or audit_df.empty:
        return []
    merged = audit_df[audit_df["duplicate_group"].astype(str).str.strip() != ""].copy()
    if merged.empty:
        return []

    map_df = load_image_map()
    review_lookup = {
        exercise_key(str(row.get("exercise_name", ""))): str(row.get("review_notes", "") or "").lower()
        for _, row in map_df.iterrows()
    }

    rows: List[Dict[str, object]] = []
    for group, group_df in merged.groupby("duplicate_group"):
        exercise_names = sorted(group_df["exercise_name"].astype(str).tolist())
        notes = [review_lookup.get(exercise_key(name), "") for name in exercise_names]
        intentional = any("duplicate intentional" in note for note in notes)
        image_path = str(group_df.iloc[0].get("current_image_path", ""))
        rows.append(
            {
                "duplicate_group": str(group),
                "image_path": image_path,
                "exercises": exercise_names,
                "classification": "intentional" if intentional else "suspicious",
            }
        )
    return rows


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    audit_df = build_audit()
    audit_df.to_csv(REPORT_PATH, index=False)

    summary = _build_summary(audit_df)
    summary["duplicate_details"] = _duplicate_report(audit_df)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {len(audit_df)} rows to {REPORT_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
