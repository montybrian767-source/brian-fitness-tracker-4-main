from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


def _safe_num(value: Any, digits: int = 0, suffix: str = '') -> str:
    try:
        if value is None or pd.isna(value):
            return f'N/A{suffix}'
        if digits <= 0:
            return f"{int(round(float(value))):,}{suffix}"
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return f'N/A{suffix}'


def _status_chip(status: str) -> str:
    color = {
        'Ready': '#16a34a',
        'Good': '#22c55e',
        'Moderate': '#eab308',
        'Low': '#f97316',
        'Recovery Day': '#ef4444',
    }.get(status, '#22c55e')
    return f"<span style='display:inline-block;padding:6px 12px;border-radius:999px;background:rgba(15,23,42,.95);border:1px solid {color};color:{color};font-weight:900;font-size:.78rem;'>{status}</span>"


def _render_data_quality_card(data_quality: Dict[str, Any], confidence_score: float):
    st.markdown('### Data Quality')
    st.markdown(
        """
        <div style='background:linear-gradient(145deg,#101a2b,#0a1320);border:1px solid rgba(100,116,139,.35);border-radius:18px;padding:14px;'>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    c1.metric('Apple data days', str(int(data_quality.get('apple_data_days_available', 0))))
    c2.metric('Readiness confidence', f"{int(round(confidence_score))}%")

    c3, c4, c5 = st.columns(3)
    c3.metric('Sleep coverage', f"{_safe_num(data_quality.get('sleep_coverage'), 1, '%')}")
    c4.metric('HRV coverage', f"{_safe_num(data_quality.get('hrv_coverage'), 1, '%')}")
    c5.metric('Resting HR coverage', f"{_safe_num(data_quality.get('resting_hr_coverage'), 1, '%')}")

    c6, c7 = st.columns(2)
    c6.metric('Brian Fit history days', str(int(data_quality.get('strength_history_days', 0))))
    c7.metric('Confidence label', str(data_quality.get('confidence_label', 'Limited data')))

    missing = list(data_quality.get('missing_inputs', []) or [])
    if missing:
        st.caption('Missing inputs: ' + ', '.join(missing))

    notes = list(data_quality.get('history_notes', []) or [])
    for note in notes[:3]:
        st.caption(note)

    st.markdown('</div>', unsafe_allow_html=True)


def _trend_series(history_df: pd.DataFrame, key: str) -> pd.Series:
    if history_df.empty or key not in history_df.columns:
        return pd.Series(dtype=float)
    tmp = history_df[['readiness_date', key]].copy()
    tmp['readiness_date'] = pd.to_datetime(tmp['readiness_date'], errors='coerce')
    tmp[key] = pd.to_numeric(tmp[key], errors='coerce')
    tmp = tmp.dropna(subset=['readiness_date', key]).sort_values('readiness_date')
    if tmp.empty:
        return pd.Series(dtype=float)
    return tmp.set_index('readiness_date')[key]


def render_recovery_readiness_page(readiness_result: Dict[str, Any], readiness_history_df: Optional[pd.DataFrame] = None):
    result = readiness_result or {}
    history_df = readiness_history_df.copy() if isinstance(readiness_history_df, pd.DataFrame) else pd.DataFrame()

    st.markdown(
        """
        <style>
        .rr-hero{background:linear-gradient(135deg,#050c17,#0c213a 54%,#153e63);border:1px solid rgba(96,165,250,.45);border-radius:24px;padding:18px;margin:8px 0 12px;box-shadow:0 14px 36px rgba(0,0,0,.35)}
        .rr-kicker{font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:#7dd3fc;font-weight:900}
        .rr-title{font-size:1.95rem;line-height:1.05;color:#f8fafc;font-weight:950;margin:.3rem 0}
        .rr-sub{color:#bfd7ff}
        .rr-score-wrap{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-top:10px}
        .rr-score{font-size:3.2rem;line-height:1;color:#22c55e;font-weight:950}
        .rr-reco{background:linear-gradient(145deg,#0f1c2e,#0a1421);border:1px solid rgba(34,197,94,.42);border-radius:18px;padding:14px;margin:10px 0}
        .rr-muscle{background:linear-gradient(145deg,#111b2b,#0b1522);border:1px solid rgba(100,116,139,.35);border-radius:14px;padding:12px;margin:8px 0}
        .rr-grid{display:grid;grid-template-columns:1fr;gap:10px}
        @media(min-width:900px){.rr-grid{grid-template-columns:1fr 1fr}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    readiness_score = float(result.get('readiness_score', 50) or 50)
    recovery_status = str(result.get('recovery_status', 'Moderate'))
    confidence_score = float(result.get('confidence_score', 40) or 40)

    recommendation = result.get('recommendation', {}) if isinstance(result.get('recommendation'), dict) else {}

    st.markdown(
        f"""
        <div class='rr-hero'>
            <div class='rr-kicker'>Brian Fit 7.3 • X.17 Recovery & Readiness Engine</div>
            <div class='rr-title'>Recovery & Readiness</div>
            <div class='rr-sub'>Daily training estimate combining Brian Fit and imported Apple Health activity.</div>
            <div class='rr-score-wrap'>
                <div class='rr-score'>{int(round(readiness_score))}</div>
                <div>
                    <div style='color:#cbd5e1;font-size:.8rem;letter-spacing:.11em;text-transform:uppercase;font-weight:900'>Daily Readiness Score</div>
                    {_status_chip(recovery_status)}
                </div>
            </div>
            <div style='margin-top:10px;color:#cbd5e1;'>Training estimate based on Brian Fit and imported Apple Health data. Not a medical assessment.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric('Recommendation', str(recommendation.get('primary_recommendation', 'Moderate Session')))
    m2.metric('Confidence', f"{int(round(confidence_score))}%")
    m3.metric('Last updated', str(result.get('last_updated', 'N/A')).replace('T', ' ')[:16])

    c1, c2, c3 = st.columns(3)
    c1.metric('Sleep score', _safe_num(result.get('sleep_score'), 0))
    c2.metric('HRV score', _safe_num(result.get('hrv_score'), 0))
    c3.metric('Resting HR score', _safe_num(result.get('resting_hr_score'), 0))

    c4, c5, c6 = st.columns(3)
    c4.metric('Activity load', _safe_num(result.get('activity_load_score'), 0))
    c5.metric('Strength load', _safe_num(result.get('strength_load_score'), 0))
    c6.metric('Recovery balance', _safe_num(result.get('recovery_balance_score'), 0))

    data_sources = list(result.get('data_sources_used', []) or [])
    if data_sources:
        st.caption('Data sources used: ' + ', '.join(data_sources))
    else:
        st.caption('Import Apple Health data to improve readiness accuracy.')

    st.markdown('### Daily Recommendation')
    st.markdown(
        f"""
        <div class='rr-reco'>
            <div style='font-size:1.3rem;font-weight:950;color:#f8fafc'>{recommendation.get('primary_recommendation', 'Moderate Session')}</div>
            <div style='color:#cbd5e1;margin-top:8px'><b>Intensity:</b> {recommendation.get('recommended_intensity_percentage', '65-78%')} | <b>Duration:</b> {recommendation.get('suggested_duration', '45-55 minutes')}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>Volume:</b> {recommendation.get('suggested_volume_adjustment', 'Reduce total volume by 20%')}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>RPE ceiling:</b> {recommendation.get('suggested_rpe_ceiling', '7.0')}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>Recommended muscle groups:</b> {', '.join(recommendation.get('recommended_muscle_groups', []) or ['Upper Body Pull'])}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>Reduce or avoid:</b> {', '.join(recommendation.get('reduce_or_avoid_muscle_groups', []) or ['None'])}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>Hydration:</b> {recommendation.get('hydration_note', 'Target 80-120 oz')}</div>
            <div style='color:#cbd5e1;margin-top:6px'><b>Sleep target:</b> {recommendation.get('sleep_target', '7.5-9.0 hours')}</div>
            <div style='color:#e2e8f0;margin-top:10px'><b>Reason:</b> {recommendation.get('coaching_reason', 'Training signals are mixed; use conservative progression.')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('### Positive Factors')
    positives = list(result.get('positive_factors', []) or [])
    if positives:
        for p in positives[:5]:
            st.markdown('- ' + str(p))
    else:
        st.caption('No strong positive factor detected from available data.')

    st.markdown('### Limiting Factors')
    limits = list(result.get('limiting_factors', []) or [])
    if limits:
        for p in limits[:6]:
            st.markdown('- ' + str(p))
    else:
        st.caption('No major limiting factor detected from available data.')

    _render_data_quality_card(result.get('data_quality', {}) if isinstance(result.get('data_quality'), dict) else {}, confidence_score)

    st.markdown('### Muscle Recovery Estimates')
    cards = list(result.get('muscle_recovery_cards', []) or [])
    if not cards:
        st.info('No muscle-level history yet. Log workouts to unlock muscle recovery estimates.')
    else:
        st.markdown("<div class='rr-grid'>", unsafe_allow_html=True)
        for card in cards:
            st.markdown(
                f"""
                <div class='rr-muscle'>
                    <div style='display:flex;justify-content:space-between;gap:8px;align-items:center;'>
                        <div style='font-weight:900;color:#f8fafc'>{card.get('muscle', 'Muscle')}</div>
                        <div style='font-weight:900;color:#22c55e'>{int(card.get('recovery_percentage', 0))}%</div>
                    </div>
                    <div style='color:#cbd5e1;margin-top:5px'><b>Status:</b> {card.get('status', 'Moderate')}</div>
                    <div style='color:#cbd5e1'><b>Last trained:</b> {card.get('last_trained', 'No history')}</div>
                    <div style='color:#cbd5e1'><b>Sets (7d):</b> {card.get('sets_last_7_days', 0)} | <b>Volume:</b> {card.get('recent_volume', 0)}</div>
                    <div style='color:#cbd5e1'><b>Avg RPE:</b> {card.get('average_recent_rpe', 'N/A')}</div>
                    <div style='color:#cbd5e1'><b>Suggested next day:</b> {card.get('suggested_next_training_day', str(date.today()))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('### Recovery Trends')
    if history_df.empty:
        st.info('Readiness history is not available yet. Run the daily_readiness migration to persist trends.')
    else:
        readiness_series = _trend_series(history_df, 'readiness_score')
        sleep_series = _trend_series(history_df, 'sleep_score')
        hrv_series = _trend_series(history_df, 'hrv_score')
        rhr_series = _trend_series(history_df, 'resting_hr_score')
        strength_series = _trend_series(history_df, 'strength_load_score')
        activity_series = _trend_series(history_df, 'activity_load_score')

        if not readiness_series.empty:
            st.markdown('#### Readiness score by day')
            st.line_chart(readiness_series)
        if not sleep_series.empty:
            st.markdown('#### Sleep trend')
            st.line_chart(sleep_series)
        if not hrv_series.empty:
            st.markdown('#### HRV versus baseline trend')
            st.line_chart(hrv_series)
        if not rhr_series.empty:
            st.markdown('#### Resting heart-rate versus baseline trend')
            st.line_chart(rhr_series)
        if not strength_series.empty:
            st.markdown('#### Strength load by day')
            st.line_chart(strength_series)
        if not activity_series.empty:
            st.markdown('#### Apple activity load by day')
            st.line_chart(activity_series)

        if 'recovery_status' in history_df.columns:
            st.markdown('#### Recovery status distribution')
            status_counts = history_df['recovery_status'].astype(str).value_counts()
            if not status_counts.empty:
                st.bar_chart(status_counts)


if __name__ == '__main__':
    render_recovery_readiness_page(readiness_result={})
