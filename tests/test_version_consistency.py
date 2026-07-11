from pathlib import Path

from config.version import APP_VERSION, BUILD_LABEL, DISPLAY_KICKER, DISPLAY_NAME


def test_version_constants_are_release_aligned():
    assert APP_VERSION == "8.0.1"
    assert "X.20.1" in BUILD_LABEL
    assert DISPLAY_NAME in DISPLAY_KICKER


def test_no_legacy_release_labels_in_primary_pages():
    app_text = Path("app.py").read_text(encoding="utf-8")
    apple_text = Path("pages/apple_activity.py").read_text(encoding="utf-8")

    legacy_tokens = [
        "Brian Fit 7.4",
        "Brian Fit 7.5",
        "Brian Fit 8.0 • X.20 Adaptive AI Coach",
        "Brian Fitness Tracker X",
    ]
    for token in legacy_tokens:
        assert token not in app_text
    assert "Brian Fit 7.4" not in apple_text
