import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path

from components.body_intelligence_panel import body_intelligence_panel
from engines.body_intelligence import BodyIntelligence

APP_DIR = Path(__file__).parent.parent
DATA = APP_DIR / "data"
BODY = DATA / "body_stats.csv"

def ensure_body_stats():
    """Create body_stats.csv if it doesn't exist with proper schema."""
    columns = [
        'date', 'body_weight_lbs', 'goal_weight_lbs', 'waist_in',
        'body_fat_pct', 'muscle_mass_lbs', 'bmi', 'water_pct',
        'protein_pct', 'bone_mass_lbs', 'bmr_cal', 'metabolic_age',
        'visceral_fat', 'lean_body_mass_lbs', 'notes', 'import_source'
    ]
    
    if BODY.exists():
        # Check if schema needs migration
        df = pd.read_csv(BODY)
        changed = False
        if set(df.columns) != set(columns):
            # Schema mismatch - migrate old data without dropping legacy columns
            for col in columns:
                if col not in df.columns:
                    df[col] = ''
                    changed = True
            extras = [c for c in df.columns if c not in columns]
            df = df[columns + extras]
            changed = True

        if 'import_source' in df.columns:
            src = df['import_source'].astype(str)
            missing = src.str.strip().eq('') | src.str.lower().eq('nan')
            if missing.any():
                df.loc[missing, 'import_source'] = 'Manual'
                changed = True

        if changed:
            df.to_csv(BODY, index=False)
    else:
        # Create new CSV with proper schema
        pd.DataFrame(columns=columns).to_csv(BODY, index=False)

def read_body_stats():
    """Read body stats CSV safely."""
    ensure_body_stats()
    try:
        return pd.read_csv(BODY)
    except Exception:
        return pd.DataFrame(columns=[
            'date', 'body_weight_lbs', 'goal_weight_lbs', 'waist_in',
            'body_fat_pct', 'muscle_mass_lbs', 'bmi', 'water_pct',
            'protein_pct', 'bone_mass_lbs', 'bmr_cal', 'metabolic_age',
            'visceral_fat', 'lean_body_mass_lbs', 'notes', 'import_source'
        ])

def append_body_stats(row_dict):
    """Append a row to body_stats.csv."""
    df = read_body_stats()
    df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
    df.to_csv(BODY, index=False)

def render_body_stats_page():
    """Render the Body Stats page with expandable sections."""
    
    st.markdown(
        '<div style="background: linear-gradient(135deg, rgba(30,58,138,0.3), rgba(16,38,63,0.5)); border-left: 4px solid #3B82F6; padding: 20px; border-radius: 12px; margin-bottom: 24px;">'
        '<div style="font-size: 2rem; font-weight: 800; color: white; margin-bottom: 8px;">⚙️ Body Intelligence Center</div>'
        '<div style="font-size: 1rem; color: #dbeafe;">Track body composition, weight, and health metrics. Automatic trend analysis and AI insights included.</div>'
        '</div>',
        unsafe_allow_html=True
    )
    
    # Load existing data
    body_df = read_body_stats()
    
    # Display AI insights if data exists
    if not body_df.empty:
        bi = BodyIntelligence(body_df)
        latest = bi.get_latest_metrics()
        
        if latest:
            body_intelligence_panel(
                latest_metrics=latest,
                weekly_change=bi.get_weekly_change(),
                monthly_change=bi.get_monthly_change(),
                body_fat_trend=bi.get_body_fat_trend(),
                muscle_mass_trend=bi.get_muscle_mass_trend(),
                ai_note=bi.generate_ai_note()
            )
    
    # Input form
    st.markdown('<div style="margin-top: 32px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.2rem; font-weight: 800; color: white;">📊 Log Body Metrics</div>', unsafe_allow_html=True)
    
    entry_date = st.date_input('Date', value=date.today(), key='body_date')
    
    # Basic Metrics Section
    with st.expander("📏 Basic Metrics", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            weight = col1.number_input('Body Weight (lbs)', min_value=0.0, value=0.0, step=0.5, key='weight_input')
        with col2:
            goal_weight = col2.number_input('Goal Weight (lbs)', min_value=0.0, value=0.0, step=0.5, key='goal_weight_input')
        with col3:
            waist = col3.number_input('Waist (inches)', min_value=0.0, value=0.0, step=0.25, key='waist_input')
    
    # Body Composition Section
    with st.expander("🧬 Body Composition"):
        col1, col2, col3 = st.columns(3)
        with col1:
            body_fat = col1.number_input('Body Fat (%)', min_value=0.0, max_value=100.0, value=0.0, step=0.1, key='bf_input')
        with col2:
            muscle_mass = col2.number_input('Muscle Mass (lbs)', min_value=0.0, value=0.0, step=0.5, key='mm_input')
        with col3:
            lean_mass = col3.number_input('Lean Body Mass (lbs)', min_value=0.0, value=0.0, step=0.5, key='lbm_input')
    
    # Health Metrics Section
    with st.expander("❤️ Health Metrics"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bmi = col1.number_input('BMI', min_value=0.0, value=0.0, step=0.1, key='bmi_input')
        with col2:
            water_pct = col2.number_input('Water (%)', min_value=0.0, max_value=100.0, value=0.0, step=0.1, key='water_input')
        with col3:
            protein_pct = col3.number_input('Protein (%)', min_value=0.0, max_value=100.0, value=0.0, step=0.1, key='protein_input')
    
    # Advanced Metrics Section
    with st.expander("⚗️ Advanced Metrics"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bone_mass = col1.number_input('Bone Mass (lbs)', min_value=0.0, value=0.0, step=0.1, key='bone_input')
        with col2:
            bmr = col2.number_input('BMR (cal/day)', min_value=0, value=0, step=10, key='bmr_input')
        with col3:
            metabolic_age = col3.number_input('Metabolic Age', min_value=0, value=0, step=1, key='meta_age_input')
    
    # Visceral Fat Section
    with st.expander("📈 Visceral Fat & Notes"):
        col1, col2 = st.columns(2)
        with col1:
            visceral_fat = col1.number_input('Visceral Fat', min_value=0.0, value=0.0, step=0.1, key='vf_input')
        with col2:
            st.markdown('<div style="margin-top: 8px;"></div>', unsafe_allow_html=True)
        
        notes = st.text_input('Notes', placeholder='Energy, soreness, progress notes, or smart scale sync status', key='body_notes')
    
    # Save button
    if st.button('💾 Save Body Stats', key='save_body_btn', width='stretch'):
        row = {
            'date': str(entry_date),
            'body_weight_lbs': weight if weight > 0 else '',
            'goal_weight_lbs': goal_weight if goal_weight > 0 else '',
            'waist_in': waist if waist > 0 else '',
            'body_fat_pct': body_fat if body_fat > 0 else '',
            'muscle_mass_lbs': muscle_mass if muscle_mass > 0 else '',
            'bmi': bmi if bmi > 0 else '',
            'water_pct': water_pct if water_pct > 0 else '',
            'protein_pct': protein_pct if protein_pct > 0 else '',
            'bone_mass_lbs': bone_mass if bone_mass > 0 else '',
            'bmr_cal': bmr if bmr > 0 else '',
            'metabolic_age': metabolic_age if metabolic_age > 0 else '',
            'visceral_fat': visceral_fat if visceral_fat > 0 else '',
            'lean_body_mass_lbs': lean_mass if lean_mass > 0 else '',
            'notes': notes,
            'import_source': 'Manual'
        }
        append_body_stats(row)
        st.success('✅ Body stats logged successfully!')
        st.rerun()
    
    # History Section
    st.markdown('<div style="margin-top: 32px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.2rem; font-weight: 800; color: white;">📈 Tracking History</div>', unsafe_allow_html=True)
    
    if body_df.empty:
        st.info('📋 No body metrics logged yet. Start tracking to see trends and AI insights!')
    else:
        # Display last 50 entries
        display_df = body_df.tail(50).copy()
        st.dataframe(display_df, width='stretch', hide_index=True)
        
        # Weight chart
        if 'body_weight_lbs' in display_df.columns:
            chart_df = display_df[['date', 'body_weight_lbs']].copy()
            chart_df['body_weight_lbs'] = pd.to_numeric(chart_df['body_weight_lbs'], errors='coerce')
            chart_df = chart_df.dropna(subset=['body_weight_lbs'])
            
            if not chart_df.empty:
                st.markdown('<div style="margin-top: 20px; font-size: 0.95rem; font-weight: 600; color: #dbeafe;">Weight Trend</div>', unsafe_allow_html=True)
                st.line_chart(chart_df.set_index('date')['body_weight_lbs'], width='stretch')
    
    # Future Smart Scale Integration Placeholder
    st.markdown('<div style="margin-top: 32px;"></div>', unsafe_allow_html=True)
    with st.expander("🔗 Smart Scale Integration (Future)"):
        st.info(
            "🚀 **Coming Soon**: Connect smart scales (Withings, Renpho, FITBIT) for automatic body composition syncing. "
            "Your CSV is already optimized for direct imports from smart scale exports. "
            "No data will be lost or modified during integration setup."
        )


if __name__ == "__main__":
    ensure_body_stats()
    render_body_stats_page()
