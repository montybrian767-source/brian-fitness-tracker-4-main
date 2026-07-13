from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

import utils.exercise_media_utils as media_utils


APP_DIR = media_utils.APP_DIR
ASSETS_DIR = media_utils.ASSETS_DIR
exercise_key = media_utils.exercise_key
resolve_exercise_media = media_utils.resolve_exercise_media
_load_map = getattr(media_utils, "load_image_map", None)
if callable(_load_map):
    load_image_map = _load_map
else:
    def load_image_map(path=None):
        return pd.DataFrame()


REPORT_PATH = APP_DIR / "reports" / "exercise_image_audit.csv"
SUMMARY_PATH = APP_DIR / "reports" / "exercise_image_summary.json"
MAP_PATH = APP_DIR / "data" / "exercise_image_map.csv"

PRIORITY_EXERCISES = [
    "Chest Press Machine",
    "Incline Dumbbell Press",
    "Pec Deck Fly",
    "Lat Pulldown",
    "Close Grip Pulldown",
    "Seated Row Machine",
    "Shoulder Press Machine",
    "Tricep Pushdown",
    "Cable Curl",
    "Leg Curl",
    "Leg Extension",
    "Hip Abduction",
    "Hip Adduction",
    "Treadmill",
    "Elliptical",
    "Stationary Bike",
]


def _safe_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_audit() -> pd.DataFrame:
    df = _safe_csv(REPORT_PATH)
    required = [
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
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df[required]


def _summary_counts(df: pd.DataFrame) -> Dict[str, int]:
    status = df["image_status"].astype(str).str.lower()
    return {
        "total": int(len(df)),
        "approved": int((status == "approved").sum()),
        "needs_review": int((status == "needs_review").sum()),
        "missing": int((status == "missing").sum()),
        "duplicates": int((df["duplicate_group"].astype(str).str.strip() != "").sum()),
        "low_resolution": int(df["low_resolution"].astype(str).str.lower().isin(["true", "1"]).sum()),
        "crop_risk": int(df["likely_mobile_crop_risk"].astype(str).str.lower().isin(["true", "1"]).sum()),
    }


def _persist_review(exercise_name: str, new_status: str, notes: str = "", fallback_type: str = "") -> None:
    df = load_image_map()
    key = exercise_key(exercise_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if df.empty:
        df = pd.DataFrame(
            columns=[
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
        )

    hit = df["canonical_exercise_key"].astype(str).str.lower() == key
    if not hit.any():
        resolved = resolve_exercise_media(exercise_name)
        df.loc[len(df)] = {
            "exercise_name": exercise_name,
            "canonical_exercise_key": key,
            "primary_image": str(resolved.get("primary_image", "") or ""),
            "secondary_image": str(resolved.get("secondary_image", "") or ""),
            "thumbnail_image": str(resolved.get("thumbnail_image", "") or ""),
            "muscle_overlay_image": str(resolved.get("muscle_overlay_image", "") or ""),
            "image_status": new_status,
            "review_notes": notes,
            "last_reviewed": now,
            "approved_by": "local_user",
            "fallback_type": fallback_type,
        }
    else:
        idx = df[hit].index[0]
        df.at[idx, "image_status"] = new_status
        if notes:
            df.at[idx, "review_notes"] = notes
        if fallback_type:
            df.at[idx, "fallback_type"] = fallback_type
        df.at[idx, "last_reviewed"] = now
        df.at[idx, "approved_by"] = "local_user"

    df.to_csv(MAP_PATH, index=False)
    load_image_map.clear()


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _clean_filter_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalized_text_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(["" for _ in range(len(df))], index=df.index, dtype="object")
    return df[column].map(_clean_filter_value).astype(str)


def _filter_options(df: pd.DataFrame, column: str) -> List[str]:
    values = _normalized_text_series(df, column)
    # values are normalized strings only, so sorting cannot compare mixed types.
    return ["All"] + sorted({v for v in values.tolist() if v})


def _display_value(value: object) -> str:
    text = _clean_filter_value(value)
    if not text:
        return "Unknown"
    return text


def _resolve_image_path(relative_path: str) -> Path:
    rel = str(relative_path or "").replace("\\", "/")
    if rel.startswith("assets/exercises/"):
        rel = rel.split("assets/exercises/", 1)[1]
    return ASSETS_DIR / rel


def _apply_filters(df):
    if df is None:
        return pd.DataFrame()

    cleaned = df.copy()

    for column in [
        "exercise_name",
        "canonical_exercise_key",
        "primary_muscle",
        "equipment",
        "movement_pattern",
        "image_status",
    ]:
        if column not in cleaned.columns:
            cleaned[column] = ""

        cleaned[column] = (
            cleaned[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    cleaned["priority_rank"] = pd.to_numeric(
        cleaned.get("priority_rank", pd.Series(index=cleaned.index)),
        errors="coerce",
    ).fillna(9999)

    cleaned = cleaned.sort_values(
        by=["priority_rank", "exercise_name"],
        ascending=[True, True],
        na_position="last",
        kind="stable",
    )

    return cleaned


def _render_review_actions(row: pd.Series, card_key: str) -> None:
    exercise_name = str(row["exercise_name"])
    notes = st.text_input("Audit notes", key=f"{card_key}_notes", value=str(row.get("recommended_action", "")))

    c1, c2, c3 = st.columns(3)
    if c1.button("Approve", key=f"{card_key}_approve", width="stretch"):
        _persist_review(exercise_name, "approved", notes)
        st.success(f"Approved {exercise_name}")
    if c2.button("Needs Better Image", key=f"{card_key}_needs_better", width="stretch"):
        _persist_review(exercise_name, "needs_review", notes)
        st.info(f"Marked needs review: {exercise_name}")
    if c3.button("Wrong Exercise", key=f"{card_key}_wrong", width="stretch"):
        _persist_review(exercise_name, "rejected", notes)
        st.warning(f"Marked wrong image: {exercise_name}")

    c4, c5, c6 = st.columns(3)
    if c4.button("Missing", key=f"{card_key}_missing", width="stretch"):
        _persist_review(exercise_name, "missing", notes)
    if c5.button("Use Fallback", key=f"{card_key}_fallback", width="stretch"):
        _persist_review(exercise_name, "fallback", notes, fallback_type="manual_fallback")
    if c6.button("Reject", key=f"{card_key}_reject", width="stretch"):
        _persist_review(exercise_name, "rejected", notes)

    c7, c8 = st.columns(2)
    if c7.button("Open Image Path", key=f"{card_key}_open_path", width="stretch"):
        st.code(str(_resolve_image_path(str(row.get("current_image_path", "")))))
    if c8.button("Next Exercise", key=f"{card_key}_next", width="stretch"):
        st.session_state["media_manager_next"] = True

    if str(row.get("duplicate_group", "")).strip():
        d1, d2 = st.columns(2)
        if d1.button("Mark duplicate intentional", key=f"{card_key}_dup_intent", width="stretch"):
            _persist_review(exercise_name, str(row.get("image_status", "needs_review")), "duplicate intentional")
        if d2.button("Mark duplicate needs replacement", key=f"{card_key}_dup_replace", width="stretch"):
            _persist_review(exercise_name, "needs_review", "duplicate needs replacement")


def render_exercise_media_manager_page() -> None:
    st.markdown("### Exercise Media Manager")
    st.caption("Review, approve, and manage exercise media quality without changing source image files.")

    map_df = load_image_map()
    if (not MAP_PATH.exists()) or map_df.empty:
        st.warning("Exercise image map has not been created yet. Run the image audit to create it.")
        return

    audit_df = _load_audit()
    if audit_df.empty:
        st.warning("No audit report found. Run scripts/audit_exercise_images.py first.")
        return

    summary = _summary_counts(audit_df)
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total exercises", summary["total"])
    m2.metric("Approved", summary["approved"])
    m3.metric("Needs review", summary["needs_review"])
    m4.metric("Missing", summary["missing"])
    m5.metric("Duplicates", summary["duplicates"])
    m6.metric("Low resolution", summary["low_resolution"])
    m7.metric("Crop risk", summary["crop_risk"])

    filtered = _apply_filters(audit_df)

    mode = st.radio("View Mode", ["Review", "Gallery"], horizontal=True, key="media_view_mode")

    st.markdown("### Exports")
    ex1, ex2, ex3, ex4 = st.columns(4)
    ex1.download_button("Download Full Image Audit CSV", audit_df.to_csv(index=False).encode("utf-8"), file_name="exercise_image_audit.csv")
    ex2.download_button("Download Missing Images CSV", audit_df[audit_df["image_status"].astype(str).str.lower() == "missing"].to_csv(index=False).encode("utf-8"), file_name="exercise_images_missing.csv")
    ex3.download_button("Download Needs Review CSV", audit_df[audit_df["image_status"].astype(str).str.lower() == "needs_review"].to_csv(index=False).encode("utf-8"), file_name="exercise_images_needs_review.csv")
    ex4.download_button("Download Duplicate Images CSV", audit_df[audit_df["duplicate_group"].astype(str).str.strip() != ""].to_csv(index=False).encode("utf-8"), file_name="exercise_images_duplicates.csv")

    if mode == "Review":
        if "media_manager_index" not in st.session_state:
            st.session_state["media_manager_index"] = 0

        idx = int(st.session_state.get("media_manager_index", 0))
        if st.session_state.pop("media_manager_next", False):
            idx += 1
        if filtered.empty:
            st.info("No exercises match the current filters.")
            return

        idx = max(0, min(idx, len(filtered) - 1))
        st.session_state["media_manager_index"] = idx
        row = filtered.iloc[idx]

        st.markdown(f"#### {row['exercise_name']}")
        image_path = _resolve_image_path(str(row.get("current_image_path", "")))
        if image_path.exists():
            st.image(str(image_path), width=320)
        else:
            st.warning("Image file missing")

        st.write(f"Primary muscle: {_display_value(row.get('primary_muscle', ''))}")
        st.write(f"Equipment: {_display_value(row.get('equipment', ''))}")
        st.write(f"Movement pattern: {_display_value(row.get('movement_pattern', ''))}")
        st.write(f"Resolution: {row.get('width', 0)} x {row.get('height', 0)}")
        st.write(f"File size: {row.get('file_size_kb', 0)} KB")
        st.write(f"Status: {_display_value(row.get('image_status', ''))}")
        if str(row.get("duplicate_group", "")).strip():
            st.warning(f"Duplicate group: {row['duplicate_group']}")
        st.caption(f"Audit note: {row.get('recommended_action', '')}")

        _render_review_actions(row, f"media_review_{idx}")
    else:
        st.markdown("### Gallery View")
        selected = st.multiselect("Select exercises", filtered["exercise_name"].astype(str).tolist(), key="gallery_selected")

        b1, b2, b3 = st.columns(3)
        if b1.button("Approve selected", width="stretch"):
            for item in selected:
                _persist_review(item, "approved", "batch approved")
            st.success(f"Approved {len(selected)} exercises")
        if b2.button("Mark selected needs review", width="stretch"):
            for item in selected:
                _persist_review(item, "needs_review", "batch needs review")
            st.info(f"Updated {len(selected)} exercises")
        if b3.download_button("Export selected list", filtered[filtered["exercise_name"].isin(selected)].to_csv(index=False).encode("utf-8"), file_name="exercise_media_selected.csv"):
            pass

        cols_per_row = 4
        for start in range(0, len(filtered), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                index = start + col_idx
                if index >= len(filtered):
                    continue
                row = filtered.iloc[index]
                with cols[col_idx]:
                    st.markdown(f"**{row['exercise_name']}**")
                    image_path = _resolve_image_path(str(row.get("current_image_path", "")))
                    if image_path.exists():
                        st.image(str(image_path), width=220)
                    st.caption(f"{_display_value(row.get('primary_muscle', ''))} • {_display_value(row.get('image_status', ''))}")
                    q1, q2 = st.columns(2)
                    if q1.button("Approve", key=f"gallery_approve_{index}", width="stretch"):
                        _persist_review(str(row["exercise_name"]), "approved", "gallery quick approve")
                    if q2.button("Needs Review", key=f"gallery_review_{index}", width="stretch"):
                        _persist_review(str(row["exercise_name"]), "needs_review", "gallery quick review")
