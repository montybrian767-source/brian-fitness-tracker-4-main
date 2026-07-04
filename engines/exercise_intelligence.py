import pandas as pd
from pathlib import Path


class ExerciseIntelligence:
    def __init__(self, db_path=None, intel_path=None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "exercise_database.csv"
        self.intel_path = intel_path or Path(__file__).parent.parent / "data" / "exercise_intelligence.csv"
        self.db = self._load_db()
        self.intel = self._load_intel()
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

    def _load_intel(self):
        """Load exercise intelligence data."""
        if self.intel_path.exists():
            try:
                return pd.read_csv(self.intel_path)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

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
        profile = {
            'exercise': exercise_name,
            'difficulty': 'Intermediate',
            'primary': 'Unknown',
            'secondary': '',
            'equipment': 'Bodyweight',
            'form_tips': [],
            'common_mistakes': [],
            'alternatives': [],
        }
        
        # Try to load from database
        if not self.db.empty:
            hit = self.db[self.db['exercise'].astype(str).str.lower() == str(exercise_name).lower()]
            if not hit.empty:
                row = hit.iloc[0]
                profile['equipment'] = str(row.get('equipment', 'Bodyweight'))
                # Parse muscle group as primary/secondary
                muscle_group = str(row.get('muscle_group', ''))
                parts = [p.strip() for p in muscle_group.split('+')]
                if parts:
                    profile['primary'] = parts[0]
                    if len(parts) > 1:
                        profile['secondary'] = ' + '.join(parts[1:])
        
        # Try to load intelligence data
        if not self.intel.empty:
            hit = self.intel[self.intel['exercise'].astype(str).str.lower() == str(exercise_name).lower()]
            if not hit.empty:
                row = hit.iloc[0]
                if pd.notna(row.get('difficulty')):
                    profile['difficulty'] = str(row['difficulty'])
                if pd.notna(row.get('form_tips')):
                    profile['form_tips'] = str(row['form_tips']).split('|')
                if pd.notna(row.get('common_mistakes')):
                    profile['common_mistakes'] = str(row['common_mistakes']).split('|')
                if pd.notna(row.get('alternatives')):
                    profile['alternatives'] = str(row['alternatives']).split('|')
        
        # Fill in smart defaults if empty
        if not profile['form_tips']:
            profile['form_tips'] = self._get_default_tips(exercise_name)
        if not profile['common_mistakes']:
            profile['common_mistakes'] = self._get_default_mistakes(exercise_name)
        
        # Smart alternatives based on primary muscle
        if not profile['alternatives']:
            primary_lower = profile['primary'].lower()
            alternatives_map = {
                'chest': ['Dumbbell Press', 'Machine Press'],
                'back': ['Lat Pulldown', 'Cable Row'],
                'shoulders': ['Machine Shoulder Press', 'Pike Push-ups'],
                'arms': ['Cable Curl', 'Tricep Rope'],
                'legs': ['Leg Press', 'Hack Squat'],
                'abs': ['Cable Crunch', 'Ab Wheel'],
            }
            for key, alts in alternatives_map.items():
                if key in primary_lower:
                    profile['alternatives'] = alts
                    break
        
        return profile
