import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


class BodyIntelligence:
    """Calculate body composition trends and generate AI insights."""
    
    def __init__(self, body_stats_df):
        self.df = body_stats_df.copy()
        if not self.df.empty:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
            self.df = self.df.dropna(subset=['date']).sort_values('date')
    
    def get_latest_metrics(self):
        """Return the most recent body stats entry."""
        if self.df.empty:
            return None
        return self.df.iloc[-1].to_dict()
    
    def get_weekly_change(self):
        """Calculate weight change over the last 7 days."""
        if self.df.empty:
            return None
        
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        recent = self.df[self.df['date'] >= week_ago].copy()
        
        if recent.empty or len(recent) < 2:
            return None
        
        recent['body_weight_lbs'] = pd.to_numeric(recent['body_weight_lbs'], errors='coerce')
        recent = recent.dropna(subset=['body_weight_lbs'])
        
        if recent.empty or len(recent) < 2:
            return None
        
        first_weight = recent.iloc[0]['body_weight_lbs']
        last_weight = recent.iloc[-1]['body_weight_lbs']
        change = last_weight - first_weight
        
        return {
            'change_lbs': round(change, 1),
            'direction': '↓' if change < 0 else '↑' if change > 0 else '→',
            'period': '7 days'
        }
    
    def get_monthly_change(self):
        """Calculate weight change over the last 30 days."""
        if self.df.empty:
            return None
        
        today = datetime.now()
        month_ago = today - timedelta(days=30)
        
        recent = self.df[self.df['date'] >= month_ago].copy()
        
        if recent.empty or len(recent) < 2:
            return None
        
        recent['body_weight_lbs'] = pd.to_numeric(recent['body_weight_lbs'], errors='coerce')
        recent = recent.dropna(subset=['body_weight_lbs'])
        
        if recent.empty or len(recent) < 2:
            return None
        
        first_weight = recent.iloc[0]['body_weight_lbs']
        last_weight = recent.iloc[-1]['body_weight_lbs']
        change = last_weight - first_weight
        
        return {
            'change_lbs': round(change, 1),
            'direction': '↓' if change < 0 else '↑' if change > 0 else '→',
            'period': '30 days'
        }
    
    def get_body_fat_trend(self):
        """Calculate body fat % change over time."""
        if self.df.empty or 'body_fat_pct' not in self.df.columns:
            return None
        
        bf_data = self.df[['date', 'body_fat_pct']].copy()
        bf_data['body_fat_pct'] = pd.to_numeric(bf_data['body_fat_pct'], errors='coerce')
        bf_data = bf_data.dropna(subset=['body_fat_pct'])
        
        if len(bf_data) < 2:
            return None
        
        first = bf_data.iloc[0]['body_fat_pct']
        last = bf_data.iloc[-1]['body_fat_pct']
        change = last - first
        
        return {
            'current': round(last, 1),
            'change': round(change, 1),
            'direction': '↓' if change < 0 else '↑' if change > 0 else '→'
        }
    
    def get_muscle_mass_trend(self):
        """Calculate muscle mass change over time."""
        if self.df.empty or 'muscle_mass_lbs' not in self.df.columns:
            return None
        
        mm_data = self.df[['date', 'muscle_mass_lbs']].copy()
        mm_data['muscle_mass_lbs'] = pd.to_numeric(mm_data['muscle_mass_lbs'], errors='coerce')
        mm_data = mm_data.dropna(subset=['muscle_mass_lbs'])
        
        if len(mm_data) < 2:
            return None
        
        first = mm_data.iloc[0]['muscle_mass_lbs']
        last = mm_data.iloc[-1]['muscle_mass_lbs']
        change = last - first
        
        return {
            'current': round(last, 1),
            'change': round(change, 1),
            'direction': '↑' if change > 0 else '↓' if change < 0 else '→'
        }
    
    def generate_ai_note(self):
        """Generate AI Body Intelligence note from trends."""
        notes = []
        
        latest = self.get_latest_metrics()
        if latest is None:
            return "Start tracking body metrics to unlock AI insights."
        
        # Weight trend
        weekly = self.get_weekly_change()
        if weekly:
            if weekly['change_lbs'] < -1.5:
                notes.append(f"Strong weight loss momentum: {weekly['direction']} {abs(weekly['change_lbs'])} lbs in 7 days. Ensure adequate protein intake.")
            elif weekly['change_lbs'] > 1.5:
                notes.append(f"Weight gaining: {weekly['direction']} {weekly['change_lbs']} lbs in 7 days. Monitor caloric surplus.")
            else:
                notes.append(f"Weight stable: {weekly['direction']} {abs(weekly['change_lbs'])} lbs in 7 days. Maintain current approach.")
        
        # Body fat trend
        bf_trend = self.get_body_fat_trend()
        if bf_trend and bf_trend['current']:
            if bf_trend['change'] < -1:
                notes.append(f"Excellent body composition: {bf_trend['direction']} {abs(bf_trend['change'])}% body fat. Continue current training and nutrition.")
            elif bf_trend['change'] > 1:
                notes.append(f"Body fat increasing: {bf_trend['direction']} {bf_trend['change']}%. Review caloric balance and training intensity.")
            else:
                notes.append(f"Body composition stable at {bf_trend['current']}% body fat.")
        
        # Muscle mass trend
        mm_trend = self.get_muscle_mass_trend()
        if mm_trend and mm_trend['current']:
            if mm_trend['change'] > 2:
                notes.append(f"Strong muscle gains: {mm_trend['direction']} {mm_trend['change']} lbs. Recovery and protein targets working.")
            elif mm_trend['change'] < -1:
                notes.append(f"Monitor muscle loss: {mm_trend['direction']} {abs(mm_trend['change'])} lbs. Increase training volume or protein.")

        # Hydration trend from water_pct if available
        if 'water_pct' in self.df.columns:
            h = self.df[['date', 'water_pct']].copy()
            h['water_pct'] = pd.to_numeric(h['water_pct'], errors='coerce')
            h = h.dropna(subset=['water_pct'])
            if len(h) >= 2:
                h_change = h.iloc[-1]['water_pct'] - h.iloc[0]['water_pct']
                if h_change > 0.3:
                    notes.append(f"Hydration trend improving: ↑ {h_change:.1f}% water.")
                elif h_change < -0.3:
                    notes.append(f"Hydration trend declining: ↓ {abs(h_change):.1f}% water. Increase fluid consistency.")
                else:
                    notes.append("Hydration trend is stable.")

        # Weekly summary line
        if weekly:
            notes.append(f"Weekly summary: weight {weekly['direction']} {abs(weekly['change_lbs'])} lbs over {weekly['period']}.")
        
        if not notes:
            return "Keep logging body metrics for trend analysis and personalized insights."
        
        return " • ".join(notes[:2])  # Return top 2 insights
