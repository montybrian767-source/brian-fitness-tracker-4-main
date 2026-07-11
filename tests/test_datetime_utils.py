import pandas as pd

from utils.datetime_utils import to_utc_day_bounds, to_utc_series, to_utc_timestamp


def test_to_utc_series_handles_mixed_values():
    series = to_utc_series(pd.Series(["2026-01-01 08:00:00", "bad"]))
    assert "UTC" in str(series.dtype)
    assert pd.notna(series[0])
    assert pd.isna(series[1])


def test_to_utc_timestamp_and_day_bounds_are_utc():
    ts = to_utc_timestamp("2026-03-02 10:15:00")
    assert ts.tzinfo is not None

    start, end = to_utc_day_bounds("2026-03-02T23:59:00-0500")
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert (end - start) == pd.Timedelta(days=1)
