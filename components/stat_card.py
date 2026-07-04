import streamlit as st


def stat_card(title, value, color="#3B82F6", icon="•", subtitle=""):
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, rgba(16,38,63,0.98), rgba(10,23,40,0.95));
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 24px;
            padding: 20px;
            min-height: 132px;
            box-shadow: 0 18px 42px rgba(0,0,0,0.24);
        ">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
                <div style="font-size: 0.78rem; letter-spacing: 0.16em; text-transform: uppercase; color: #9cc7ff; font-weight: 800;">
                    {title}
                </div>
                <div style="font-size: 1.1rem; color: {color}; font-weight: 800;">
                    {icon}
                </div>
            </div>
            <div style="font-size: 2rem; color: white; font-weight: 800; margin-top: 8px;">
                {value}
            </div>
            <div style="font-size: 0.9rem; color: #cbd5e1; margin-top: 8px;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
