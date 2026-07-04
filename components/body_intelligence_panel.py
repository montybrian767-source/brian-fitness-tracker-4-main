import streamlit as st


def body_intelligence_panel(latest_metrics, weekly_change, monthly_change, body_fat_trend, 
                            muscle_mass_trend, ai_note):
    """Display body composition trends and AI insights using native Streamlit components."""
    
    st.markdown("#### 🧬 Body Intelligence Summary")
    st.info(ai_note, icon="💡")
    
    # Metrics grid - max 2 columns for better spacing
    if weekly_change or monthly_change or body_fat_trend or muscle_mass_trend:
        col_count = sum([1 for x in [weekly_change, monthly_change, body_fat_trend, muscle_mass_trend] if x])
        cols = st.columns(min(col_count, 2))
        col_idx = 0
        
        if weekly_change:
            with cols[col_idx % len(cols)]:
                st.metric(
                    "Weekly Change",
                    f"{weekly_change['direction']} {abs(weekly_change['change_lbs'])} lbs"
                )
            col_idx += 1
        
        if monthly_change:
            with cols[col_idx % len(cols)]:
                st.metric(
                    "Monthly Change",
                    f"{monthly_change['direction']} {abs(monthly_change['change_lbs'])} lbs"
                )
            col_idx += 1
        
        if body_fat_trend:
            with cols[col_idx % len(cols)]:
                st.metric(
                    "Body Fat %",
                    f"{body_fat_trend['current']}%"
                )
            col_idx += 1
        
        if muscle_mass_trend:
            with cols[col_idx % len(cols)]:
                st.metric(
                    "Muscle Mass",
                    f"{muscle_mass_trend['current']} lbs"
                )
    
    st.markdown("---")

    # Keep this summary section native so no raw HTML tags are ever shown.
    summary_bits = []
    if latest_metrics:
        latest_date = latest_metrics.get("date")
        if latest_date:
            summary_bits.append(f"Latest entry: {latest_date}")

    if summary_bits:
        st.caption(" | ".join(summary_bits))
