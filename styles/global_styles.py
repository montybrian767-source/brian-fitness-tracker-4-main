from __future__ import annotations

import textwrap

import streamlit as st

from styles.design_tokens import TOKENS


def inject_global_styles() -> None:
    st.markdown(
        textwrap.dedent(
            f"""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&family=Sora:wght@600;700;800&display=swap');

            :root {{
              --page-gutter: {TOKENS.page_gutter};
              --space-xs: {TOKENS.space_xs};
              --space-sm: {TOKENS.space_sm};
              --space-md: {TOKENS.space_md};
              --space-lg: {TOKENS.space_lg};
              --space-xl: {TOKENS.space_xl};

              --radius-sm: {TOKENS.radius_sm};
              --radius-md: {TOKENS.radius_md};
              --radius-lg: {TOKENS.radius_lg};

              --border-subtle: {TOKENS.border_subtle};
              --border-strong: {TOKENS.border_strong};

              --shadow-soft: {TOKENS.shadow_soft};
              --shadow-card: {TOKENS.shadow_card};

              --button-height: {TOKENS.button_height};
              --button-gap: {TOKENS.button_gap};

              --font-body: {TOKENS.font_body};
              --font-heading: {TOKENS.font_heading};
              --font-size-body: {TOKENS.font_size_body};
              --font-size-caption: {TOKENS.font_size_caption};
              --font-size-h1: {TOKENS.font_size_h1};
              --font-size-h2: {TOKENS.font_size_h2};
              --font-size-h3: {TOKENS.font_size_h3};

              --motion-fast: {TOKENS.motion_fast};
              --motion-normal: {TOKENS.motion_normal};
              --motion-curve: {TOKENS.motion_curve};

              --text-body: {TOKENS.text_body};
              --text-muted: {TOKENS.text_muted};
              --text-heading: {TOKENS.text_heading};

              --status-success: {TOKENS.status_success};
              --status-warning: {TOKENS.status_warning};
              --status-error: {TOKENS.status_error};
              --status-info: {TOKENS.status_info};
            }}

            html, body, [class*="css"] {{
              font-family: var(--font-body);
              font-size: var(--font-size-body);
              color: var(--text-body);
            }}

            h1, h2, h3, h4, .title, .side-title {{
              font-family: var(--font-heading);
              color: var(--text-heading);
            }}

            h1 {{ font-size: var(--font-size-h1); }}
            h2 {{ font-size: var(--font-size-h2); }}
            h3 {{ font-size: var(--font-size-h3); }}
            .stCaption {{ font-size: var(--font-size-caption); }}

            .stApp {{
              background: radial-gradient(circle at 8% 0%, #12325b 0%, #07111f 42%, #03060d 100%);
              color: var(--text-body);
            }}

            .block-container {{
              max-width: {TOKENS.page_max_width}px;
              padding-top: 0.7rem;
              padding-bottom: 2.5rem;
              padding-left: var(--page-gutter);
              padding-right: var(--page-gutter);
              animation: fadeRise var(--motion-normal) var(--motion-curve);
            }}

            .metric-card,
            .side-card,
            .history-session-card,
            .chart-shell {{
              border-radius: var(--radius-md);
              border: var(--border-subtle);
              box-shadow: var(--shadow-soft);
              transition: transform var(--motion-fast) var(--motion-curve), border-color var(--motion-fast) var(--motion-curve), box-shadow var(--motion-fast) var(--motion-curve);
            }}

            .metric-card:hover,
            .side-card:hover,
            .history-session-card:hover,
            .chart-shell:hover {{
              transform: translateY(-1px);
              border-color: rgba(96, 165, 250, 0.45);
              box-shadow: var(--shadow-card);
            }}

            .stButton > button,
            .stDownloadButton > button {{
              min-height: var(--button-height);
              border-radius: var(--radius-sm);
              font-weight: 800;
              transition: transform var(--motion-fast) var(--motion-curve), box-shadow var(--motion-fast) var(--motion-curve);
              margin-bottom: var(--button-gap);
            }}

            .stButton > button:hover,
            .stDownloadButton > button:hover {{
              transform: translateY(-1px);
              box-shadow: 0 10px 24px rgba(0, 0, 0, 0.32);
            }}

            div[data-testid="stAlert"] {{
              border-radius: var(--radius-sm);
              border: var(--border-subtle);
            }}

            div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
              margin: 0;
              line-height: 1.4;
            }}

            div[data-testid="stPlotlyChart"],
            .stLineChart,
            .stBarChart {{
              border: var(--border-subtle);
              border-radius: var(--radius-md);
              background: linear-gradient(160deg, #0b1628, #0a1322);
              padding: 6px;
            }}

            .status-ok {{
              color: var(--status-success);
            }}

            .status-warn {{
              color: var(--status-warning);
            }}

            .status-error {{
              color: var(--status-error);
            }}

            .mobile-nav-shell {{
              border-radius: var(--radius-lg);
              border: var(--border-strong);
              box-shadow: var(--shadow-card);
            }}

            @keyframes fadeRise {{
              from {{ opacity: 0; transform: translateY(4px); }}
              to {{ opacity: 1; transform: translateY(0); }}
            }}

            @media (max-width: 900px) {{
              .stApp {{
                padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 104px);
              }}

              .mobile-nav-shell {{
                position: fixed;
                left: 10px;
                right: 10px;
                bottom: calc(env(safe-area-inset-bottom, 0px) + 10px);
                z-index: 999;
                background: rgba(4, 11, 22, 0.96);
                backdrop-filter: blur(10px);
                padding: 8px;
                margin: 0;
              }}

              .mobile-nav-shell div[role="radiogroup"] {{
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 6px;
              }}

              .mobile-nav-shell label {{
                min-height: 44px;
                border-radius: 12px;
                text-align: center;
                justify-content: center;
                margin: 0;
                padding: 8px 6px;
              }}
            }}
            </style>
            """
        ),
        unsafe_allow_html=True,
    )
