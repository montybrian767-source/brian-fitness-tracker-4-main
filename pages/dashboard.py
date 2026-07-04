import streamlit as st
import pandas as pd
from pathlib import Path

from components.executive_header import executive_header
from components.mission_card import mission_card
from components.action_button import start_workout_button
from components.hero_banner import hero_banner
from components.stat_card import stat_card
from components.ai_card import ai_card
from components.glass_panel import glass_panel
from components.body_composition_summary import body_composition_summary
from engines.body_intelligence import BodyIntelligence


def render_dashboard():
    # Load latest body stats for summary card
    app_dir = Path(__file__).parent.parent
    body_stats_path = app_dir / "data" / "body_stats.csv"
    
    latest_weight = None
    latest_bf = None
    latest_mm = None
    latest_gw = None
    
    if body_stats_path.exists():
        try:
            body_df = pd.read_csv(body_stats_path)
            if not body_df.empty:
                latest = body_df.iloc[-1]
                latest_weight = latest.get('body_weight_lbs')
                latest_bf = latest.get('body_fat_pct')
                latest_mm = latest.get('muscle_mass_lbs')
                latest_gw = latest.get('goal_weight_lbs')
                
                # Convert to numeric safely
                if latest_weight and latest_weight != '':
                    try:
                        latest_weight = float(latest_weight)
                    except:
                        latest_weight = None
                if latest_bf and latest_bf != '':
                    try:
                        latest_bf = float(latest_bf)
                    except:
                        latest_bf = None
                if latest_mm and latest_mm != '':
                    try:
                        latest_mm = float(latest_mm)
                    except:
                        latest_mm = None
                if latest_gw and latest_gw != '':
                    try:
                        latest_gw = float(latest_gw)
                    except:
                        latest_gw = None
        except:
            pass
    
    executive_header(
        title="Project Titan is Live",
        subtitle="Stay aligned on recovery, training execution, and the next best action for today.",
        badge="PROJECT TITAN",
    )

    mission_card(
        workout="Shoulders + Abs",
        recovery="94%",
        readiness="Ready To Train",
        time="58 min",
        description="Lead with clarity, execute each set with control, and finish the session feeling sharper than when you started.",
    )

    start_workout_button("💪 LAUNCH TODAY'S WORKOUT")

    st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

    hero_banner(
        workout_name="Shoulders + Abs",
        recovery="94%",
        readiness="Excellent",
        duration="60 min",
        today="Thursday",
        focus="Shoulders + Abs",
        title="Good Morning Brian",
        subtitle="Your executive brief is aligned around strength, recovery, and consistency. Make the next move obvious and keep momentum high.",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("Sessions", "0", "#3B82F6", "⚡", "Focused sessions")
    with c2:
        stat_card("Total Volume", "0 lbs", "#22C55E", "🏋️", "Lbs lifted")
    with c3:
        stat_card("Protein Today", "0g", "#8B5CF6", "🥣", "Daily target")
    with c4:
        stat_card("Calories Today", "0", "#F59E0B", "🔥", "Energy balance")

    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

    body_composition_summary(latest_weight, latest_bf, latest_mm, latest_gw)

    ai_card(
        message="Recovery is strong, your form should stay controlled, and hydration is the main lever to protect energy through the session.",
        recommendation="Increase shoulder press by 5 lbs if the first set feels clean.",
        protein_status="On Track",
        hydration_status="Below Goal",
    )

    glass_panel(
        "Today's Workout Summary",
        "<div style='display:grid; gap:10px;'><div>• Primary focus: Shoulders + Abs</div><div>• Target pace: smooth, controlled reps with clean rest</div><div>• Recovery cue: hydrate, breathe, and keep the session deliberate</div></div>",
        "🧠",
        accent="#22C55E",
    )


render_dashboard()
