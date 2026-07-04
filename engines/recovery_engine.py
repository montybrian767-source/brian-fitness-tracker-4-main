from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd


RECOVERY_COLUMNS = [
	"timestamp",
	"sleep_hours",
	"sleep_quality",
	"muscle_soreness",
	"energy_level",
	"stress_level",
	"hydration_oz",
	"previous_workout_intensity",
	"calories",
	"protein_g",
	"body_weight_lbs",
	"body_fat_pct",
	"recovery_score",
	"recovery_pct",
	"recovery_status",
	"readiness_color",
	"recommendation",
]


def _to_float(value, default=0.0):
	try:
		if value == "":
			return float(default)
		return float(value)
	except Exception:
		return float(default)


def ensure_recovery_log(path: Path) -> None:
	if not path.exists():
		pd.DataFrame(columns=RECOVERY_COLUMNS).to_csv(path, index=False)
		return

	try:
		df = pd.read_csv(path)
	except Exception:
		pd.DataFrame(columns=RECOVERY_COLUMNS).to_csv(path, index=False)
		return

	for col in RECOVERY_COLUMNS:
		if col not in df.columns:
			df[col] = ""
	df = df[RECOVERY_COLUMNS]
	df.to_csv(path, index=False)


def load_recovery_log(path: Path) -> pd.DataFrame:
	ensure_recovery_log(path)
	try:
		return pd.read_csv(path)
	except Exception:
		return pd.DataFrame(columns=RECOVERY_COLUMNS)


def save_recovery_entry(path: Path, row: Dict) -> Dict:
	df = load_recovery_log(path)
	payload = calculate_recovery(row)
	payload["timestamp"] = str(row.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
	out = pd.concat([df, pd.DataFrame([payload])], ignore_index=True)
	out.to_csv(path, index=False)
	return payload


def get_latest_recovery(path: Path) -> Dict:
	df = load_recovery_log(path)
	if df.empty:
		return {}
	latest = df.iloc[-1].to_dict()
	if "recovery_score" in latest:
		latest["recovery_score"] = int(_to_float(latest.get("recovery_score"), 0))
	if "recovery_pct" in latest:
		latest["recovery_pct"] = int(_to_float(latest.get("recovery_pct"), 0))
	return latest


def calculate_recovery(inputs: Dict) -> Dict:
	sleep_hours = _to_float(inputs.get("sleep_hours"), 0)
	sleep_quality = _to_float(inputs.get("sleep_quality"), 0)
	soreness = _to_float(inputs.get("muscle_soreness"), 0)
	energy = _to_float(inputs.get("energy_level"), 0)
	stress = _to_float(inputs.get("stress_level"), 0)
	hydration = _to_float(inputs.get("hydration_oz"), 0)
	calories = _to_float(inputs.get("calories"), 0)
	protein = _to_float(inputs.get("protein_g"), 0)
	body_weight = max(1.0, _to_float(inputs.get("body_weight_lbs"), 180.0))
	body_fat = _to_float(inputs.get("body_fat_pct"), 20.0)

	intensity_raw = str(inputs.get("previous_workout_intensity", "Normal")).strip().lower()
	intensity_map = {"recovery": 1.0, "light": 0.75, "normal": 0.45, "heavy": 0.15}
	intensity_score = intensity_map.get(intensity_raw, 0.45)

	sleep_hours_score = min(1.0, max(0.0, sleep_hours / 8.0))
	sleep_quality_score = min(1.0, max(0.0, sleep_quality / 10.0))
	soreness_score = min(1.0, max(0.0, (10.0 - soreness) / 10.0))
	energy_score = min(1.0, max(0.0, energy / 10.0))
	stress_score = min(1.0, max(0.0, (10.0 - stress) / 10.0))
	hydration_target = min(140.0, max(70.0, body_weight * 0.6))
	hydration_score = min(1.0, max(0.0, hydration / hydration_target))
	calorie_score = min(1.0, max(0.0, calories / 2800.0))
	protein_score = min(1.0, max(0.0, protein / 160.0))

	if body_fat <= 0:
		body_fat_score = 0.5
	elif 10 <= body_fat <= 20:
		body_fat_score = 1.0
	elif 20 < body_fat <= 28:
		body_fat_score = 0.85
	elif 6 <= body_fat < 10:
		body_fat_score = 0.85
	else:
		body_fat_score = 0.7

	score = (
		sleep_hours_score * 0.16
		+ sleep_quality_score * 0.12
		+ soreness_score * 0.12
		+ energy_score * 0.12
		+ stress_score * 0.10
		+ hydration_score * 0.08
		+ intensity_score * 0.10
		+ calorie_score * 0.08
		+ protein_score * 0.08
		+ body_fat_score * 0.04
	)
	recovery_score = int(round(score * 100))
	recovery_pct = recovery_score

	if recovery_score >= 85:
		recovery_status = "Train Heavy"
		readiness_color = "Green"
		recommendation = "Recovery is excellent. Increase intensity today."
	elif recovery_score >= 70:
		recovery_status = "Train Normal"
		readiness_color = "Green"
		recommendation = "Recovery is solid. Train as planned with normal loading."
	elif recovery_score >= 50:
		recovery_status = "Light Session"
		readiness_color = "Yellow"
		recommendation = "Recovery is moderate. Keep weights lighter and focus on clean form."
	else:
		recovery_status = "Recovery Day"
		readiness_color = "Red"
		recommendation = "Recovery is below target. Reduce weight by 10% and extend rest periods."

	return {
		"sleep_hours": round(sleep_hours, 2),
		"sleep_quality": round(sleep_quality, 2),
		"muscle_soreness": round(soreness, 2),
		"energy_level": round(energy, 2),
		"stress_level": round(stress, 2),
		"hydration_oz": round(hydration, 2),
		"previous_workout_intensity": str(inputs.get("previous_workout_intensity", "Normal")),
		"calories": round(calories, 2),
		"protein_g": round(protein, 2),
		"body_weight_lbs": round(body_weight, 2),
		"body_fat_pct": round(body_fat, 2),
		"recovery_score": recovery_score,
		"recovery_pct": recovery_pct,
		"recovery_status": recovery_status,
		"readiness_color": readiness_color,
		"recommendation": recommendation,
	}
