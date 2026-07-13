from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets" / "exercises"
IMAGE_MAP_PATH = DATA_DIR / "exercise_image_map.csv"
MAP_PATH = IMAGE_MAP_PATH
FALLBACK_IMAGE = "image_coming_soon.png"
INTEL_PATH = DATA_DIR / "exercise_intelligence.json"

IMAGE_MAP_COLUMNS = [
    "exercise_name",
    "canonical_exercise_key",
    "primary_image",
    "secondary_image",
    "thumbnail_image",
    "muscle_overlay_image",
    "image_status",
    "review_notes",
    "last_reviewed",
    "approved_by",
    "fallback_type",
]


_MUSCLE_FALLBACKS: Dict[str, str] = {
    "chest": "chest_press_machine.png",
    "triceps": "tricep_pushdown.png",
    "back": "seated_row_machine.png",
    "lats": "wide_grip_lat_pulldown.png",
    "biceps": "bicep_curl.png",
    "shoulders": "shoulder_press_machine.png",
    "delts": "machine_lateral_raise.png",
    "legs": "leg_curl.png",
    "quads": "leg_extension.png",
    "hamstrings": "leg_curl.png",
    "glutes": "leg_press_machine.png",
    "calves": "standing_calf_raise.png",
    "core": "plank.png",
    "abs": "crunch.png",
    "forearms": "hammer_curl.png",
}


_MOVEMENT_FALLBACKS: Dict[str, str] = {
    "push": "chest_press_machine.png",
    "pull": "seated_row_machine.png",
    "squat": "squat_barbell.png",
    "hinge": "dumbbell_lunge.png",
    "core": "plank.png",
    "cardio": "image_coming_soon.png",
}


_VIEW_TO_COLUMN = {
    "primary": "primary_image",
    "secondary": "secondary_image",
    "thumbnail": "thumbnail_image",
    "overlay": "muscle_overlay_image",
}


def normalize_exercise_name(name: str) -> str:
    text = str(name or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def exercise_key(name: str) -> str:
    return normalize_exercise_name(name).replace(" ", "_")


def _normalize_map_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=IMAGE_MAP_COLUMNS)

    out = df.copy()
    if "exercise" in out.columns and "exercise_name" not in out.columns:
        out["exercise_name"] = out["exercise"]
    if "image_file" in out.columns and "primary_image" not in out.columns:
        out["primary_image"] = out["image_file"]
    if "status" in out.columns and "image_status" not in out.columns:
        out["image_status"] = out["status"]
    if "notes" in out.columns and "review_notes" not in out.columns:
        out["review_notes"] = out["notes"]

    for col in IMAGE_MAP_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    out["exercise_name"] = out["exercise_name"].astype(str)
    out["canonical_exercise_key"] = out["canonical_exercise_key"].astype(str)
    missing_key = out["canonical_exercise_key"].str.strip().eq("")
    if missing_key.any():
        out.loc[missing_key, "canonical_exercise_key"] = out.loc[missing_key, "exercise_name"].map(exercise_key)

    status_missing = out["image_status"].astype(str).str.strip().eq("")
    if status_missing.any():
        out.loc[status_missing, "image_status"] = "needs_review"

    return out[IMAGE_MAP_COLUMNS]


@st.cache_data(ttl=300, show_spinner=False)
def load_image_map(path: str | Path | None = None) -> pd.DataFrame:
    map_path = Path(path) if path else IMAGE_MAP_PATH

    if not map_path.exists():
        return pd.DataFrame(columns=IMAGE_MAP_COLUMNS)

    try:
        raw_df = pd.read_csv(map_path)
    except Exception:
        return pd.DataFrame(columns=IMAGE_MAP_COLUMNS)

    df = _normalize_map_frame(raw_df)
    for column in IMAGE_MAP_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[IMAGE_MAP_COLUMNS].copy()

    df["exercise_name"] = df["exercise_name"].fillna("").astype(str)
    df["canonical_exercise_key"] = df["canonical_exercise_key"].fillna("").astype(str)
    return df


def clear_media_cache() -> None:
    load_image_map.clear()
    _map_lookup.cache_clear()


def _infer_movement_pattern(name: str) -> str:
    token = exercise_key(name)
    if any(key in token for key in ["press", "pushdown", "extension", "fly"]):
        return "push"
    if any(key in token for key in ["row", "pulldown", "pull", "curl"]):
        return "pull"
    if any(key in token for key in ["squat", "lunge", "leg_press", "leg_extension"]):
        return "squat"
    if any(key in token for key in ["deadlift", "hinge", "bridge"]):
        return "hinge"
    if any(key in token for key in ["plank", "crunch", "twist"]):
        return "core"
    if any(key in token for key in ["bike", "elliptical", "treadmill", "run", "walk"]):
        return "cardio"
    return "general"


@lru_cache(maxsize=1)
def _exercise_db() -> pd.DataFrame:
    path = DATA_DIR / "exercise_database.csv"
    if not path.exists():
        return pd.DataFrame(columns=["exercise", "muscle_group", "equipment", "movement_pattern"])
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=["exercise", "muscle_group", "equipment", "movement_pattern"])
    if "exercise" not in df.columns:
        return pd.DataFrame(columns=["exercise", "muscle_group", "equipment", "movement_pattern"])
    if "movement_pattern" not in df.columns:
        df["movement_pattern"] = df["exercise"].astype(str).map(_infer_movement_pattern)
    return df


@lru_cache(maxsize=1)
def _movement_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not INTEL_PATH.exists():
        return out
    try:
        payload = json.loads(INTEL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return out
    profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
    templates = payload.get("templates", {}) if isinstance(payload, dict) else {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        movement = str(profile.get("movement_pattern", "") or "").strip().lower()
        template_name = str(profile.get("template", "") or "").strip()
        if not movement and template_name and isinstance(templates.get(template_name), dict):
            movement = str(templates.get(template_name, {}).get("movement_pattern", "") or "").strip().lower()
        if movement:
            out[exercise_key(name)] = movement
    return out


def _exercise_meta(name: str) -> Dict[str, str]:
    key = exercise_key(name)
    db = _exercise_db()
    if db.empty:
        return {"primary_muscle": "", "equipment": "", "movement_pattern": _movement_map().get(key, _infer_movement_pattern(name))}
    hit = db[db["exercise"].astype(str).map(exercise_key) == key]
    if hit.empty:
        return {"primary_muscle": "", "equipment": "", "movement_pattern": _movement_map().get(key, _infer_movement_pattern(name))}
    row = hit.iloc[0]
    muscle_group = str(row.get("muscle_group", "") or "")
    primary = muscle_group.split("+")[0].strip()
    movement = str(row.get("movement_pattern", "") or "").strip().lower() or _movement_map().get(key, _infer_movement_pattern(name))
    return {
        "primary_muscle": primary,
        "equipment": str(row.get("equipment", "") or "").strip(),
        "movement_pattern": movement,
    }


def _map_df() -> pd.DataFrame:
    return load_image_map()


@lru_cache(maxsize=1)
def _map_lookup() -> Dict[str, Dict[str, str]]:
    df = _map_df()
    lookup: Dict[str, Dict[str, str]] = {}
    for _, row in df.iterrows():
        name = normalize_exercise_name(row.get("exercise_name", ""))
        key = str(row.get("canonical_exercise_key", "")).strip().lower()
        payload = {
            "primary_image": str(row.get("primary_image", "") or "").strip(),
            "secondary_image": str(row.get("secondary_image", "") or "").strip(),
            "thumbnail_image": str(row.get("thumbnail_image", "") or "").strip(),
            "muscle_overlay_image": str(row.get("muscle_overlay_image", "") or "").strip(),
            "image_status": str(row.get("image_status", "") or "").strip().lower(),
            "review_notes": str(row.get("review_notes", "") or "").strip(),
            "fallback_type": str(row.get("fallback_type", "") or "").strip().lower(),
        }
        if name:
            lookup[name] = payload
        if key:
            lookup[key] = payload
    return lookup


def image_exists(path: str | Path) -> bool:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.exists()
    return (ASSETS_DIR / candidate).exists() or candidate.exists()


def fallback_image_for_muscle(muscle_group: str) -> str:
    text = normalize_exercise_name(muscle_group)
    for token, image in _MUSCLE_FALLBACKS.items():
        if token in text and image_exists(image):
            return image
    return FALLBACK_IMAGE


def _fallback_for_movement(movement_pattern: str) -> str:
    movement = str(movement_pattern or "").strip().lower()
    image = _MOVEMENT_FALLBACKS.get(movement, FALLBACK_IMAGE)
    return image if image_exists(image) else FALLBACK_IMAGE


def _find_by_same_pattern(movement_pattern: str) -> str:
    movement = str(movement_pattern or "").strip().lower()
    if not movement:
        return ""
    for _, row in _map_df().iterrows():
        status = str(row.get("image_status", "") or "").strip().lower()
        if status not in {"approved", "needs_review"}:
            continue
        candidate_name = str(row.get("exercise_name", "") or "").strip()
        meta = _exercise_meta(candidate_name)
        if meta.get("movement_pattern", "") != movement:
            continue
        image_name = str(row.get("primary_image", "") or "").strip()
        if image_name and image_exists(image_name):
            return image_name
    return ""


def _find_by_same_muscle(muscle: str) -> str:
    target = normalize_exercise_name(muscle)
    if not target:
        return ""
    for _, row in _map_df().iterrows():
        status = str(row.get("image_status", "") or "").strip().lower()
        if status not in {"approved", "needs_review"}:
            continue
        candidate_name = str(row.get("exercise_name", "") or "").strip()
        meta = _exercise_meta(candidate_name)
        candidate_muscle = normalize_exercise_name(meta.get("primary_muscle", ""))
        if not candidate_muscle or candidate_muscle != target:
            continue
        image_name = str(row.get("primary_image", "") or "").strip()
        if image_name and image_exists(image_name):
            return image_name
    return ""


def get_image_status(name: str) -> str:
    key_name = normalize_exercise_name(name)
    payload = _map_lookup().get(key_name) or _map_lookup().get(exercise_key(name)) or {}
    status = str(payload.get("image_status", "") or "").strip().lower()
    return status or "needs_review"


def resolve_exercise_media(name: str) -> Dict[str, str]:
    """Resolve media with strict fallback ordering and no unrelated image selection."""
    key_name = normalize_exercise_name(name)
    payload = _map_lookup().get(key_name) or _map_lookup().get(exercise_key(name)) or {}
    meta = _exercise_meta(name)

    status = str(payload.get("image_status", "") or "").strip().lower() or "needs_review"
    primary = str(payload.get("primary_image", "") or "").strip()
    secondary = str(payload.get("secondary_image", "") or "").strip()
    thumbnail = str(payload.get("thumbnail_image", "") or "").strip()
    overlay = str(payload.get("muscle_overlay_image", "") or "").strip()

    # 1. exact approved exercise image
    if status == "approved" and primary and image_exists(primary):
        return {
            "primary_image": primary,
            "secondary_image": secondary if image_exists(secondary) else "",
            "thumbnail_image": thumbnail if image_exists(thumbnail) else primary,
            "muscle_overlay_image": overlay if image_exists(overlay) else "",
            "image_status": status,
            "fallback_level": "exact_approved",
        }

    # 2. exact needs-review image
    if status == "needs_review" and primary and image_exists(primary):
        return {
            "primary_image": primary,
            "secondary_image": secondary if image_exists(secondary) else "",
            "thumbnail_image": thumbnail if image_exists(thumbnail) else primary,
            "muscle_overlay_image": overlay if image_exists(overlay) else "",
            "image_status": status,
            "fallback_level": "exact_needs_review",
        }

    # 3. canonical exercise variation (same canonical key prefix)
    own_key = exercise_key(name)
    own_prefix = own_key.split("_")[0] if own_key else ""
    if own_prefix:
        for _, row in _map_df().iterrows():
            status_row = str(row.get("image_status", "") or "").strip().lower()
            if status_row not in {"approved", "needs_review"}:
                continue
            candidate_key = str(row.get("canonical_exercise_key", "") or "").strip().lower()
            if not candidate_key.startswith(own_prefix):
                continue
            candidate_image = str(row.get("primary_image", "") or "").strip()
            if candidate_image and image_exists(candidate_image):
                return {
                    "primary_image": candidate_image,
                    "secondary_image": "",
                    "thumbnail_image": candidate_image,
                    "muscle_overlay_image": "",
                    "image_status": "fallback",
                    "fallback_level": "canonical_variation",
                }

    # 4. same movement pattern
    pattern_image = _find_by_same_pattern(meta.get("movement_pattern", ""))
    if pattern_image:
        return {
            "primary_image": pattern_image,
            "secondary_image": "",
            "thumbnail_image": pattern_image,
            "muscle_overlay_image": "",
            "image_status": "fallback",
            "fallback_level": "movement_pattern",
        }

    # 5. same primary muscle
    muscle_image = _find_by_same_muscle(meta.get("primary_muscle", ""))
    if muscle_image:
        return {
            "primary_image": muscle_image,
            "secondary_image": "",
            "thumbnail_image": muscle_image,
            "muscle_overlay_image": "",
            "image_status": "fallback",
            "fallback_level": "primary_muscle",
        }

    # 6. neutral fallback image
    movement_fallback = _fallback_for_movement(meta.get("movement_pattern", ""))
    muscle_fallback = fallback_image_for_muscle(meta.get("primary_muscle", ""))
    neutral = movement_fallback if movement_fallback and movement_fallback != FALLBACK_IMAGE else muscle_fallback
    if not neutral or not image_exists(neutral):
        neutral = FALLBACK_IMAGE

    return {
        "primary_image": neutral,
        "secondary_image": "",
        "thumbnail_image": neutral,
        "muscle_overlay_image": "",
        "image_status": "fallback",
        "fallback_level": "neutral",
    }


def resolve_exercise_image(name: str, view: str = "primary") -> str:
    payload = resolve_exercise_media(name)
    column = _VIEW_TO_COLUMN.get(str(view or "").strip().lower(), "primary_image")
    candidate = str(payload.get(column, "") or "").strip()
    if candidate and image_exists(candidate):
        return candidate
    if column != "primary_image":
        primary = str(payload.get("primary_image", "") or "").strip()
        if primary and image_exists(primary):
            return primary
    return FALLBACK_IMAGE


def resolve_thumbnail(name: str) -> str:
    return resolve_exercise_image(name, view="thumbnail")


def resolve_primary_image(name: str) -> str:
    return resolve_exercise_image(name, view="primary")


def resolve_secondary_image(name: str) -> str:
    return resolve_exercise_image(name, view="secondary")


def resolve_muscle_overlay(name: str) -> str:
    return resolve_exercise_image(name, view="overlay")
