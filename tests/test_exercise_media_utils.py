from pathlib import Path

import pandas as pd

from utils.exercise_media_utils import IMAGE_MAP_COLUMNS, load_image_map


def _clear_cache() -> None:
    load_image_map.clear()


def test_load_image_map_file_exists(tmp_path: Path):
    _clear_cache()
    path = tmp_path / "exercise_image_map.csv"
    sample = pd.DataFrame(
        [
            {
                "exercise_name": "Chest Press Machine",
                "canonical_exercise_key": "chest_press_machine",
                "primary_image": "chest_press_machine.png",
                "secondary_image": "",
                "thumbnail_image": "",
                "muscle_overlay_image": "",
                "image_status": "approved",
                "review_notes": "",
                "last_reviewed": "2026-07-12",
                "approved_by": "tester",
                "fallback_type": "",
            }
        ]
    )
    sample.to_csv(path, index=False)

    df = load_image_map(path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
    assert len(df) == 1
    assert df.iloc[0]["exercise_name"] == "Chest Press Machine"


def test_load_image_map_file_missing(tmp_path: Path):
    _clear_cache()
    missing_path = tmp_path / "does_not_exist.csv"

    df = load_image_map(missing_path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
    assert df.empty


def test_load_image_map_missing_columns(tmp_path: Path):
    _clear_cache()
    path = tmp_path / "exercise_image_map.csv"
    pd.DataFrame(
        [
            {
                "exercise_name": "Seated Row Machine",
                "primary_image": "seated_row_machine.png",
            }
        ]
    ).to_csv(path, index=False)

    df = load_image_map(path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
    assert "canonical_exercise_key" in df.columns
    assert df.iloc[0]["exercise_name"] == "Seated Row Machine"


def test_load_image_map_empty_csv(tmp_path: Path):
    _clear_cache()
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    df = load_image_map(path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
    assert df.empty


def test_load_image_map_malformed_csv(tmp_path: Path):
    _clear_cache()
    path = tmp_path / "malformed.csv"
    path.write_bytes(b"\xff\xfe\x00\x00")

    df = load_image_map(path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
    assert df.empty


def test_load_image_map_returns_expected_columns_for_any_case(tmp_path: Path):
    _clear_cache()
    path = tmp_path / "minimal.csv"
    pd.DataFrame([{"exercise_name": "Plank"}]).to_csv(path, index=False)

    df = load_image_map(path)

    assert list(df.columns) == IMAGE_MAP_COLUMNS
