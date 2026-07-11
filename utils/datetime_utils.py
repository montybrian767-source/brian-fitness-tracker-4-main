from __future__ import annotations

from typing import Any, Optional, Tuple

import pandas as pd


def to_utc_series(series: Any) -> pd.Series:
    return pd.to_datetime(series, errors='coerce', utc=True)


def to_utc_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize('UTC')
    return ts.tz_convert('UTC')


def to_utc_day_bounds(value: Any) -> Tuple[pd.Timestamp, pd.Timestamp]:
    start = to_utc_timestamp(value).normalize()
    return start, start + pd.Timedelta(days=1)


def to_local_display_time(value: Any, timezone_name: Optional[str] = None) -> str:
    ts = pd.to_datetime(value, errors='coerce', utc=True)
    if pd.isna(ts):
        return 'Unknown'
    if timezone_name:
        try:
            ts = ts.tz_convert(timezone_name)
            return ts.strftime('%Y-%m-%d %H:%M %Z')
        except Exception:
            return ts.strftime('%Y-%m-%d %H:%M UTC')
    return ts.strftime('%Y-%m-%d %H:%M UTC')
