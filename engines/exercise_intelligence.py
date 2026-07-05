import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd


class ExerciseIntelligence:
    def __init__(self, db_path=None, intel_path=None, log_path=None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "exercise_database.csv"
        self.intel_path = intel_path or Path(__file__).parent.parent / "data" / "exercise_intelligence.json"
        self.log_path = log_path or Path(__file__).parent.parent / "data" / "workout_log.csv"
        self.db = self._load_db()
        self.intel = self._load_intel()
        self.log = self._load_log()
        # Default form tips by exercise pattern
        self.default_tips = {
            'press': ['Control the eccentric: lower for 2-3 seconds', 'Chest at top of movement', 'Full arm extension at bottom'],
            'curl': ['Avoid swinging: control the weight', 'Pause at the top for a moment', 'Full extension at the bottom'],
            'row': ['Pull elbows back past torso', 'Squeeze shoulder blades at top', 'Full extension at bottom'],
            'squat': ['Knees track over toes', 'Stay upright and controlled', 'Full range of motion'],
            'deadlift': ['Neutral spine throughout', 'Hips and shoulders rise together', 'Control the descent'],
            'leg': ['Full range without locking knees', 'Knees track over toes', 'Controlled movement'],
            'fly': ['Control the arc of movement', 'Light stretch at bottom, squeeze at top', 'Focus on the target muscle'],
            'raise': ['Light weight, strict form', 'No swinging or momentum', 'Pause at the top'],
            'pull': ['Full range of motion', 'Chest to bar if possible', 'Controlled descent'],
            'plank': ['Keep hips level', 'Neutral spine', 'Engage your core throughout'],
        }
        self.default_mistakes = {
            'press': ['Using excessive weight and losing control', 'Bouncing at the bottom', 'Incomplete range of motion'],
            'curl': ['Swinging the weight up', 'Jerky movements at the top', 'Not fully extending arms'],
            'row': ['Incomplete contraction at top', 'Rounding the lower back', 'Short range of motion'],
            'squat': ['Knees caving inward', 'Upper back rounding', 'Rising hips faster than shoulders'],
            'deadlift': ['Rounding the back at the start', 'Hips rising too fast', 'Losing tension off the floor'],
            'leg': ['Knees going past toes excessively', 'Leaning forward too much', 'Incomplete range of motion'],
            'fly': ['Using too much weight and jerking', 'Incomplete range of motion', 'Arms too straight (not enough bend)'],
            'raise': ['Using momentum and body English', 'Raising above shoulder height', 'Jerky, uncontrolled movement'],
            'pull': ['Partial range of motion', 'Swinging momentum', 'Poor grip width for the exercise'],
            'plank': ['Hips sagging or too high', 'Head dropping or jutting forward', 'Holding breath'],
        }

    def _load_db(self):
        """Load exercise database."""
        if self.db_path.exists():
            try:
                return pd.read_csv(self.db_path)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def _load_log(self):
        if self.log_path.exists():
            try:
                return pd.read_csv(self.log_path)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def _load_intel(self) -> Dict[str, Dict]:
        """Load structured exercise intelligence data from JSON, with CSV fallback."""
        if self.intel_path.exists() and self.intel_path.suffix.lower() == ".json":
            try:
                payload = json.loads(self.intel_path.read_text(encoding="utf-8"))
                return {
                    "templates": payload.get("templates", {}),
                    "profiles": payload.get("profiles", {}),
                }
            except Exception:
                return {"templates": {}, "profiles": {}}

        csv_path = self.intel_path
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
            except Exception:
                df = pd.DataFrame()
            profiles = {}
            for _, row in df.iterrows():
                profiles[str(row.get("exercise", ""))] = {
                    "difficulty": str(row.get("difficulty", "Intermediate")),
                    "primary": str(row.get("primary", "Unknown")),
                    "secondary": str(row.get("secondary", "")),
                    "equipment": str(row.get("equipment", "Bodyweight")),
                    "rest_seconds": row.get("rest_seconds", ""),
                }
            return {"templates": {}, "profiles": profiles}

        return {"templates": {}, "profiles": {}}

    def _safe_list(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split("|") if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    def _slugify(self, text: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(text or "").strip())
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug.strip("_")

    def _exercise_log(self, exercise_name: str) -> pd.DataFrame:
        if self.log.empty or "exercise" not in self.log.columns:
            return pd.DataFrame()
        df = self.log[self.log["exercise"].astype(str).str.lower() == str(exercise_name).lower()].copy()
        if df.empty:
            return df
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for col in ["weight_lbs", "reps", "rpe", "pain", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.sort_values("date") if "date" in df.columns else df

    def _equipment_icons(self, equipment: str) -> List[str]:
        equipment_lower = str(equipment or "").lower()
        icons = []
        mapping = [
            ("machine", "Machine"),
            ("dumbbell", "Dumbbell"),
            ("barbell", "Barbell"),
            ("cable", "Cable"),
            ("band", "Band"),
            ("bench", "Bench"),
            ("bodyweight", "Bodyweight"),
        ]
        for token, label in mapping:
            if token in equipment_lower:
                icons.append(label)
        return icons or ["General"]

    def _progression_metrics(self, exercise_name: str) -> Dict:
        df = self._exercise_log(exercise_name)
        if df.empty:
            return {
                "personal_record": "No personal records logged yet.",
                "estimated_one_rep_max": "N/A",
                "last_workout": "No workout history yet.",
                "recommended_weight": "Build a baseline session first.",
                "ai_confidence_score": 42,
                "weekly_volume": 0,
                "muscle_recovery_pct": 100,
                "ai_coaching_recommendations": [
                    "Log 2-3 clean sessions to unlock more accurate load recommendations.",
                    "Use the image gallery and coaching cues to standardize execution.",
                ],
            }

        latest = df.iloc[-1]
        latest_weight = float(latest.get("weight_lbs", 0) or 0)
        latest_reps = int(latest.get("reps", 0) or 0)
        latest_rpe = float(latest.get("rpe", 0) or 0)
        latest_pain = float(latest.get("pain", 0) or 0)

        pr_weight = pd.to_numeric(df.get("weight_lbs", pd.Series(dtype=float)), errors="coerce").dropna()
        best_weight = float(pr_weight.max()) if not pr_weight.empty else 0.0
        best_row = df.loc[pr_weight.idxmax()] if not pr_weight.empty else latest

        one_rm_series = (
            pd.to_numeric(df.get("weight_lbs", pd.Series(dtype=float)), errors="coerce")
            * (1 + (pd.to_numeric(df.get("reps", pd.Series(dtype=float)), errors="coerce").fillna(0) / 30.0))
        )
        est_1rm = float(one_rm_series.max()) if not one_rm_series.dropna().empty else 0.0

        today = pd.Timestamp(datetime.now().date())
        weekly_cut = today - pd.Timedelta(days=7)
        weekly = df[df["date"] >= weekly_cut] if "date" in df.columns else df
        weekly_volume = int(pd.to_numeric(weekly.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not weekly.empty else 0

        days_since = 7
        if pd.notna(latest.get("date")):
            days_since = max(0, int((today - pd.Timestamp(latest.get("date")).normalize()).days))
        recovery_pct = min(100, 40 + days_since * 14)

        recommended_weight = latest_weight
        if latest_pain >= 4 or latest_rpe >= 9.5:
            recommended_weight = max(0.0, latest_weight - 5)
        elif latest_rpe <= 7.5 and latest_reps >= 10:
            recommended_weight = latest_weight + 5
        elif latest_rpe <= 8.5 and latest_reps >= 8:
            recommended_weight = latest_weight + 2.5

        confidence = min(97, 45 + (len(df) * 6))
        if latest_pain >= 4:
            confidence = max(35, confidence - 12)

        recommendations = []
        if latest_pain >= 4:
            recommendations.append("Pain trend is elevated. Keep the load conservative and prioritize controlled execution.")
        elif latest_rpe <= 7.5 and latest_reps >= 10:
            recommendations.append("Performance is stable. A small load increase is reasonable next session.")
        else:
            recommendations.append("Hold the current load and improve rep quality before progressing.")
        recommendations.append("Match the next working sets to the cleanest rep path shown in your image reference.")

        best_date = pd.to_datetime(best_row.get("date"), errors="coerce")
        last_date = pd.to_datetime(latest.get("date"), errors="coerce")
        best_date_txt = best_date.strftime("%Y-%m-%d") if pd.notna(best_date) else "Unknown"
        last_date_txt = last_date.strftime("%Y-%m-%d") if pd.notna(last_date) else "Unknown"

        return {
            "personal_record": f"{best_weight:.1f} lbs on {best_date_txt}",
            "estimated_one_rep_max": f"{est_1rm:.1f} lbs" if est_1rm > 0 else "N/A",
            "last_workout": f"{last_date_txt} • {latest_weight:.1f} lbs x {latest_reps}",
            "recommended_weight": f"{recommended_weight:.1f} lbs",
            "ai_confidence_score": int(confidence),
            "weekly_volume": weekly_volume,
            "muscle_recovery_pct": int(recovery_pct),
            "ai_coaching_recommendations": recommendations,
        }

    def _similar_exercises(self, exercise_name: str, payload: Dict) -> List[str]:
        names = []
        target_group = str(payload.get("muscle_group", ""))
        target_pattern = str(payload.get("movement_pattern", ""))

        if not self.db.empty:
            for _, row in self.db.iterrows():
                candidate = str(row.get("exercise", "")).strip()
                if not candidate or candidate.lower() == str(exercise_name).lower():
                    continue
                row_group = str(row.get("muscle_group", ""))
                profile_data = self.intel.get("profiles", {}).get(candidate, {}) if isinstance(self.intel, dict) else {}
                template_data = {}
                template_name = profile_data.get("template") if isinstance(profile_data, dict) else None
                if template_name:
                    template_data = self.intel.get("templates", {}).get(template_name, {}) if isinstance(self.intel, dict) else {}
                candidate_pattern = str(profile_data.get("movement_pattern") or template_data.get("movement_pattern") or "")
                if row_group == target_group or candidate_pattern == target_pattern:
                    names.append(candidate)

        if not names:
            names = [item for item in payload.get("variations", []) if str(item).strip() and str(item).strip().lower() != str(exercise_name).lower()]
        return list(dict.fromkeys(names))[:4]

    def _db_row(self, exercise_name: str):
        if self.db.empty:
            return None
        hit = self.db[self.db["exercise"].astype(str).str.lower() == str(exercise_name).lower()]
        if hit.empty:
            return None
        return hit.iloc[0]

    def _default_structured_profile(self, exercise_name: str) -> Dict:
        row = self._db_row(exercise_name)
        muscle_group = str(row.get("muscle_group", "")) if row is not None else ""
        equipment = str(row.get("equipment", "Bodyweight")) if row is not None else "Bodyweight"
        image_file = str(row.get("image_file", "")) if row is not None else ""
        primary = muscle_group.split("+")[0].strip() if muscle_group else "Unknown"
        return {
            "name": exercise_name,
            "exercise": exercise_name,
            "category": muscle_group or "General",
            "muscle_group": muscle_group or "General",
            "primary_muscles": [primary] if primary and primary != "Unknown" else ["Unknown"],
            "secondary_muscles": [],
            "stabilizers": ["Core"],
            "muscle_percentages": [{"muscle": primary or "Unknown", "percentage": 100}],
            "equipment": equipment,
            "difficulty": "Intermediate",
            "exercise_type": "Compound",
            "movement_pattern": "Push" if "chest" in primary.lower() or "shoulder" in primary.lower() else "Pull",
            "strength_focus": "Strength",
            "tags": [primary or "General", "Strength"],
            "instructions": [
                "Set up with control and organize the body before the first rep.",
                "Move through the cleanest full range you can own.",
                "Keep tension on the target muscles instead of chasing momentum.",
            ],
            "tips": self._get_default_tips(exercise_name),
            "common_mistakes": self._get_default_mistakes(exercise_name),
            "variations": [],
            "summary": "Exercise detail data will expand as the Project Titan library grows.",
            "hero_image": image_file,
            "image_file": image_file,
            "start_image": image_file,
            "end_image": "",
            "side_image": "",
            "top_image": "",
            "image_files": {
                "hero": image_file,
                "start": image_file,
                "finish": "",
                "side": "",
            },
            "personal_record_placeholder": "No personal record logged yet.",
            "progression_recommendation_placeholder": "Progression recommendation will appear after consistent workout history is available.",
        }

    def _resolved_profile_payload(self, exercise_name: str) -> Dict:
        base = self._default_structured_profile(exercise_name)
        templates = self.intel.get("templates", {}) if isinstance(self.intel, dict) else {}
        profiles = self.intel.get("profiles", {}) if isinstance(self.intel, dict) else {}
        raw_profile = profiles.get(exercise_name, {})
        template_name = raw_profile.get("template")
        template_payload = templates.get(template_name, {}) if template_name else {}
        merged = {**base, **template_payload, **{k: v for k, v in raw_profile.items() if k != "template"}}

        merged["exercise"] = merged.get("exercise") or merged.get("name") or exercise_name
        merged["name"] = merged.get("name") or merged.get("exercise") or exercise_name
        merged["category"] = merged.get("category") or merged.get("muscle_group") or "General"
        merged["asset_folder"] = merged.get("asset_folder") or self._slugify(merged["exercise"])

        row = self._db_row(exercise_name)
        if row is not None:
            merged.setdefault("muscle_group", str(row.get("muscle_group", "General")))
            if not merged.get("equipment"):
                merged["equipment"] = str(row.get("equipment", "Bodyweight"))
            if not merged.get("image_file"):
                merged["image_file"] = str(row.get("image_file", ""))

        for key in ["primary_muscles", "secondary_muscles", "stabilizers", "tags", "instructions", "tips", "common_mistakes", "variations"]:
            merged[key] = self._safe_list(merged.get(key))

        image_files = merged.get("image_files", {})
        if not isinstance(image_files, dict):
            image_files = {}
        merged["hero_image"] = image_files.get("hero") or merged.get("hero_image") or merged.get("image_file", "")
        merged["start_image"] = image_files.get("start") or merged.get("start_image") or merged.get("hero_image", "")
        merged["end_image"] = image_files.get("finish") or merged.get("end_image") or ""
        merged["side_image"] = image_files.get("side") or merged.get("side_image") or ""
        merged["top_image"] = image_files.get("top") or merged.get("top_image") or ""
        merged["image_files"] = {
            "hero": merged.get("hero_image", ""),
            "start": merged.get("start_image", ""),
            "finish": merged.get("end_image", ""),
            "side": merged.get("side_image", ""),
            "top": merged.get("top_image", ""),
        }

        muscle_percentages = merged.get("muscle_percentages", [])
        if not isinstance(muscle_percentages, list):
            muscle_percentages = []
        merged["muscle_percentages"] = muscle_percentages
        merged.setdefault("personal_record_placeholder", "No personal record logged yet.")
        merged.setdefault("progression_recommendation_placeholder", "Progression recommendation will appear after consistent workout history is available.")

        progression = self._progression_metrics(exercise_name)
        merged.update(progression)
        merged["similar_exercises"] = merged.get("similar_exercises") or self._similar_exercises(exercise_name, merged)
        merged["equipment_icons"] = merged.get("equipment_icons") or self._equipment_icons(merged.get("equipment", ""))
        return merged

    def get_library_dataframe(self) -> pd.DataFrame:
        rows = []
        exercises = []
        if not self.db.empty and "exercise" in self.db.columns:
            exercises = self.db["exercise"].astype(str).dropna().tolist()
        else:
            exercises = list(self.intel.get("profiles", {}).keys()) if isinstance(self.intel, dict) else []

        for exercise_name in dict.fromkeys(exercises):
            profile = self._resolved_profile_payload(exercise_name)
            rows.append(
                {
                    "exercise": profile.get("exercise", exercise_name),
                    "name": profile.get("name", exercise_name),
                    "category": profile.get("category", profile.get("muscle_group", "General")),
                    "muscle_group": profile.get("muscle_group", "General"),
                    "equipment": profile.get("equipment", "Bodyweight"),
                    "movement_pattern": profile.get("movement_pattern", "General"),
                    "difficulty": profile.get("difficulty", "Intermediate"),
                    "image_file": profile.get("image_file", ""),
                }
            )
        return pd.DataFrame(rows).drop_duplicates(subset=["exercise"]).sort_values("exercise").reset_index(drop=True)

    def _get_default_tips(self, exercise_name):
        """Return smart default form tips based on exercise pattern."""
        name_lower = str(exercise_name).lower()
        for pattern, tips in self.default_tips.items():
            if pattern in name_lower:
                return tips
        return ['Control the movement', 'Use full range of motion', 'Stay focused on the target muscle']

    def _get_default_mistakes(self, exercise_name):
        """Return smart default common mistakes based on exercise pattern."""
        name_lower = str(exercise_name).lower()
        for pattern, mistakes in self.default_mistakes.items():
            if pattern in name_lower:
                return mistakes
        return ['Using too much weight', 'Incomplete range of motion', 'Poor form and control']

    def get_profile(self, exercise_name):
        """Get comprehensive exercise profile including intelligence data."""
        payload = self._resolved_profile_payload(exercise_name)
        primary_muscles = payload.get("primary_muscles", [])
        secondary_muscles = payload.get("secondary_muscles", [])
        payload["primary"] = primary_muscles[0] if primary_muscles else "Unknown"
        payload["secondary"] = " + ".join(secondary_muscles[:2])
        payload["form_tips"] = payload.get("tips", []) or self._get_default_tips(exercise_name)
        payload["common_mistakes"] = payload.get("common_mistakes", []) or self._get_default_mistakes(exercise_name)
        payload["alternatives"] = payload.get("variations", [])
        return payload
