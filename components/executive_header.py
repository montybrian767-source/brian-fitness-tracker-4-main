# Brian Fitness Tracker X
# Executive Header Component

import streamlit as st


def executive_header(title="Project Titan is Live", subtitle="Today’s mission is built around performance, recovery, and consistency.", badge="PROJECT TITAN"):
    st.markdown(f"## {badge}")
    st.markdown(f"### {title}")
    st.caption(subtitle)
