from __future__ import annotations

import json
from datetime import date

import pandas as pd
import streamlit as st

from services.apple_health_import_service import (
    get_apple_activity_daily,
    get_apple_workouts,
    get_import_summary,
    parse_apple_health_export,
)


def _fmt_number(value, digits=0, suffix='') -> str:
    try:
        if value is None or pd.isna(value):
            return f'0{suffix}'
        if digits == 0:
            return f'{int(round(float(value))):,}{suffix}'
        return f'{float(value):.{digits}f}{suffix}'
    except Exception:
        return f'0{suffix}'


def _metric_card(label: str, value: str, subtext: str = '') -> str:
    return f"<div class='apple-card'><div class='apple-label'>{label}</div><div class='apple-value'>{value}</div><div class='small'>{subtext}</div></div>"


def _progress_text(value: float, goal: float) -> str:
    if goal <= 0:
        return 'N/A'
    return f'{min(999.0, (value / goal) * 100.0):.0f}%'


def render_apple_activity_page():
    st.markdown(
        '''
        <style>
        .apple-hero{background:linear-gradient(135deg,#07111f,#0e2744 58%,#123d62);border:1px solid rgba(96,165,250,.38);border-radius:26px;padding:24px;margin:10px 0 18px 0;box-shadow:0 18px 50px rgba(0,0,0,.38)}
        .apple-kicker{font-size:.76rem;letter-spacing:.24em;text-transform:uppercase;color:#7dd3fc;font-weight:950}
        .apple-title{font-size:2.15rem;line-height:1.03;color:#fff;font-weight:950;margin:.35rem 0}
        .apple-sub{color:#c9d7e8;font-size:1rem}
        .apple-card{background:linear-gradient(180deg,#0f1f34,#0b1626);border:1px solid rgba(148,163,184,.18);border-radius:18px;padding:14px;margin:8px 0;box-shadow:0 14px 34px rgba(0,0,0,.24)}
        .apple-label{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#94a3b8;font-weight:900}
        .apple-value{font-size:1.6rem;color:#fff;font-weight:950;line-height:1.1;margin:.2rem 0 .3rem}
        .apple-note{background:linear-gradient(135deg,rgba(14,165,233,.17),rgba(15,23,42,.96));border:1px solid rgba(56,189,248,.35);border-radius:16px;padding:12px 14px}
        </style>
        ''',
        unsafe_allow_html=True,
    )

    st.markdown(
        '''
        <div class="apple-hero">
          <div class="apple-kicker">Brian Fit 7.3 • X.17 Recovery & Readiness Engine</div>
          <div class="apple-title">Apple Activity</div>
          <div class="apple-sub">Manual Apple Health import for ZIP exports or export.xml. This page does not connect to HealthKit directly.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    summary = get_import_summary()
    daily_df, daily_error = get_apple_activity_daily()
    workout_df, workout_error = get_apple_workouts()
    import_result = st.session_state.get('apple_health_last_import_result', {})

    if daily_error or workout_error:
        st.warning('Apple Activity tables are not ready yet. Run the Supabase migration in supabase/apple_activity_schema.sql, then refresh the app.')
        if daily_error:
            st.caption(f'Daily activity query: {daily_error}')
        if workout_error:
            st.caption(f'Workout query: {workout_error}')

    with st.container(border=True):
        st.subheader('Import Apple Health Export')
        st.caption('Accepted formats: .zip or export.xml. The uploaded file is processed in memory or temporary storage and is not retained.')
        uploaded = st.file_uploader('Apple Health Export ZIP or export.xml', type=['zip', 'xml'], key='apple_health_upload')
        if uploaded is not None:
            c1, c2 = st.columns([1.2, 0.8])
            with c1:
                st.caption(f'File: {uploaded.name}')
            with c2:
                if st.button('Process Apple Health Import', type='primary', use_container_width=True, key='apple_health_process'):
                    with st.spinner('Parsing Apple Health export and saving rows to Supabase...'):
                        result = parse_apple_health_export(uploaded)
                    st.session_state['apple_health_last_import_result'] = result
                    st.rerun()

    if import_result:
        st.markdown('### Apple Health import completed')
        r1, r2, r3, r4 = st.columns(4)
        r1.metric('Daily records added', str(int(import_result.get('daily_records_added', 0))))
        r2.metric('Daily records updated', str(int(import_result.get('daily_records_updated', 0))))
        r3.metric('Apple workouts added', str(int(import_result.get('apple_workouts_added', 0))))
        r4.metric('Duplicate workouts skipped', str(int(import_result.get('duplicate_workouts_skipped', 0))))
        info1, info2, info3 = st.columns(3)
        info1.markdown(_metric_card('Import source', str(import_result.get('import_source', 'Apple Health Export')), 'ZIP or export.xml'), unsafe_allow_html=True)
        info2.markdown(_metric_card('Date range', str(import_result.get('date_range', 'No data')), f"{float(import_result.get('duration_seconds', 0.0)):.1f}s import"), unsafe_allow_html=True)
        info3.markdown(_metric_card('Records ignored', str(int(import_result.get('records_ignored', 0))), 'Unsupported or duplicate-like entries'), unsafe_allow_html=True)

        if import_result.get('errors'):
            st.error('Import finished with errors. Review the log below.')
            error_lines = [json.dumps(item, default=str) for item in import_result.get('errors', [])]
            error_log = '\n'.join(error_lines)
            st.download_button('Download Import Error Log', error_log, file_name=f"apple_health_import_errors_{date.today().isoformat()}.txt", mime='text/plain', use_container_width=True)
            with st.expander('Import errors', expanded=False):
                st.code(error_log, language='text')
        else:
            st.success('Apple Health import completed successfully.')

    st.markdown('### Current Apple activity summary')
    latest_daily = daily_df.copy()
    if not latest_daily.empty and 'activity_date' in latest_daily.columns:
        latest_daily['activity_date'] = pd.to_datetime(latest_daily['activity_date'], errors='coerce')
        latest_daily = latest_daily.dropna(subset=['activity_date']).sort_values('activity_date')
    latest_row = latest_daily.iloc[-1].to_dict() if not latest_daily.empty else {}
    current_workout_week = int(summary.get('weekly_workouts', 0))

    s1, s2, s3, s4 = st.columns(4)
    s1.markdown(_metric_card('Move calories', _fmt_number(latest_row.get('active_energy_kcal'), 0, ' kcal'), f"Goal: {_fmt_number(latest_row.get('active_energy_goal_kcal'), 0, ' kcal')}"), unsafe_allow_html=True)
    s2.markdown(_metric_card('Move progress', _progress_text(float(latest_row.get('active_energy_kcal') or 0), float(latest_row.get('active_energy_goal_kcal') or 0)), 'Active energy goal progress'), unsafe_allow_html=True)
    s3.markdown(_metric_card('Exercise minutes', _fmt_number(latest_row.get('exercise_minutes'), 0, ' min'), f"Goal: {_fmt_number(latest_row.get('exercise_goal_minutes'), 0, ' min')}"), unsafe_allow_html=True)
    s4.markdown(_metric_card('Exercise progress', f'{_progress_text(float(latest_row.get('exercise_minutes') or 0), float(latest_row.get('exercise_goal_minutes') or 0))}', f'Apple workouts this week: {current_workout_week}'), unsafe_allow_html=True)

    t1, t2, t3, t4 = st.columns(4)
    t1.markdown(_metric_card('Stand hours', _fmt_number(latest_row.get('stand_hours'), 1, ' hr'), f"Goal: {_fmt_number(latest_row.get('stand_goal_hours'), 1, ' hr')}"), unsafe_allow_html=True)
    t2.markdown(_metric_card('Stand progress', _progress_text(float(latest_row.get('stand_hours') or 0), float(latest_row.get('stand_goal_hours') or 0)), 'Daily stand goal progress'), unsafe_allow_html=True)
    t3.markdown(_metric_card('Steps', _fmt_number(latest_row.get('steps'), 0), f"Distance: {_fmt_number(latest_row.get('walking_running_distance_miles'), 1, ' mi')}"), unsafe_allow_html=True)
    t4.markdown(_metric_card('Resting HR / HRV', f"{_fmt_number(latest_row.get('resting_heart_rate'), 0, ' bpm')} / {_fmt_number(latest_row.get('heart_rate_variability_ms'), 0, ' ms')}", f"Sleep: {_fmt_number(latest_row.get('sleep_hours'), 1, ' hr')}"), unsafe_allow_html=True)

    if not latest_daily.empty:
        chart_df = latest_daily.copy()
        chart_df['activity_date'] = pd.to_datetime(chart_df['activity_date'], errors='coerce')
        chart_df = chart_df.dropna(subset=['activity_date']).sort_values('activity_date').tail(21)
    else:
        chart_df = pd.DataFrame()

    st.markdown('### Apple Activity Dashboard')
    if chart_df.empty:
        st.info('Import Apple Health data to see activity charts.')
    else:
        c1, c2 = st.columns(2)
        c1.markdown('#### Steps by day')
        c1.line_chart(chart_df.set_index('activity_date')['steps'], use_container_width=True)
        c1.markdown('#### Active calories by day')
        c1.line_chart(chart_df.set_index('activity_date')['active_energy_kcal'], use_container_width=True)
        c1.markdown('#### Exercise minutes by day')
        c1.line_chart(chart_df.set_index('activity_date')['exercise_minutes'], use_container_width=True)
        c1.markdown('#### Stand hours by day')
        c1.line_chart(chart_df.set_index('activity_date')['stand_hours'], use_container_width=True)

        c2.markdown('#### Resting heart-rate trend')
        c2.line_chart(chart_df.set_index('activity_date')['resting_heart_rate'], use_container_width=True)
        c2.markdown('#### HRV trend')
        c2.line_chart(chart_df.set_index('activity_date')['heart_rate_variability_ms'], use_container_width=True)
        c2.markdown('#### Sleep trend')
        c2.line_chart(chart_df.set_index('activity_date')['sleep_hours'], use_container_width=True)

    st.markdown('### Apple workout history')
    if workout_df.empty:
        st.info('No Apple workouts imported yet.')
    else:
        workout_sorted = workout_df.copy()
        workout_sorted['start_time'] = pd.to_datetime(workout_sorted['start_time'], errors='coerce')
        workout_sorted = workout_sorted.dropna(subset=['start_time']).sort_values('start_time', ascending=False).head(20)
        for _, row in workout_sorted.iterrows():
            start_time = pd.to_datetime(row.get('start_time'), errors='coerce')
            end_time = pd.to_datetime(row.get('end_time'), errors='coerce')
            header = f"{start_time.date().isoformat() if not pd.isna(start_time) else 'Unknown date'} • {row.get('workout_type', 'Other')} • {_fmt_number(row.get('duration_minutes'), 0, ' min')} • {_fmt_number(row.get('total_energy_kcal'), 0, ' kcal')}"
            with st.expander(header, expanded=False):
                card_cols = st.columns(2)
                card_cols[0].markdown(_metric_card('Start', str(start_time) if not pd.isna(start_time) else 'Unknown', f"End: {str(end_time) if not pd.isna(end_time) else 'Unknown'}"), unsafe_allow_html=True)
                card_cols[1].markdown(_metric_card('Distance / HR', f"{_fmt_number(row.get('total_distance_miles'), 2, ' mi')} • {_fmt_number(row.get('average_heart_rate'), 0, ' bpm')}", f"Max HR: {_fmt_number(row.get('maximum_heart_rate'), 0, ' bpm')}"), unsafe_allow_html=True)
                st.markdown(_metric_card('Device / source', f"{row.get('source_name', 'Apple Health Workout')}" if row.get('source_name') else 'Apple Health Workout', f"Device: {row.get('device', 'Unknown')}"), unsafe_allow_html=True)
                metadata = row.get('metadata')
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {'metadata': metadata}
                st.caption(f"Source label: Apple Health Workout • {row.get('source_name', 'Apple Health')}")
                if metadata:
                    st.markdown('##### Workout details')
                    st.json(metadata)

    st.markdown('### Import snapshot')
    st.markdown(
        f"<div class='apple-note'><b>Last successful import:</b> {summary.get('last_successful_import', 'Unknown')}<br>"
        f"<b>Source:</b> {summary.get('import_source', 'Apple Health Export')}<br>"
        f"<b>Date range imported:</b> {summary.get('date_range', 'No data')}<br>"
        f"<b>Daily records imported:</b> {summary.get('daily_rows', 0)}<br>"
        f"<b>Apple workouts imported:</b> {summary.get('workout_rows', 0)}<br>"
        f"<b>Duplicate records skipped:</b> {summary.get('duplicate_workouts_skipped', 0)}</div>",
        unsafe_allow_html=True,
    )

    st.caption('Apple Activity and Brian Fit strength workouts remain separate. Imported Apple Health data is used as context, not as a medical assessment.')


if __name__ == '__main__':
    render_apple_activity_page()