from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import streamlit as st

from services.apple_health_import_service import (
    get_apple_activity_daily,
    get_apple_workout_day_aggregate,
    get_apple_workout_types_present,
    get_apple_workouts,
    get_apple_workouts_total_count,
    get_daily_readiness_history,
    get_import_summary,
    parse_apple_health_export,
)
from services.supabase_service import get_workouts


FIXED_TYPES = [
    'Pickleball',
    'Walking',
    'Cycling',
    'Swimming',
    'Traditional Strength Training',
    'Functional Strength Training',
]

DATE_RANGE_OPTIONS = [
    'Last 7 Days',
    'Last 30 Days',
    'Last 90 Days',
    'This Year',
    'Last Year',
    'All Time',
    'Custom Range',
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    return int(round(_safe_float(value, float(default))))


def _fmt_num(value: Any, digits: int = 0, suffix: str = '') -> str:
    number = _safe_float(value, 0.0)
    if digits <= 0:
        return f'{int(round(number)):,}{suffix}'
    return f'{number:.{digits}f}{suffix}'


def _fmt_dt(value: Any) -> str:
    ts = pd.to_datetime(value, errors='coerce', utc=True)
    if pd.isna(ts):
        return 'Unknown'
    return ts.strftime('%Y-%m-%d %H:%M UTC')


def _workout_category(workout_type: str) -> str:
    text = str(workout_type or '').strip()
    if text in FIXED_TYPES:
        return text
    return 'Other'


def _date_range_to_bounds(option: str, custom_start: Optional[date], custom_end: Optional[date]) -> Tuple[Optional[str], Optional[str]]:
    today = date.today()
    if option == 'Last 7 Days':
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    if option == 'Last 30 Days':
        return (today - timedelta(days=29)).isoformat(), today.isoformat()
    if option == 'Last 90 Days':
        return (today - timedelta(days=89)).isoformat(), today.isoformat()
    if option == 'This Year':
        return date(today.year, 1, 1).isoformat(), today.isoformat()
    if option == 'Last Year':
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)
        return start.isoformat(), end.isoformat()
    if option == 'Custom Range':
        start = custom_start.isoformat() if custom_start else None
        end = custom_end.isoformat() if custom_end else None
        return start, end
    return None, None


def _to_workout_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    if df.empty:
        return pd.DataFrame(
            columns=[
                'apple_workout_key', 'workout_type', 'start_time', 'end_time', 'duration_minutes', 'total_energy_kcal',
                'total_distance_miles', 'average_heart_rate', 'maximum_heart_rate', 'source_name', 'source_version',
                'device', 'metadata', 'imported_at',
            ]
        )
    for col in ['start_time', 'end_time', 'imported_at']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
        else:
            df[col] = pd.NaT
    for col in ['duration_minutes', 'total_energy_kcal', 'total_distance_miles', 'average_heart_rate', 'maximum_heart_rate']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0
    if 'workout_type' not in df.columns:
        df['workout_type'] = 'Other'
    if 'source_name' not in df.columns:
        df['source_name'] = ''
    if 'device' not in df.columns:
        df['device'] = ''
    df['workout_category'] = df['workout_type'].apply(_workout_category)
    return df


def _df_theme() -> alt.Chart:
    return alt.Chart().configure(
        background='transparent',
        axis=alt.AxisConfig(labelColor='#cbd5e1', titleColor='#cbd5e1', gridColor='#1f334c'),
        legend=alt.LegendConfig(labelColor='#dbeafe', titleColor='#dbeafe'),
        title=alt.TitleConfig(color='#ffffff'),
        view=alt.ViewConfig(stroke=None),
    )


@st.cache_data(ttl=60)
def _cached_readiness_score() -> Optional[float]:
    history, err = get_daily_readiness_history(days=3)
    if err or history.empty:
        return None
    score_series = pd.to_numeric(history.get('readiness_score'), errors='coerce').dropna()
    if score_series.empty:
        return None
    return float(score_series.iloc[-1])


@st.cache_data(ttl=60)
def _cached_workout_page(filters: Dict[str, Any], limit: int, offset: int) -> Tuple[pd.DataFrame, Optional[int], Optional[str]]:
    rows, total_count, err = get_apple_workouts(
        date_from=filters.get('date_from'),
        date_to=filters.get('date_to'),
        workout_type=filters.get('workout_type'),
        limit=int(limit),
        offset=int(offset),
        min_duration_minutes=filters.get('min_duration_minutes'),
        has_calories=filters.get('has_calories'),
        has_distance=filters.get('has_distance'),
        has_heart_rate=filters.get('has_heart_rate'),
    )
    return _to_workout_df(rows), total_count, err


@st.cache_data(ttl=60)
def _cached_all_filtered(filters: Dict[str, Any]) -> Tuple[pd.DataFrame, Optional[str]]:
    all_rows: List[Dict[str, Any]] = []
    offset = 0
    page_size = 250

    while True:
        rows, _, err = get_apple_workouts(
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to'),
            workout_type=filters.get('workout_type'),
            limit=page_size,
            offset=offset,
            min_duration_minutes=filters.get('min_duration_minutes'),
            has_calories=filters.get('has_calories'),
            has_distance=filters.get('has_distance'),
            has_heart_rate=filters.get('has_heart_rate'),
        )
        if err and not all_rows:
            return _to_workout_df([]), err
        chunk = rows or []
        all_rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
        if offset > 10000:
            break

    return _to_workout_df(all_rows), None


@st.cache_data(ttl=60)
def _cached_unfiltered_all() -> Tuple[pd.DataFrame, Optional[str]]:
    return _cached_all_filtered({
        'date_from': None,
        'date_to': None,
        'workout_type': 'All',
        'min_duration_minutes': None,
        'has_calories': False,
        'has_distance': False,
        'has_heart_rate': False,
    })


@st.cache_data(ttl=60)
def _cached_brian_workouts() -> pd.DataFrame:
    rows, err = get_workouts(days=None)
    if err:
        return pd.DataFrame()
    df = pd.DataFrame(rows or [])
    if df.empty:
        return df
    if 'workout_date' in df.columns:
        df['workout_date'] = pd.to_datetime(df['workout_date'], errors='coerce').dt.date.astype(str)
    else:
        df['workout_date'] = ''
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce', utc=True)
    else:
        df['created_at'] = pd.NaT
    for col in ['exercise', 'day', 'workout_session_id']:
        if col not in df.columns:
            df[col] = ''
    return df


def _strength_match_for_workout(apple_row: pd.Series, brian_df: pd.DataFrame) -> Tuple[Optional[str], pd.DataFrame]:
    if brian_df.empty:
        return None, pd.DataFrame()

    start_ts = pd.to_datetime(apple_row.get('start_time'), errors='coerce', utc=True)
    if pd.isna(start_ts):
        return None, pd.DataFrame()

    workout_date = start_ts.date().isoformat()
    candidates = brian_df[brian_df['workout_date'] == workout_date].copy()
    if candidates.empty:
        return None, pd.DataFrame()

    if 'workout_session_id' in candidates.columns:
        sid_series = candidates['workout_session_id'].astype(str).str.strip()
        grouped = candidates.assign(_sid=sid_series).groupby('_sid', as_index=False)
        non_empty = [g for sid, g in grouped if sid]
        if non_empty:
            def _rank(group_df: pd.DataFrame) -> float:
                if 'created_at' in group_df.columns and group_df['created_at'].notna().any():
                    diff = (group_df['created_at'].dropna() - start_ts).abs().min().total_seconds()
                    return float(diff)
                return 999999.0

            best_group = sorted(non_empty, key=_rank)[0]
            sid = str(best_group['workout_session_id'].iloc[0]).strip()
            return sid if sid else None, best_group

    return None, candidates


def _render_calendar(day_df: pd.DataFrame, filters: Dict[str, Any]):
    if 'calendar_anchor' not in st.session_state:
        now = date.today()
        st.session_state['calendar_anchor'] = date(now.year, now.month, 1)

    c1, c2, c3 = st.columns([1, 2, 1])
    if c1.button('Prev Month', width='stretch', key='apple_cal_prev'):
        anchor = st.session_state['calendar_anchor']
        prev_month = (anchor.month - 2) % 12 + 1
        prev_year = anchor.year - 1 if anchor.month == 1 else anchor.year
        st.session_state['calendar_anchor'] = date(prev_year, prev_month, 1)
    if c3.button('Next Month', width='stretch', key='apple_cal_next'):
        anchor = st.session_state['calendar_anchor']
        next_month = (anchor.month % 12) + 1
        next_year = anchor.year + 1 if anchor.month == 12 else anchor.year
        st.session_state['calendar_anchor'] = date(next_year, next_month, 1)

    anchor = st.session_state['calendar_anchor']
    c2.markdown(f"### {anchor.strftime('%B %Y')}")

    if day_df.empty:
        st.info('No calendar data for current filters.')
        return

    month_start = date(anchor.year, anchor.month, 1)
    month_end = date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])

    day_df = day_df.copy()
    day_df['day'] = pd.to_datetime(day_df['day'], errors='coerce').dt.date
    day_df = day_df.dropna(subset=['day'])
    day_df = day_df[(day_df['day'] >= month_start) & (day_df['day'] <= month_end)]

    by_day = {
        d['day']: d
        for _, d in day_df.iterrows()
    }

    week_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = st.columns(7)
    for i, wd in enumerate(week_days):
        cols[i].markdown(f'**{wd}**')

    month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year, anchor.month)
    for week in month_matrix:
        cols = st.columns(7)
        for i, day_value in enumerate(week):
            if day_value.month != anchor.month:
                cols[i].caption('')
                continue
            info = by_day.get(day_value)
            workouts = _safe_int(info.get('workouts', 0), 0) if info is not None else 0
            minutes = _safe_int(info.get('minutes', 0), 0) if info is not None else 0
            dominant = str(info.get('dominant_workout_type', '')) if info is not None else ''
            label = f"{day_value.day} | {workouts}w | {minutes}m"
            if cols[i].button(label, key=f'apple_cal_day_{day_value.isoformat()}', width='stretch'):
                st.session_state['apple_selected_date'] = day_value.isoformat()
                st.session_state['apple_filters'] = {
                    **filters,
                    'date_from': day_value.isoformat(),
                    'date_to': day_value.isoformat(),
                }
                st.session_state['apple_page_num'] = 1
                st.rerun()
            if dominant:
                cols[i].caption(dominant[:16])



def render_apple_activity_page():
    st.markdown(
        '''
        <style>
        .apple-hero{background:linear-gradient(135deg,#061423,#0c2b44 55%,#1d4b64);border:1px solid rgba(125,211,252,.28);border-radius:24px;padding:20px;margin:8px 0 16px 0;box-shadow:0 16px 44px rgba(0,0,0,.34)}
        .apple-kicker{font-size:.74rem;letter-spacing:.22em;text-transform:uppercase;color:#93c5fd;font-weight:900}
        .apple-title{font-size:2.05rem;line-height:1.04;color:#fff;font-weight:950;margin:.35rem 0}
        .apple-sub{color:#d1d5db;font-size:.98rem}
        .intel-card{background:linear-gradient(180deg,#0b1a2d,#0c2038);border:1px solid rgba(148,163,184,.2);border-radius:16px;padding:12px;min-height:106px}
        .intel-label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#9ca3af;font-weight:800}
        .intel-value{font-size:1.45rem;color:#fff;font-weight:900;line-height:1.1;margin-top:6px}
        .intel-sub{font-size:.85rem;color:#bfdbfe;margin-top:4px}
        .timeline-card{background:linear-gradient(180deg,#0a1525,#0f1f35);border:1px solid rgba(96,165,250,.18);border-radius:16px;padding:12px;margin-bottom:10px}
        .badge{display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(14,165,233,.18);border:1px solid rgba(56,189,248,.35);color:#dbeafe;font-size:.74rem;font-weight:800;margin-right:6px;margin-bottom:6px}
        .section-shell{background:linear-gradient(180deg,#081223,#0b1b31);border:1px solid rgba(148,163,184,.16);border-radius:18px;padding:14px;margin-top:12px}
        @media (max-width: 768px){
          .apple-title{font-size:1.55rem}
          .intel-card{min-height:96px}
        }
        </style>
        ''',
        unsafe_allow_html=True,
    )

    st.markdown(
        '''
        <div class="apple-hero">
          <div class="apple-kicker">Brian Fit 7.4 • X.18 Apple Intelligence Dashboard</div>
          <div class="apple-title">Apple Intelligence</div>
          <div class="apple-sub">Full Apple workout intelligence with fast pagination, filter control, and Brian Fit training context.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if 'apple_filters' not in st.session_state:
        st.session_state['apple_filters'] = {
            'date_range': 'All Time',
            'date_from': None,
            'date_to': None,
            'workout_type': 'All',
            'min_duration_minutes': None,
            'has_calories': False,
            'has_distance': False,
            'has_heart_rate': False,
        }
    if 'apple_rows_per_page' not in st.session_state:
        st.session_state['apple_rows_per_page'] = 25
    if 'apple_page_num' not in st.session_state:
        st.session_state['apple_page_num'] = 1

    with st.container(border=True):
        st.subheader('Import Apple Health Export')
        st.caption('Accepted formats: .zip or export.xml. This import path is isolated from normal page navigation.')
        uploaded = st.file_uploader('Apple Health Export ZIP or export.xml', type=['zip', 'xml'], key='apple_health_upload')
        c1, c2 = st.columns([1.2, 0.8])
        with c1:
            if uploaded is not None:
                st.caption(f'File selected: {uploaded.name}')
        with c2:
            if uploaded is not None and st.button('Process Apple Health Import', type='primary', width='stretch', key='apple_health_process'):
                with st.spinner('Parsing Apple Health export and saving rows to Supabase...'):
                    result = parse_apple_health_export(uploaded)
                st.session_state['apple_health_last_import_result'] = result
                st.session_state['apple_health_import_cache_nonce'] = datetime.now().isoformat()
                _cached_workout_page.clear()
                _cached_all_filtered.clear()
                _cached_unfiltered_all.clear()
                _cached_readiness_score.clear()
                _cached_brian_workouts.clear()
                st.rerun()

    import_result = st.session_state.get('apple_health_last_import_result', {})
    if import_result:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric('Daily added', _safe_int(import_result.get('daily_records_added', 0)))
        r2.metric('Daily updated', _safe_int(import_result.get('daily_records_updated', 0)))
        r3.metric('Workouts added', _safe_int(import_result.get('apple_workouts_added', 0)))
        r4.metric('Duplicates skipped', _safe_int(import_result.get('duplicate_workouts_skipped', 0)))

    filter_box = st.container(border=True)
    with filter_box:
        st.subheader('Filters')
        known_types, types_err = get_apple_workout_types_present()
        options = ['All'] + FIXED_TYPES + ['Other']
        for wt in known_types:
            if wt and wt not in options and wt not in FIXED_TYPES:
                options.append(wt)

        with st.form('apple_filter_form', clear_on_submit=False):
            fc1, fc2 = st.columns(2)
            range_value = fc1.selectbox('Date range', DATE_RANGE_OPTIONS, index=DATE_RANGE_OPTIONS.index(st.session_state['apple_filters'].get('date_range', 'All Time')))
            type_value = fc2.selectbox('Workout type', options, index=options.index(st.session_state['apple_filters'].get('workout_type', 'All')) if st.session_state['apple_filters'].get('workout_type', 'All') in options else 0)

            custom_start = None
            custom_end = None
            if range_value == 'Custom Range':
                cc1, cc2 = st.columns(2)
                stored_start = st.session_state['apple_filters'].get('date_from')
                stored_end = st.session_state['apple_filters'].get('date_to')
                start_default = pd.to_datetime(stored_start, errors='coerce').date() if stored_start else date.today() - timedelta(days=30)
                end_default = pd.to_datetime(stored_end, errors='coerce').date() if stored_end else date.today()
                custom_start = cc1.date_input('Custom start', value=start_default)
                custom_end = cc2.date_input('Custom end', value=end_default)

            ec1, ec2, ec3, ec4 = st.columns(4)
            min_duration = ec1.number_input('Minimum duration (min)', min_value=0, value=int(st.session_state['apple_filters'].get('min_duration_minutes') or 0), step=5)
            has_calories = ec2.checkbox('Has calories', value=bool(st.session_state['apple_filters'].get('has_calories', False)))
            has_distance = ec3.checkbox('Has distance', value=bool(st.session_state['apple_filters'].get('has_distance', False)))
            has_hr = ec4.checkbox('Has heart-rate data', value=bool(st.session_state['apple_filters'].get('has_heart_rate', False)))

            a1, a2 = st.columns(2)
            apply_filters = a1.form_submit_button('Apply Filters', width='stretch')
            clear_filters = a2.form_submit_button('Clear Filters', width='stretch')

            if apply_filters:
                date_from, date_to = _date_range_to_bounds(range_value, custom_start, custom_end)
                st.session_state['apple_filters'] = {
                    'date_range': range_value,
                    'date_from': date_from,
                    'date_to': date_to,
                    'workout_type': type_value,
                    'min_duration_minutes': float(min_duration) if min_duration > 0 else None,
                    'has_calories': bool(has_calories),
                    'has_distance': bool(has_distance),
                    'has_heart_rate': bool(has_hr),
                }
                st.session_state['apple_page_num'] = 1
                st.rerun()

            if clear_filters:
                st.session_state['apple_filters'] = {
                    'date_range': 'All Time',
                    'date_from': None,
                    'date_to': None,
                    'workout_type': 'All',
                    'min_duration_minutes': None,
                    'has_calories': False,
                    'has_distance': False,
                    'has_heart_rate': False,
                }
                st.session_state['apple_page_num'] = 1
                st.rerun()

    filters = dict(st.session_state['apple_filters'])
    rows_per_page = int(st.session_state.get('apple_rows_per_page', 25))
    page_num = max(1, int(st.session_state.get('apple_page_num', 1)))
    offset = (page_num - 1) * rows_per_page

    page_df, total_count, page_err = _cached_workout_page(filters, rows_per_page, offset)

    if page_err and page_df.empty:
        st.warning('Apple workouts are temporarily unavailable. The rest of Brian Fit remains usable.')
        st.caption(str(page_err))
        return

    if total_count is None:
        st.info('Limited count mode: loaded rows are shown, but total count is unavailable right now.')

    all_filtered_df, all_filtered_err = _cached_all_filtered(filters)
    if all_filtered_err and all_filtered_df.empty:
        all_filtered_df = page_df.copy()

    unfiltered_df, unfiltered_err = _cached_unfiltered_all()
    readiness = _cached_readiness_score()

    now_utc = pd.Timestamp.now(tz='UTC')
    week_cutoff = now_utc - pd.Timedelta(days=7)
    month_cutoff = now_utc - pd.Timedelta(days=30)

    stat_source = unfiltered_df if not unfiltered_df.empty else all_filtered_df
    weekly_df = stat_source[stat_source['start_time'] >= week_cutoff] if not stat_source.empty else pd.DataFrame()
    monthly_df = stat_source[stat_source['start_time'] >= month_cutoff] if not stat_source.empty else pd.DataFrame()

    most_common = 'N/A'
    if not stat_source.empty:
        counts = stat_source['workout_type'].value_counts()
        if not counts.empty:
            most_common = str(counts.index[0])

    latest_workout = page_df.iloc[0].to_dict() if not page_df.empty else {}
    longest_recent = monthly_df.sort_values('duration_minutes', ascending=False).head(1)
    longest_text = 'N/A'
    if not longest_recent.empty:
        row = longest_recent.iloc[0]
        longest_text = f"{_fmt_num(row.get('duration_minutes'), 0, ' min')} • {row.get('workout_type', 'Other')}"

    top_cards = [
        ('Workouts this week', _fmt_num(len(weekly_df))),
        ('Workouts this month', _fmt_num(len(monthly_df))),
        ('Exercise minutes this week', _fmt_num(weekly_df['duration_minutes'].sum() if not weekly_df.empty else 0, 0, ' min')),
        ('Active calories this week', _fmt_num(weekly_df['total_energy_kcal'].sum() if not weekly_df.empty else 0, 0, ' kcal')),
        ('Most common type', most_common),
        ('Longest recent workout', longest_text),
        ('Average duration', _fmt_num(stat_source['duration_minutes'].mean() if not stat_source.empty else 0, 1, ' min')),
        ('Average workout HR', _fmt_num(stat_source[stat_source['average_heart_rate'] > 0]['average_heart_rate'].mean() if not stat_source.empty else 0, 0, ' bpm')),
        ('Latest workout', f"{latest_workout.get('workout_type', 'N/A')} • {_fmt_dt(latest_workout.get('start_time'))}"),
        ('Current readiness score', _fmt_num(readiness, 0) if readiness is not None else 'N/A'),
    ]

    st.markdown('### Apple Intelligence Dashboard')
    for i in range(0, len(top_cards), 2):
        cols = st.columns(2)
        for col, (label, value) in zip(cols, top_cards[i:i + 2]):
            col.markdown(
                f"<div class='intel-card'><div class='intel-label'>{label}</div><div class='intel-value'>{value}</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown('### Workout Type Summary')
    summary_df = all_filtered_df.copy()
    if summary_df.empty:
        st.info('No workouts match current filters.')
    else:
        summary_df['start_day'] = summary_df['start_time'].dt.date.astype(str)
        cards = []
        for workout_type in FIXED_TYPES + ['Other']:
            if workout_type == 'Other':
                subset = summary_df[~summary_df['workout_type'].isin(FIXED_TYPES)]
            else:
                subset = summary_df[summary_df['workout_type'] == workout_type]
            if subset.empty:
                cards.append((workout_type, 0, 0.0, 0.0, 0.0, 'N/A'))
                continue
            cards.append((
                workout_type,
                int(len(subset)),
                float(subset['duration_minutes'].sum()),
                float(subset['total_energy_kcal'].sum()),
                float(subset['duration_minutes'].mean()),
                str(subset['start_time'].max().date()),
            ))

        for i in range(0, len(cards), 2):
            cols = st.columns(2)
            for col, item in zip(cols, cards[i:i + 2]):
                wt, sessions, total_duration, total_calories, avg_duration, last_date = item
                col.markdown(
                    f"<div class='section-shell'><div class='intel-label'>{wt}</div>"
                    f"<div class='intel-sub'>Sessions: {sessions}</div>"
                    f"<div class='intel-sub'>Total duration: {_fmt_num(total_duration, 0, ' min')}</div>"
                    f"<div class='intel-sub'>Total calories: {_fmt_num(total_calories, 0, ' kcal')}</div>"
                    f"<div class='intel-sub'>Average duration: {_fmt_num(avg_duration, 1, ' min')}</div>"
                    f"<div class='intel-sub'>Most recent: {last_date}</div></div>",
                    unsafe_allow_html=True,
                )

    st.markdown('### Apple Workout Timeline')
    p1, p2, p3 = st.columns([1.2, 1.2, 1.6])
    with p1:
        rows_choice = st.selectbox('Rows per page', [10, 25, 50], index=[10, 25, 50].index(rows_per_page), key='apple_rows_choice')
        if int(rows_choice) != rows_per_page:
            st.session_state['apple_rows_per_page'] = int(rows_choice)
            st.session_state['apple_page_num'] = 1
            st.rerun()
    with p2:
        if st.button('Previous Page', width='stretch', disabled=page_num <= 1, key='apple_prev_page'):
            st.session_state['apple_page_num'] = max(1, page_num - 1)
            st.rerun()
    with p3:
        next_disabled = total_count is not None and (offset + len(page_df) >= total_count)
        if st.button('Next Page', width='stretch', disabled=bool(next_disabled), key='apple_next_page'):
            st.session_state['apple_page_num'] = page_num + 1
            st.rerun()

    start_idx = offset + 1 if len(page_df) > 0 else 0
    end_idx = offset + len(page_df)
    total_text = str(total_count) if total_count is not None else 'unknown'
    st.caption(f'Displaying {start_idx}-{end_idx} of {total_text} Apple workouts • Page {page_num}')

    if page_df.empty:
        st.info('No Apple workouts match current filters.')
    else:
        brian_df = _cached_brian_workouts()
        for _, row in page_df.iterrows():
            start_time = _fmt_dt(row.get('start_time'))
            end_time = _fmt_dt(row.get('end_time'))
            duration = _fmt_num(row.get('duration_minutes'), 0, ' min')
            calories = _fmt_num(row.get('total_energy_kcal'), 0, ' kcal')
            distance = _fmt_num(row.get('total_distance_miles'), 2, ' mi')
            avg_hr = _fmt_num(row.get('average_heart_rate'), 0, ' bpm') if _safe_float(row.get('average_heart_rate')) > 0 else 'N/A'
            max_hr = _fmt_num(row.get('maximum_heart_rate'), 0, ' bpm') if _safe_float(row.get('maximum_heart_rate')) > 0 else 'N/A'
            source = str(row.get('source_name', '') or 'Apple Health')
            device = str(row.get('device', '') or 'Unknown device')

            st.markdown(
                f"<div class='timeline-card'>"
                f"<span class='badge'>{str(row.get('workout_type', 'Other'))}</span>"
                f"<span class='badge'>{str(pd.to_datetime(row.get('start_time'), errors='coerce', utc=True).date() if not pd.isna(pd.to_datetime(row.get('start_time'), errors='coerce', utc=True)) else 'Unknown')}</span>"
                f"<div class='intel-sub'>Start: {start_time}</div>"
                f"<div class='intel-sub'>Duration: {duration} | Calories: {calories} | Distance: {distance}</div>"
                f"<div class='intel-sub'>Avg HR: {avg_hr} | Max HR: {max_hr}</div>"
                f"<div class='intel-sub'>Device/Source: {device} • {source}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            if 'strength' in str(row.get('workout_type', '')).lower():
                st.markdown('**Apple Watch Session Summary**')
                st.caption(f"{str(row.get('workout_type', 'Strength'))} • {duration} • {calories}")
                sid, matched_rows = _strength_match_for_workout(row, brian_df)
                st.markdown('**Brian Fit Exercise Details**')
                if matched_rows.empty:
                    st.info('No Brian Fit strength session matched this Apple Watch workout.')
                else:
                    if sid:
                        st.caption(f'Matched workout_session_id: {sid}')
                    for ex in sorted(set(matched_rows['exercise'].astype(str).tolist())):
                        ex_rows = matched_rows[matched_rows['exercise'].astype(str) == ex]
                        st.caption(
                            f"{ex}: {len(ex_rows)} sets • reps avg {_fmt_num(pd.to_numeric(ex_rows.get('reps', 0), errors='coerce').mean(), 1)} • weight avg {_fmt_num(pd.to_numeric(ex_rows.get('weight_lbs', 0), errors='coerce').mean(), 1, ' lbs')}"
                        )

    st.markdown('### Activity Calendar')
    calendar_df, calendar_err = get_apple_workout_day_aggregate(
        date_from=filters.get('date_from'),
        date_to=filters.get('date_to'),
        workout_type=filters.get('workout_type'),
    )
    if calendar_err and calendar_df.empty:
        st.warning('Calendar data is temporarily unavailable.')
        st.caption(calendar_err)
    else:
        _render_calendar(calendar_df, filters)

    analytics_toggle = st.toggle('Load Analytics', value=False, key='apple_show_analytics')
    if analytics_toggle:
        st.markdown('### Analytics')
        chart_df = all_filtered_df.copy()
        if chart_df.empty:
            st.info('No data available for analytics with current filters.')
        else:
            chart_df['week'] = chart_df['start_time'].dt.to_period('W').astype(str)
            by_week = chart_df.groupby('week', as_index=False).agg(
                workouts=('apple_workout_key', 'count'),
                minutes=('duration_minutes', 'sum'),
                calories=('total_energy_kcal', 'sum'),
            )
            type_dist = chart_df.groupby('workout_type', as_index=False).size().rename(columns={'size': 'sessions'})
            avg_duration = chart_df.groupby('workout_type', as_index=False)['duration_minutes'].mean()

            heart_df = chart_df[chart_df['average_heart_rate'] > 0].copy()
            distance_df = chart_df[(chart_df['total_distance_miles'] > 0) & (chart_df['duration_minutes'] > 0)].copy()
            distance_df = distance_df[distance_df['workout_type'].isin(['Walking', 'Cycling', 'Swimming'])]
            if not distance_df.empty:
                distance_df['speed_mph'] = distance_df['total_distance_miles'] / (distance_df['duration_minutes'] / 60.0)
                distance_df['pace_min_mile'] = distance_df['duration_minutes'] / distance_df['total_distance_miles']

            pkl_df = chart_df[chart_df['workout_type'] == 'Pickleball'].copy()
            if not pkl_df.empty:
                pkl_df['month'] = pkl_df['start_time'].dt.to_period('M').astype(str)
                pkl_by_month = pkl_df.groupby('month', as_index=False).size().rename(columns={'size': 'sessions'})
            else:
                pkl_by_month = pd.DataFrame(columns=['month', 'sessions'])

            charts = st.container()
            with charts:
                c1, c2 = st.columns(2)
                c1.altair_chart(
                    alt.Chart(by_week).mark_line(point=True).encode(x='week:N', y='workouts:Q').properties(height=220),
                    width='stretch',
                )
                c2.altair_chart(
                    alt.Chart(by_week).mark_line(point=True).encode(x='week:N', y='minutes:Q').properties(height=220),
                    width='stretch',
                )

                c3, c4 = st.columns(2)
                c3.altair_chart(
                    alt.Chart(by_week).mark_bar().encode(x='week:N', y='calories:Q').properties(height=220),
                    width='stretch',
                )
                c4.altair_chart(
                    alt.Chart(type_dist).mark_arc(innerRadius=45).encode(theta='sessions:Q', color='workout_type:N').properties(height=220),
                    width='stretch',
                )

                c5, c6 = st.columns(2)
                c5.altair_chart(
                    alt.Chart(avg_duration).mark_bar().encode(x='workout_type:N', y='duration_minutes:Q').properties(height=220),
                    width='stretch',
                )
                if not heart_df.empty:
                    heart_trend = heart_df.sort_values('start_time').tail(300)
                    c6.altair_chart(
                        alt.Chart(heart_trend).mark_line(point=False).encode(x='start_time:T', y='average_heart_rate:Q').properties(height=220),
                        width='stretch',
                    )
                else:
                    c6.info('Heart-rate trend unavailable for current filters.')

                c7, c8 = st.columns(2)
                if not distance_df.empty:
                    c7.altair_chart(
                        alt.Chart(distance_df.tail(300)).mark_line(point=False).encode(x='start_time:T', y='total_distance_miles:Q', color='workout_type:N').properties(height=220),
                        width='stretch',
                    )
                else:
                    c7.info('Distance trend unavailable for walking/cycling/swimming under current filters.')

                if not pkl_by_month.empty:
                    c8.altair_chart(
                        alt.Chart(pkl_by_month).mark_bar().encode(x='month:N', y='sessions:Q').properties(height=220),
                        width='stretch',
                    )
                else:
                    c8.info('Pickleball sessions by month unavailable for current filters.')

    st.markdown('### Pickleball Intelligence')
    pickleball_df = all_filtered_df[all_filtered_df['workout_type'] == 'Pickleball'].copy() if not all_filtered_df.empty else pd.DataFrame()
    this_month = pd.Timestamp.now(tz='UTC').to_period('M')
    if not pickleball_df.empty:
        pickleball_df['month_period'] = pickleball_df['start_time'].dt.to_period('M')
        p_month = pickleball_df[pickleball_df['month_period'] == this_month]
        pk1, pk2, pk3, pk4 = st.columns(4)
        pk1.metric('Sessions this month', _safe_int(len(p_month)))
        pk2.metric('Total hours this month', _fmt_num((p_month['duration_minutes'].sum() if not p_month.empty else 0) / 60.0, 1, ' hr'))
        pk3.metric('Average session duration', _fmt_num(pickleball_df['duration_minutes'].mean(), 1, ' min'))
        pk4.metric('Longest session', _fmt_num(pickleball_df['duration_minutes'].max(), 0, ' min'))

        pk5, pk6, pk7 = st.columns(3)
        pk5.metric('Calories this month', _fmt_num(p_month['total_energy_kcal'].sum() if not p_month.empty else 0, 0, ' kcal'))
        hr_vals = pickleball_df[pickleball_df['average_heart_rate'] > 0]['average_heart_rate']
        pk6.metric('Average heart rate', _fmt_num(hr_vals.mean() if not hr_vals.empty else 0, 0, ' bpm'))
        p_week = pickleball_df.assign(week=pickleball_df['start_time'].dt.to_period('W').astype(str)).groupby('week', as_index=False).size().rename(columns={'size': 'sessions'})
        pk7.metric('Weeks with sessions', _safe_int(len(p_week)))

        st.caption('Recent pickleball timeline')
        for _, row in pickleball_df.sort_values('start_time', ascending=False).head(10).iterrows():
            st.caption(f"{_fmt_dt(row.get('start_time'))} • {_fmt_num(row.get('duration_minutes'), 0, ' min')} • {_fmt_num(row.get('total_energy_kcal'), 0, ' kcal')}")
    else:
        st.info('No pickleball sessions for current filters.')

    st.markdown('### Walking, Cycling, and Swimming')
    for activity in ['Walking', 'Cycling', 'Swimming']:
        subset = all_filtered_df[all_filtered_df['workout_type'] == activity].copy() if not all_filtered_df.empty else pd.DataFrame()
        with st.container(border=True):
            st.subheader(activity)
            if subset.empty:
                st.caption('No sessions for current filters.')
                continue
            sessions = len(subset)
            minutes = float(subset['duration_minutes'].sum())
            distance = float(subset['total_distance_miles'].sum())
            calories = float(subset['total_energy_kcal'].sum())
            c1, c2, c3, c4 = st.columns(4)
            c1.metric('Sessions', _safe_int(sessions))
            c2.metric('Time', _fmt_num(minutes, 0, ' min'))
            c3.metric('Distance', _fmt_num(distance, 2, ' mi'))
            c4.metric('Calories', _fmt_num(calories, 0, ' kcal'))

            valid = subset[(subset['duration_minutes'] > 0) & (subset['total_distance_miles'] > 0)]
            if not valid.empty:
                if activity == 'Walking':
                    pace = (valid['duration_minutes'] / valid['total_distance_miles']).mean()
                    st.caption(f'Average pace: {_fmt_num(pace, 2, " min/mi")}.')
                if activity == 'Cycling':
                    speed = (valid['total_distance_miles'] / (valid['duration_minutes'] / 60.0)).mean()
                    st.caption(f'Average speed: {_fmt_num(speed, 2, " mph")}.')

    st.markdown('### Data Quality')
    total_count, count_err = get_apple_workouts_total_count()
    daily_df, daily_err = get_apple_activity_daily()
    dq_df = unfiltered_df if not unfiltered_df.empty else all_filtered_df

    if dq_df.empty:
        st.info('Apple workouts are unavailable for quality checks right now.')
    else:
        earliest = dq_df['start_time'].min()
        latest = dq_df['start_time'].max()
        types_present = sorted(set(dq_df['workout_type'].astype(str).tolist()))
        missing_cal = int((dq_df['total_energy_kcal'] <= 0).sum())
        missing_dist = int((dq_df['total_distance_miles'] <= 0).sum())
        missing_hr = int((dq_df['average_heart_rate'] <= 0).sum())
        source_names = sorted({str(v).strip() for v in dq_df.get('source_name', pd.Series(dtype=str)).astype(str).tolist() if str(v).strip()})

        q1, q2, q3, q4 = st.columns(4)
        q1.metric('Total Apple workouts', _fmt_num(total_count if total_count > 0 else len(dq_df)))
        q2.metric('Earliest workout date', earliest.date().isoformat() if not pd.isna(earliest) else 'N/A')
        q3.metric('Latest workout date', latest.date().isoformat() if not pd.isna(latest) else 'N/A')
        q4.metric('Workout types present', _safe_int(len(types_present)))

        q5, q6, q7 = st.columns(3)
        q5.metric('Rows missing calories', missing_cal)
        q6.metric('Rows missing distance', missing_dist)
        q7.metric('Rows missing heart rate', missing_hr)

        if source_names:
            st.caption(f'Imported source names: {", ".join(source_names[:12])}')

        if not daily_df.empty and 'imported_at' in daily_df.columns:
            imported = pd.to_datetime(daily_df['imported_at'], errors='coerce', utc=True).dropna()
            if not imported.empty:
                st.caption(f'Last import date: {str(imported.max())}')

    if count_err:
        st.warning('Count query warning: total count could not be verified from Supabase.')
        st.caption(count_err)
    if types_err:
        st.caption(f'Workout-type inventory warning: {types_err}')
    if daily_err:
        st.caption(f'Apple activity daily warning: {daily_err}')
    if unfiltered_err:
        st.caption(f'Unfiltered workout snapshot warning: {unfiltered_err}')

    st.caption('Apple Watch Session Summary and Brian Fit Exercise Details are intentionally separated to avoid claiming exercise-level data from Apple Health.')


if __name__ == '__main__':
    render_apple_activity_page()
