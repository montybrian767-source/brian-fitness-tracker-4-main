import streamlit as st


def mission_card(
    workout="Shoulders + Abs",
    recovery="94%",
    readiness="Ready To Train",
    time="58 min",
    description="Lead with clarity, execute each set with control, and finish the session feeling stronger than when you started.",
):
    st.markdown(
        f"""
        <div style="
            padding: 28px 30px;
            border-radius: 28px;
            background: linear-gradient(135deg, rgba(17,24,39,0.98), rgba(23,37,84,0.95));
            border: 1px solid rgba(255,255,255,0.10);
            box-shadow: 0 20px 50px rgba(0,0,0,0.34);
            margin-bottom: 24px;
        ">
            <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:18px; align-items:center;">
                <div style="max-width: 720px;">
                    <div style="color: #93c5fd; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.24em; text-transform: uppercase;">
                        Executive Mission
                    </div>
                    <div style="color: white; font-size: 2rem; font-weight: 800; margin-top: 8px;">
                        {workout}
                    </div>
                    <div style="color: #dbeafe; font-size: 1rem; line-height: 1.6; margin-top: 10px;">
                        {description}
                    </div>
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:10px;">
                    <div style="color: white; background: rgba(34,197,94,0.16); border: 1px solid rgba(34,197,94,0.35); padding: 12px 14px; border-radius: 16px; font-weight: 800;">
                        Recovery • <b>{recovery}</b>
                    </div>
                    <div style="color: white; background: rgba(59,130,246,0.16); border: 1px solid rgba(59,130,246,0.35); padding: 12px 14px; border-radius: 16px; font-weight: 800;">
                        Status • <b>{readiness}</b>
                    </div>
                    <div style="color: white; background: rgba(245,158,11,0.16); border: 1px solid rgba(245,158,11,0.35); padding: 12px 14px; border-radius: 16px; font-weight: 800;">
                        Time • <b>{time}</b>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
