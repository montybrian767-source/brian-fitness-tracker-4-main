import streamlit as st
from components.exercise_intelligence_panel import exercise_intelligence_panel


def workout_command_center(
    row,
    idx,
    total,
    photo_html,
    last_weight,
    last_reps,
    best_weight,
    sets,
    reps_default,
    ai_cue,
    completed_today,
    total_volume_today,
    day,
    exercise_data=None,
    key_prefix="wcc",
    disable_actions=False,
):
    """Render a premium Workout Command Center with Exercise Intelligence integration.

    This component is display-only in terms of persistence: callers should perform any CSV logging when
    `result['complete']` is True.
    """
    # No duplicate header — rely on exercise intelligence panel for context
    
    left, right = st.columns([1.0, 1.0])
    
    with left:
        # Exercise image with clean aspect ratio
        st.markdown(f'<div style="border-radius:12px;overflow:hidden;background:#0f1f34;padding:8px;">{photo_html}</div>', unsafe_allow_html=True)
        
        # Display metrics below image
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div style="background:#07111f;border-radius:8px;padding:10px;text-align:center;"><div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Previous</div><div style="font-weight:900;font-size:1.3rem;">{last_weight:g}</div><div style="color:#93c5fd;font-size:.75rem;">lbs</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div style="background:#07111f;border-radius:8px;padding:10px;text-align:center;"><div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Previous Reps</div><div style="font-weight:900;font-size:1.3rem;">{int(last_reps or 0)}</div><div style="color:#93c5fd;font-size:.75rem;">reps</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div style="background:#07111f;border-radius:8px;padding:10px;text-align:center;"><div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Personal Record</div><div style="font-weight:900;font-size:1.3rem;">{best_weight:g}</div><div style="color:#93c5fd;font-size:.75rem;">lbs</div></div>', unsafe_allow_html=True)
    
    with right:
        # Exercise Intelligence Panel
        if exercise_data:
            exercise_intelligence_panel(exercise_data)
    
    # Logging inputs
    st.markdown("### Log This Set")
    col1, col2, col3 = st.columns(3)
    with col1:
        weight = st.number_input("Weight", min_value=0.0, value=float(last_weight or row.get('base_weight',0)), step=2.5, key=f"{key_prefix}_w_{idx}")
    with col2:
        reps = st.number_input("Reps", min_value=0, value=int(reps_default or 8), step=1, key=f"{key_prefix}_r_{idx}")
    with col3:
        rpe = st.number_input("RPE", min_value=0.0, max_value=10.0, value=7.0, step=0.5, key=f"{key_prefix}_rpe_{idx}")

    body_feedback_score = st.slider("Body Check-In", 0, 10, 0, key=f"{key_prefix}_body_feedback_{idx}")
    set_number = st.number_input("Set number", min_value=1, max_value=max(int(sets or 8), 8), value=1, step=1, key=f"{key_prefix}_set_{idx}")
    body_feedback_notes = st.text_input("Quick notes", value="", placeholder="Form, difficulty, body check-in, equipment notes...", key=f"{key_prefix}_notes_{idx}")

    vol = int(weight * reps)
    st.markdown(f'<div style="background:#07111f;border-radius:12px;padding:12px;margin-bottom:12px;"><div style="color:#93c5fd;font-size:.85rem;">Current Set Volume</div><div style="font-size:1.8rem;font-weight:900;color:#22c55e;">{vol:,} lbs</div></div>', unsafe_allow_html=True)

    complete = st.button(
        "✅ COMPLETE SET",
        key=f"{key_prefix}_complete_{idx}",
        use_container_width=True,
        disabled=bool(disable_actions),
    )
    
    # Navigation buttons
    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        prev_clicked = st.button("← Previous", key=f"{key_prefix}_prev_{idx}", disabled=(idx<=0), use_container_width=True)
    with nav2:
        next_clicked = st.button("➡ NEXT EXERCISE", key=f"{key_prefix}_next_{idx}", disabled=(idx>=total-1), use_container_width=True)
    with nav3:
        st.caption(f"Exercise {idx+1} of {total}")
    with nav4:
        finish_clicked = st.button(
            "🏁 Finish",
            key=f"{key_prefix}_finish_{idx}",
            use_container_width=True,
            disabled=bool(disable_actions),
        )

    # Progress
    st.markdown(f"**Progress:** {completed_today} sets logged • {total_volume_today:,} lbs")
    progress_pct = 0
    try:
        progress_pct = min(100, int((completed_today / max(1, int(row.get('target_sets',1)))) * 100))
    except Exception:
        progress_pct = 0
    st.progress(progress_pct / 100.0)

    return {
        'complete': complete,
        'weight': weight,
        'reps': reps,
        'rpe': rpe,
        'pain': body_feedback_score,
        'body_feedback_score': body_feedback_score,
        'set_number': set_number,
        'notes': body_feedback_notes,
        'body_feedback_notes': body_feedback_notes,
        'volume': vol,
        'prev': prev_clicked,
        'next': next_clicked,
        'finish': finish_clicked,
    }
