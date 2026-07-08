from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class CloudWriteResult:
    ok: bool
    inserted: int
    message: str
    error: str = ""


def is_cloud_configured(supabase_url: Optional[str], supabase_key: Optional[str]) -> bool:
    return bool(str(supabase_url or "").strip() and str(supabase_key or "").strip())


def _normalize_records(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        clean: Dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                clean[key] = None
            elif pd.isna(value):
                clean[key] = None
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        normalized.append(clean)
    return normalized


def _get_client(supabase_url: str, supabase_key: str):
    from supabase import create_client

    return create_client(supabase_url, supabase_key)


def insert_workout_rows(
    rows: List[Dict[str, Any]],
    supabase_url: Optional[str],
    supabase_key: Optional[str],
) -> CloudWriteResult:
    if not rows:
        return CloudWriteResult(ok=True, inserted=0, message="No rows to sync.")

    if not is_cloud_configured(supabase_url, supabase_key):
        return CloudWriteResult(
            ok=False,
            inserted=0,
            message="Supabase credentials are missing. Saved locally only.",
            error="missing_credentials",
        )

    try:
        client = _get_client(str(supabase_url).strip(), str(supabase_key).strip())
        payload = _normalize_records(rows)
        client.table("workout_log").insert(payload).execute()
        return CloudWriteResult(
            ok=True,
            inserted=len(payload),
            message=f"Synced {len(payload)} row(s) to cloud.",
        )
    except Exception as exc:
        return CloudWriteResult(
            ok=False,
            inserted=0,
            message="Cloud sync failed. Saved locally only.",
            error=str(exc),
        )


def fetch_cloud_row_count(
    supabase_url: Optional[str],
    supabase_key: Optional[str],
) -> Tuple[Optional[int], Optional[str]]:
    if not is_cloud_configured(supabase_url, supabase_key):
        return None, "missing_credentials"

    try:
        client = _get_client(str(supabase_url).strip(), str(supabase_key).strip())
        response = client.table("workout_log").select("*", count="exact", head=True).execute()
        return int(response.count or 0), None
    except Exception as exc:
        return None, str(exc)


def sync_local_csv_to_cloud(
    log_path: Path,
    supabase_url: Optional[str],
    supabase_key: Optional[str],
) -> CloudWriteResult:
    if not Path(log_path).exists():
        return CloudWriteResult(ok=True, inserted=0, message="Local log file is empty.")

    try:
        df = pd.read_csv(log_path)
    except Exception as exc:
        return CloudWriteResult(
            ok=False,
            inserted=0,
            message="Could not read local workout_log.csv.",
            error=str(exc),
        )

    if df.empty:
        return CloudWriteResult(ok=True, inserted=0, message="Local log file is empty.")

    rows = df.to_dict(orient="records")
    return insert_workout_rows(rows, supabase_url, supabase_key)
