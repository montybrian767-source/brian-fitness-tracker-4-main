import streamlit as st


def hero_banner(
    workout_name="Shoulders + Abs",
    recovery="94%",
    readiness="Excellent",
    duration="61 min",
    today="Today",
    focus="Recovery / Rest",
    title="Project Titan is Live",
    subtitle=None,
):
    subtitle = subtitle or (
        f"Today's focus is {workout_name}. Keep the session sharp, recover with intention, and finish with momentum."
    )

    st.markdown("### PROJECT TITAN")
    st.markdown(f"## {title}")
    st.caption(subtitle)

    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"**Today:** {today}")
        st.markdown(f"**Focus:** {focus}")
    with c2:
        st.markdown(f"**Recovery:** {recovery}")
        st.markdown(f"**Readiness:** {readiness}")
        st.markdown(f"**Duration:** {duration}")
