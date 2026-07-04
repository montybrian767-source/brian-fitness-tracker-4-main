import streamlit as st


def exercise_intelligence_panel(exercise_data):
    """Render a premium Exercise Intelligence panel with form tips, common mistakes, alternatives, and metrics."""
    
    exercise_name = exercise_data.get('exercise', 'Unknown')
    primary = exercise_data.get('primary', 'Unknown')
    secondary = exercise_data.get('secondary', '')
    equipment = exercise_data.get('equipment', 'Bodyweight')
    difficulty = exercise_data.get('difficulty', 'Intermediate')
    form_tips = exercise_data.get('form_tips', [])
    common_mistakes = exercise_data.get('common_mistakes', [])
    alternatives = exercise_data.get('alternatives', [])
    
    # Clean up lists
    if isinstance(form_tips, str):
        form_tips = [t.strip() for t in form_tips.split(',') if t.strip()]
    if isinstance(common_mistakes, str):
        common_mistakes = [m.strip() for m in common_mistakes.split(',') if m.strip()]
    if isinstance(alternatives, str):
        alternatives = [a.strip() for a in alternatives.split(',') if a.strip()]
    
    # Render compact intelligence card
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0f1f34,#07111f);border:1px solid rgba(96,165,250,.25);border-radius:16px;padding:16px;margin-bottom:12px;">
      <div style="display:grid;grid-template-columns:auto auto auto;gap:16px;margin-bottom:12px;">
        <div><div style="color:#93c5fd;font-size:.78rem;font-weight:900;text-transform:uppercase;">Primary</div><div style="font-weight:900;margin-top:4px;">{primary}</div></div>
        <div><div style="color:#93c5fd;font-size:.78rem;font-weight:900;text-transform:uppercase;">Equipment</div><div style="font-weight:900;margin-top:4px;">{equipment}</div></div>
        <div><div style="color:#93c5fd;font-size:.78rem;font-weight:900;text-transform:uppercase;">Difficulty</div><div style="font-weight:900;margin-top:4px;">{difficulty}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Form tips section
    if form_tips:
        tips_html = ''.join([f'<li style="margin-bottom:6px;"><strong>{tip.split(":",1)[0]}:</strong> {tip.split(":",1)[1] if ":" in tip else tip}</li>' for tip in form_tips[:3]])
        st.markdown(f"""
        <div style="background:#0f1f34;border-left:3px solid #22c55e;border-radius:8px;padding:12px;margin-bottom:12px;">
          <div style="color:#86efac;font-weight:900;font-size:.9rem;margin-bottom:8px;">✓ FORM TIPS</div>
          <ul style="margin:0;padding-left:20px;color:#c8d3e6;font-size:.95rem;">{tips_html}</ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Common mistakes section
    if common_mistakes:
        mistakes_html = ''.join([f'<li style="margin-bottom:6px;">{mistake}</li>' for mistake in common_mistakes[:3]])
        st.markdown(f"""
        <div style="background:#0f1f34;border-left:3px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:12px;">
          <div style="color:#fcd34d;font-weight:900;font-size:.9rem;margin-bottom:8px;">⚠ AVOID</div>
          <ul style="margin:0;padding-left:20px;color:#c8d3e6;font-size:.95rem;">{mistakes_html}</ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Alternatives section
    if alternatives:
        alts_text = ', '.join(alternatives[:2])
        st.markdown(f"""
        <div style="background:#0f1f34;border-left:3px solid #8b5cf6;border-radius:8px;padding:12px;">
          <div style="color:#d8b4fe;font-weight:900;font-size:.9rem;margin-bottom:6px;">↔ ALTERNATIVES</div>
          <div style="color:#c8d3e6;font-size:.95rem;">{alts_text}</div>
        </div>
        """, unsafe_allow_html=True)
