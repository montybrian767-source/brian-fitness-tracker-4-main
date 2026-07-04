from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from engines.smart_scale_engine import BODY_COLUMNS


@dataclass
class RenphoSyncResult:
    ok: bool
    message: str
    pulled: int
    duplicates: int
    invalid: int
    added: int
    candidates_df: pd.DataFrame
    fallback: bool = False


def _load_local_env() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in {"RENPHO_EMAIL", "RENPHO_PASSWORD"} and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Environment loading is best-effort only.
        return


def _friendly_auth_error(exc: Exception) -> str:
    txt = str(exc).lower()
    if any(k in txt for k in ["auth", "login", "password", "credential", "unauthorized", "forbidden"]):
        return "Renpho login failed. Please verify RENPHO_EMAIL and RENPHO_PASSWORD in your local .env file."
    return f"Renpho sync failed: {exc}"


def _extract_measurements(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        for k in ["data", "measurements", "results", "items", "list"]:
            v = payload.get(k)
            if isinstance(v, list):
                return [p for p in v if isinstance(p, dict)]
        return [payload]
    return []


def _first(m: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in m and m.get(key) not in [None, ""]:
            return m.get(key)
    return None


def _num(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def _to_lbs(weight_value: Any) -> float:
    w = _num(weight_value)
    if pd.isna(w):
        return w
    # Renpho is often metric; convert likely-kg values.
    if 20 <= w <= 140:
        return w * 2.20462
    return w


def _normalize_measurements(measurements: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for m in measurements:
        raw_date = _first(m, ["date", "datetime", "datatime", "timestamp", "time", "created_at"])
        dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(dt):
            continue

        row = {c: "" for c in BODY_COLUMNS}
        row["date"] = dt.strftime("%Y-%m-%d")
        row["body_weight_lbs"] = _to_lbs(_first(m, ["weight", "weight_kg", "weightKg", "body_weight"]))
        row["body_fat_pct"] = _num(_first(m, ["bodyfat", "body_fat", "bodyFat", "fat", "fat_percent"]))
        row["muscle_mass_lbs"] = _to_lbs(_first(m, ["muscle_mass", "muscleMass", "muscle"]))
        row["bmi"] = _num(_first(m, ["bmi"]))
        row["water_pct"] = _num(_first(m, ["water", "water_percent", "body_water"]))
        row["protein_pct"] = _num(_first(m, ["protein", "protein_percent"]))
        row["bone_mass_lbs"] = _to_lbs(_first(m, ["bone_mass", "boneMass", "bone"]))
        row["bmr_cal"] = _num(_first(m, ["bmr", "bmr_cal", "metabolism"]))
        row["visceral_fat"] = _num(_first(m, ["visceral_fat", "visceralFat", "vf"]))
        row["metabolic_age"] = _num(_first(m, ["metabolic_age", "metabolicAge", "body_age"]))
        row["lean_body_mass_lbs"] = _to_lbs(_first(m, ["lean_body_mass", "leanMass", "lbm", "fat_free_mass"]))
        row["import_source"] = "RENPHO"

        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=BODY_COLUMNS)

    df = pd.DataFrame(rows)
    for c in [
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
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df[BODY_COLUMNS]


def _get_client_and_payload(email: str, password: str) -> Any:
    mod = importlib.import_module("renpho_api")

    # Try common class constructors.
    candidates = ["RenphoApi", "RenphoClient", "Renpho"]
    last_error = None
    for cls_name in candidates:
        cls = getattr(mod, cls_name, None)
        if cls is None:
            continue
        for ctor in [
            lambda: cls(email, password),
            lambda: cls(username=email, password=password),
            lambda: cls(email=email, password=password),
        ]:
            try:
                client = ctor()
                break
            except Exception as exc:
                last_error = exc
                client = None
        if client is None:
            continue

        for login_method in ["login", "authenticate", "sign_in", "auth"]:
            meth = getattr(client, login_method, None)
            if callable(meth):
                try:
                    meth()
                except Exception as exc:
                    raise RuntimeError(_friendly_auth_error(exc)) from exc
                break

        for data_method in [
            "get_measurements",
            "measurements",
            "get_user_measurements",
            "get_data",
            "fetch_measurements",
            "list_measurements",
        ]:
            meth = getattr(client, data_method, None)
            if callable(meth):
                return meth()

    # Try module-level functions if class patterns fail.
    for func_name in ["login", "authenticate", "get_measurements", "fetch_measurements"]:
        fn = getattr(mod, func_name, None)
        if callable(fn):
            try:
                return fn(email=email, password=password)
            except TypeError:
                try:
                    return fn(email, password)
                except Exception as exc:
                    last_error = exc
            except Exception as exc:
                last_error = exc

    if last_error:
        raise RuntimeError(str(last_error))
    raise RuntimeError("Unable to locate a compatible renpho-api client interface.")


def sync_renpho_measurements(existing_df: pd.DataFrame) -> RenphoSyncResult:
    _load_local_env()

    email = os.getenv("RENPHO_EMAIL", "").strip()
    password = os.getenv("RENPHO_PASSWORD", "").strip()
    if not email or not password:
        return RenphoSyncResult(
            ok=False,
            fallback=True,
            message="Renpho credentials are missing. Add RENPHO_EMAIL and RENPHO_PASSWORD to your local .env file.",
            pulled=0,
            duplicates=0,
            invalid=0,
            added=0,
            candidates_df=pd.DataFrame(columns=BODY_COLUMNS),
        )

    try:
        payload = _get_client_and_payload(email, password)
    except ModuleNotFoundError:
        return RenphoSyncResult(
            ok=False,
            fallback=True,
            message="renpho-api is not installed. CSV import is still available as a backup.",
            pulled=0,
            duplicates=0,
            invalid=0,
            added=0,
            candidates_df=pd.DataFrame(columns=BODY_COLUMNS),
        )
    except Exception as exc:
        return RenphoSyncResult(
            ok=False,
            fallback=False,
            message=_friendly_auth_error(exc),
            pulled=0,
            duplicates=0,
            invalid=0,
            added=0,
            candidates_df=pd.DataFrame(columns=BODY_COLUMNS),
        )

    measurements = _extract_measurements(payload)
    pulled = len(measurements)

    normalized = _normalize_measurements(measurements)
    invalid = max(0, pulled - len(normalized))

    existing_dates = set(existing_df.get("date", pd.Series(dtype=str)).astype(str).dropna()) if not existing_df.empty else set()
    duplicate_mask = normalized["date"].astype(str).isin(existing_dates) if not normalized.empty else pd.Series(dtype=bool)
    duplicates = int(duplicate_mask.sum()) if not normalized.empty else 0

    candidates = normalized.loc[~duplicate_mask].drop_duplicates(subset=["date"], keep="last") if not normalized.empty else normalized
    added = len(candidates)

    if added == 0:
        return RenphoSyncResult(
            ok=True,
            fallback=False,
            message="Renpho sync completed, but no new entries were found.",
            pulled=pulled,
            duplicates=duplicates,
            invalid=invalid,
            added=0,
            candidates_df=pd.DataFrame(columns=BODY_COLUMNS),
        )

    return RenphoSyncResult(
        ok=True,
        fallback=False,
        message="Renpho sync successful.",
        pulled=pulled,
        duplicates=duplicates,
        invalid=invalid,
        added=added,
        candidates_df=candidates[BODY_COLUMNS],
    )
