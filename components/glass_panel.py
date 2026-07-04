import streamlit as st


def glass_panel(title, body, icon="✨", accent="#3B82F6"):
    html_template = '<div style="background:linear-gradient(145deg,rgba(16,38,63,0.98),rgba(10,23,40,0.95)); border:1px solid rgba(255,255,255,0.1); border-radius:24px; padding:24px; margin-bottom:20px"><div style="display:flex; align-items:center; gap:10px; margin-bottom:12px"><div style="width:38px; height:38px; border-radius:999px; background:rgba(255,255,255,0.1); display:flex; align-items:center; justify-content:center; color:{0}; font-weight:800">{1}</div><div style="font-size:1.15rem; font-weight:800; color:white">{2}</div></div><div style="color:#dbeafe; font-size:1rem; line-height:1.7">{3}</div></div>'
    html = html_template.format(accent, icon, title, body)
    st.markdown(html, unsafe_allow_html=True)
