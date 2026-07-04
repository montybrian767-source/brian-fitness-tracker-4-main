import streamlit as st


def body_composition_summary(weight, body_fat, muscle_mass, goal_weight=None):
    """Display body composition summary card for dashboard."""
    
    weight_str = f"{weight} lbs" if weight else "—"
    bf_str = f"{body_fat}%" if body_fat else "—"
    mm_str = f"{muscle_mass} lbs" if muscle_mass else "—"
    goal_str = f"Goal: {goal_weight} lbs" if goal_weight else "No goal set"
    
    html_content = f"""<div style="background:linear-gradient(145deg,rgba(16,38,63,0.98),rgba(10,23,40,0.95));border:1px solid rgba(255,255,255,0.10);border-radius:24px;padding:24px;margin-bottom:20px;box-shadow:0 18px 42px rgba(0,0,0,0.24);"><div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;"><div style="display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:999px;background:rgba(255,255,255,0.10);color:#06B6D4;font-size:1.05rem;font-weight:800;">⚖️</div><div style="font-size:1.15rem;font-weight:800;color:white;">Body Composition</div></div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;"><div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;"><div style="font-size:0.75rem;text-transform:uppercase;color:#9ca3af;font-weight:600;margin-bottom:8px;">Weight</div><div style="font-size:1.5rem;color:#3B82F6;font-weight:800;">{weight_str}</div></div><div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;"><div style="font-size:0.75rem;text-transform:uppercase;color:#9ca3af;font-weight:600;margin-bottom:8px;">Body Fat</div><div style="font-size:1.5rem;color:#8B5CF6;font-weight:800;">{bf_str}</div></div><div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;"><div style="font-size:0.75rem;text-transform:uppercase;color:#9ca3af;font-weight:600;margin-bottom:8px;">Muscle Mass</div><div style="font-size:1.5rem;color:#22C55E;font-weight:800;">{mm_str}</div></div></div><div style="font-size:0.9rem;color:#cbd5e1;margin-top:12px;text-align:center;">{goal_str}</div></div>"""
    
    st.markdown(html_content, unsafe_allow_html=True)
