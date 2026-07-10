
from pathlib import Path
from datetime import date, datetime
import base64
import pandas as pd
import streamlit as st
import textwrap

from components.ai_card import ai_card
from components.executive_header import executive_header
from components.glass_panel import glass_panel
from components.hero_banner import hero_banner
from components.mission_card import mission_card
from components.stat_card import stat_card
from components.workout_command_center import workout_command_center
from components.muscle_heatmap import render_muscle_heatmap
from components.exercise_photo import exercise_photo
from components.body_composition_summary import body_composition_summary
from engines.exercise_intelligence import ExerciseIntelligence
from engines.body_intelligence import BodyIntelligence
from engines.ai_coach_engine import build_daily_brief
from engines.muscle_readiness_engine import build_muscle_readiness_snapshot, normalize_muscle_name
from engines.recovery_engine import RECOVERY_COLUMNS, get_latest_recovery
from engines.smart_scale_engine import BODY_COLUMNS, dashboard_body_metrics
from services.supabase_service import (
    get_workouts,
    health_check,
)
from services.workout_save_service import (
    build_workout_session_id,
    get_last_save_result,
    save_completed_set,
    save_workout_session as unified_save_workout_session,
)
from engines.performance_intelligence import (
    build_pr_summary,
    compute_workout_grade,
    performance_scores,
    recovery_recommendation,
    workout_streak_days,
)
from pages.body_stats import render_body_stats_page
from pages.recovery_center import render_recovery_center
from pages.smart_scale_import import render_smart_scale_import_page

APP_DIR = Path(__file__).parent
DATA = APP_DIR / "data"
ASSETS = APP_DIR / "assets" / "exercises"
DATA.mkdir(exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
WORKOUTS = DATA / "workouts.csv"
LOG = DATA / "workout_log.csv"
MAP = DATA / "exercise_image_map.csv"
NUTRITION = DATA / "nutrition_log.csv"
BODY = DATA / "body_stats.csv"
SUPPLEMENTS = DATA / "supplement_log.csv"
SUPPLEMENT_PLAN = DATA / "supplement_plan.csv"
RECOVERY = DATA / "recovery_log.csv"

st.set_page_config(page_title="Brian Fitness Tracker X", page_icon="🏋️", layout="wide", initial_sidebar_state="expanded")

def ensure_log():
    if not LOG.exists():
        pd.DataFrame(columns=['date','day','exercise','set_number','weight_lbs','reps','rpe','pain','body_feedback_score','notes','body_feedback_notes','volume']).to_csv(LOG,index=False)
ensure_log()

def ensure_csv(path, columns):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)
    else:
        # Non-destructive schema migration: add missing columns, keep extras.
        df = pd.read_csv(path)
        changed = False
        for col in columns:
            if col not in df.columns:
                df[col] = ''
                changed = True

        # Keep required columns first and preserve any legacy/extra columns.
        extras = [c for c in df.columns if c not in columns]
        target_cols = columns + extras
        if list(df.columns) != target_cols:
            df = df[target_cols]
            changed = True

        # Backfill import source for older body records.
        if path == BODY and 'import_source' in df.columns:
            src = df['import_source'].astype(str)
            missing = src.str.strip().eq('') | src.str.lower().eq('nan')
            if missing.any():
                df.loc[missing, 'import_source'] = 'Manual'
                changed = True

        if changed:
            df.to_csv(path, index=False)

def ensure_health_logs():
    ensure_csv(WORKOUTS, ['day','muscle_group','exercise','target_sets','target_reps','base_weight','image_file'])
    ensure_csv(MAP, ['exercise', 'image_file'])
    ensure_csv(NUTRITION, ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes'])
    ensure_csv(BODY, BODY_COLUMNS)
    ensure_csv(SUPPLEMENTS, ['date','creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes','notes'])
    ensure_csv(SUPPLEMENT_PLAN, ['supplement','category','default_time','target_days_per_week','notes'])
    ensure_csv(RECOVERY, RECOVERY_COLUMNS)
ensure_health_logs()

def read_csv_safe(path, columns):
    ensure_csv(path, columns)
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns)

def append_csv(path, row, columns):
    df = read_csv_safe(path, columns)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(path, index=False)

def repair_workout_database(df):
    """Keep the weekly plan clean even if an older workouts.csv is uploaded."""
    required = ['day','muscle_group','exercise','target_sets','target_reps','base_weight','image_file']
    for c in required:
        if c not in df.columns:
            df[c] = ''

    # Normalize text fields
    df['day'] = df['day'].astype(str).str.strip()
    df['muscle_group'] = df['muscle_group'].astype(str).str.strip()
    df['exercise'] = df['exercise'].astype(str).str.strip()

    changed = False

    # Remove calf work from Wednesday / Shoulder Day
    wrong = (df['day'].str.lower() == 'wednesday') & (df['exercise'].str.lower().str.contains('calf', na=False))
    if wrong.any():
        df = df.loc[~wrong].copy()
        changed = True

    # Add Plank to Wednesday if missing
    wed = df[df['day'].str.lower() == 'wednesday']
    has_plank = wed['exercise'].str.lower().eq('plank').any()
    if not has_plank:
        df = pd.concat([df, pd.DataFrame([{
            'day':'Wednesday',
            'muscle_group':'Shoulders + Abs',
            'exercise':'Plank',
            'target_sets':3,
            'target_reps':'45 sec',
            'base_weight':0,
            'image_file':'plank.png'
        }])], ignore_index=True)
        changed = True

    # Ensure Standing Calf Raise lives on leg/recovery day, not shoulders.
    has_calf = df['exercise'].str.lower().eq('standing calf raise').any()
    if not has_calf:
        df = pd.concat([df, pd.DataFrame([{
            'day':'Thursday',
            'muscle_group':'Leg Rehab Day',
            'exercise':'Standing Calf Raise',
            'target_sets':3,
            'target_reps':15,
            'base_weight':30,
            'image_file':'standing_calf_raise.png'
        }])], ignore_index=True)
        changed = True

    # Deduplicate exact same day/exercise rows
    before = len(df)
    df = df.drop_duplicates(subset=['day','exercise'], keep='first').reset_index(drop=True)
    if len(df) != before:
        changed = True

    if changed:
        try:
            df.to_csv(WORKOUTS, index=False)
        except Exception:
            pass
    return df[required]

def load_workouts():
    ensure_csv(WORKOUTS, ['day','muscle_group','exercise','target_sets','target_reps','base_weight','image_file'])
    df = pd.read_csv(WORKOUTS)
    return repair_workout_database(df)

def load_log_local():
    ensure_log()
    try:
        df = pd.read_csv(LOG)
    except Exception:
        return pd.DataFrame(columns=['date','day','exercise','set_number','weight_lbs','reps','rpe','pain','body_feedback_score','notes','body_feedback_notes','volume'])

    if 'body_feedback_score' not in df.columns:
        if 'pain_score' in df.columns:
            df['body_feedback_score'] = df['pain_score']
        elif 'pain' in df.columns:
            df['body_feedback_score'] = df['pain']
        else:
            df['body_feedback_score'] = 0
    if 'body_feedback_notes' not in df.columns:
        if 'pain_notes' in df.columns:
            df['body_feedback_notes'] = df['pain_notes']
        elif 'notes' in df.columns:
            df['body_feedback_notes'] = df['notes']
        else:
            df['body_feedback_notes'] = ''
    if 'pain' not in df.columns:
        df['pain'] = df['body_feedback_score']
    if 'notes' not in df.columns:
        df['notes'] = df['body_feedback_notes']
    return df


def normalize_cloud_workouts(rows):
    base_cols = ['date','day','exercise','set_number','weight_lbs','reps','rpe','pain','body_feedback_score','notes','body_feedback_notes','volume']
    if not rows:
        return pd.DataFrame(columns=base_cols + ['workout_session_id'])

    df = pd.DataFrame(rows)
    if 'workout_date' in df.columns:
        df['date'] = pd.to_datetime(df['workout_date'], errors='coerce').dt.date.astype(str)
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date.astype(str)
    else:
        df['date'] = ''

    for col in ['day','exercise','set_number','weight_lbs','reps','rpe','body_feedback_score','body_feedback_notes','volume']:
        if col not in df.columns:
            df[col] = ''

    if 'workout_session_id' not in df.columns:
        df['workout_session_id'] = ''

    df['pain'] = df['body_feedback_score']
    df['notes'] = df['body_feedback_notes']

    for col in ['set_number','weight_lbs','reps','rpe','body_feedback_score','volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df[base_cols + ['workout_session_id']]


def load_log(return_meta=False):
    cloud_rows, cloud_error = get_workouts()
    if cloud_error:
        df = load_log_local()
        if return_meta:
            return df, 'csv_fallback', cloud_error
        return df

    if not cloud_rows:
        df = normalize_cloud_workouts([])
        if return_meta:
            return df, 'cloud', None
        return df

    df = normalize_cloud_workouts(cloud_rows)
    if return_meta:
        return df, 'cloud', None
    return df


def get_supabase_credentials():
    try:
        supabase_url = str(st.secrets.get('SUPABASE_URL', '')).strip()
        supabase_key = str(st.secrets.get('SUPABASE_KEY', '')).strip()
    except Exception:
        supabase_url, supabase_key = '', ''
    return supabase_url, supabase_key


def update_cloud_sync_state(ok: bool, message: str, inserted: int = 0, error: str = ''):
    st.session_state['cloud_sync_status'] = {
        'ok': bool(ok),
        'message': str(message),
        'inserted': int(inserted),
        'error': str(error or ''),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def update_last_save_debug(attempted_row: dict, ok: bool, error: str = ''):
    st.session_state['last_save_debug'] = {
        'attempted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'success' if bool(ok) else 'error',
        'error': str(error or ''),
        'last_saved_exercise': str((attempted_row or {}).get('exercise', '')),
        'workout': dict(attempted_row or {}),
    }


def get_recent_exercise_stats(log_df: pd.DataFrame, exercise_name: str) -> tuple[float, int, float]:
    if log_df is None or log_df.empty or 'exercise' not in log_df.columns:
        return 0.0, 0, 0.0

    rows = log_df[log_df['exercise'].astype(str).str.strip().str.lower() == str(exercise_name).strip().lower()].copy()
    if rows.empty:
        return 0.0, 0, 0.0

    rows['weight_lbs'] = pd.to_numeric(rows.get('weight_lbs', 0), errors='coerce').fillna(0)
    rows['reps'] = pd.to_numeric(rows.get('reps', 0), errors='coerce').fillna(0)
    rows['rpe'] = pd.to_numeric(rows.get('rpe', 0), errors='coerce').fillna(0)

    last_row = rows.iloc[-1]
    last_weight = float(last_row.get('weight_lbs', 0) or 0)
    last_reps = int(float(last_row.get('reps', 0) or 0))
    best_weight = float(rows['weight_lbs'].max() if not rows.empty else 0)
    return last_weight, last_reps, best_weight


def get_mobile_primary_page() -> str:
    mapping = {
        'Dashboard': 'Dashboard',
        'Workout': "Today's Workout",
        'Gym Mode': 'Gym Mode',
        'History': 'History',
        'Progress': 'Progress Analytics',
        'More': 'More',
    }

    if 'mobile_more_active' not in st.session_state:
        st.session_state['mobile_more_active'] = False

    current = str(st.session_state.get('main_nav', 'Dashboard'))
    reverse = {
        "Today's Workout": 'Workout',
        'Progress Analytics': 'Progress',
    }
    current_mobile = reverse.get(current, current if current in mapping else 'Dashboard')

    st.markdown('<div class="mobile-nav-shell">', unsafe_allow_html=True)
    selected = st.radio(
        'Mobile Primary Navigation',
        ['Dashboard', 'Workout', 'Gym Mode', 'History', 'Progress', 'More'],
        horizontal=True,
        key='mobile_primary_nav',
        index=['Dashboard', 'Workout', 'Gym Mode', 'History', 'Progress', 'More'].index(current_mobile) if current_mobile in ['Dashboard', 'Workout', 'Gym Mode', 'History', 'Progress', 'More'] else 0,
        label_visibility='collapsed',
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if selected == 'More':
        st.session_state['mobile_more_active'] = True
        more_options = [
            'AI Coach',
            'Workout Builder',
            'Weekly Plan',
            'Recovery Center',
            'Nutrition',
            'Supplements',
            'Body Stats',
            'Smart Scale',
            'Exercise Library',
            'Data Manager',
            'System Check',
        ]
        more_target = st.selectbox('More', more_options, key='mobile_more_select')
        st.session_state['main_nav'] = more_target
        return more_target

    st.session_state['mobile_more_active'] = False
    target = mapping[selected]
    st.session_state['main_nav'] = target
    return target


def get_rest_timer_state(flow_key: str) -> dict:
    key = f'{flow_key}_rest_timer'
    if key not in st.session_state:
        st.session_state[key] = {
            'duration': 90,
            'remaining': 90,
            'running': False,
            'started_at': None,
            'last_completed_set_at': '',
        }
    return st.session_state[key]


def render_rest_timer(flow_key: str):
    state = get_rest_timer_state(flow_key)
    st.markdown('<div class="rest-timer-card">', unsafe_allow_html=True)
    st.markdown('### Rest Timer')
    quick = st.radio(
        'Quick timer',
        ['60 sec', '90 sec', '120 sec', '180 sec'],
        horizontal=True,
        key=f'{flow_key}_rest_quick',
        index=[60, 90, 120, 180].index(int(state.get('duration', 90))) if int(state.get('duration', 90)) in [60, 90, 120, 180] else 1,
    )
    selected_seconds = int(str(quick).split()[0])
    if selected_seconds != int(state.get('duration', 90)) and not bool(state.get('running', False)):
        state['duration'] = selected_seconds
        state['remaining'] = selected_seconds

    if bool(state.get('running', False)) and state.get('started_at'):
        elapsed = (datetime.now() - state['started_at']).total_seconds()
        remaining = max(0, int(state.get('duration', 90) - elapsed))
        state['remaining'] = remaining
        if remaining <= 0:
            state['running'] = False
            state['started_at'] = None

    st.markdown(f'<div class="rest-countdown">{int(state.get("remaining", 0))}s</div>', unsafe_allow_html=True)
    if int(state.get('remaining', 0)) == 0:
        st.success('Rest complete')

    b1, b2, b3, b4 = st.columns(4)
    if b1.button('Start', key=f'{flow_key}_rest_start', use_container_width=True):
        state['duration'] = int(selected_seconds)
        state['started_at'] = datetime.now() - pd.to_timedelta(int(state.get('duration', selected_seconds)) - int(state.get('remaining', selected_seconds)), unit='s')
        state['running'] = True
    if b2.button('Pause', key=f'{flow_key}_rest_pause', use_container_width=True):
        state['running'] = False
        state['started_at'] = None
    if b3.button('Reset', key=f'{flow_key}_rest_reset', use_container_width=True):
        state['duration'] = int(selected_seconds)
        state['remaining'] = int(selected_seconds)
        state['running'] = False
        state['started_at'] = None
    if b4.button('Skip', key=f'{flow_key}_rest_skip', use_container_width=True):
        state['remaining'] = 0
        state['running'] = False
        state['started_at'] = None
    st.markdown('</div>', unsafe_allow_html=True)


def build_session_metrics(session_sets: list[dict], started_at: Optional[datetime] = None) -> dict:
    rows = list(session_sets or [])
    if not rows:
        return {
            'duration_min': 0,
            'exercise_count': 0,
            'set_count': 0,
            'total_volume': 0,
            'avg_rpe': 0.0,
            'highest_weight_exercise': 'N/A',
            'estimated_calories': 0,
        }

    df = pd.DataFrame(rows)
    df['weight_lbs'] = pd.to_numeric(df.get('weight_lbs', 0), errors='coerce').fillna(0)
    df['reps'] = pd.to_numeric(df.get('reps', 0), errors='coerce').fillna(0)
    df['rpe'] = pd.to_numeric(df.get('rpe', 0), errors='coerce').fillna(0)
    df['volume'] = pd.to_numeric(df.get('volume', 0), errors='coerce').fillna(0)

    top_idx = df['weight_lbs'].idxmax() if not df.empty else None
    top_ex = str(df.iloc[int(top_idx)].get('exercise', 'N/A')) if top_idx is not None and top_idx == top_idx else 'N/A'
    duration_min = 0
    if started_at is not None:
        duration_min = max(1, int((datetime.now() - started_at).total_seconds() // 60))

    total_volume = int(df['volume'].sum())
    return {
        'duration_min': int(duration_min),
        'exercise_count': int(df['exercise'].astype(str).str.strip().str.lower().nunique()),
        'set_count': int(len(df)),
        'total_volume': total_volume,
        'avg_rpe': round(float(df['rpe'].mean() if not df.empty else 0.0), 1),
        'highest_weight_exercise': top_ex,
        'estimated_calories': int(max(30, total_volume / 65.0)),
    }


def detect_session_prs(log_df: pd.DataFrame, session_sets: list[dict]) -> list[dict]:
    if log_df is None or log_df.empty or not session_sets:
        return []

    base = log_df.copy()
    for c in ['weight_lbs', 'reps', 'volume']:
        if c in base.columns:
            base[c] = pd.to_numeric(base[c], errors='coerce').fillna(0)
        else:
            base[c] = 0
    base['exercise'] = base.get('exercise', pd.Series(dtype=str)).astype(str)
    base['est_1rm'] = base['weight_lbs'] * (1 + (base['reps'] / 30.0))

    prs = []
    for row in session_sets:
        ex = str(row.get('exercise', '')).strip()
        if not ex:
            continue
        ex_hist = base[base['exercise'].str.strip().str.lower() == ex.lower()]
        if ex_hist.empty:
            continue

        w = float(row.get('weight_lbs', 0) or 0)
        r = float(row.get('reps', 0) or 0)
        v = float(row.get('volume', w * r) or 0)
        e1 = float(w * (1 + (r / 30.0)))

        prev_weight = float(ex_hist['weight_lbs'].max())
        prev_reps = float(ex_hist['reps'].max())
        prev_vol = float(ex_hist['volume'].max())
        prev_1rm = float(ex_hist['est_1rm'].max())

        if w > prev_weight:
            prs.append({'exercise': ex, 'record': 'Heaviest weight', 'previous': round(prev_weight, 1), 'new': round(w, 1), 'improvement': round(w - prev_weight, 1)})
        if r > prev_reps:
            prs.append({'exercise': ex, 'record': 'Most reps', 'previous': int(prev_reps), 'new': int(r), 'improvement': int(r - prev_reps)})
        if v > prev_vol:
            prs.append({'exercise': ex, 'record': 'Highest set volume', 'previous': round(prev_vol, 1), 'new': round(v, 1), 'improvement': round(v - prev_vol, 1)})
        if e1 > prev_1rm:
            prs.append({'exercise': ex, 'record': 'Highest estimated 1RM', 'previous': round(prev_1rm, 1), 'new': round(e1, 1), 'improvement': round(e1 - prev_1rm, 1)})
    return prs


def render_session_summary(save_result: dict, session_sets: list[dict], flow_key: str):
    started_at = st.session_state.get(f'{flow_key}_started_at')
    metrics = build_session_metrics(session_sets, started_at=started_at)
    historical = load_log()
    prs = detect_session_prs(historical, session_sets)

    st.markdown('<div class="session-summary">', unsafe_allow_html=True)
    st.success('Workout saved permanently')
    st.caption('Cloud: Supabase')
    if bool(save_result.get('session_id_supported', False)):
        st.caption(f"Session ID: {str(save_result.get('session_id', ''))}")
    else:
        st.caption('Session ID tracking: unavailable until Supabase schema migration is applied.')
    st.caption(f"Supabase verification: {int(save_result.get('verified_rows', 0))} row(s) verified")

    a1, a2, a3, a4 = st.columns(4)
    a1.metric('Duration', f"{metrics['duration_min']} min")
    a2.metric('Exercises', str(metrics['exercise_count']))
    a3.metric('Sets', str(metrics['set_count']))
    a4.metric('Total Volume', f"{metrics['total_volume']:,} lbs")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric('Average RPE', f"{metrics['avg_rpe']:.1f}")
    b2.metric('Top Exercise', str(metrics['highest_weight_exercise']))
    b3.metric('Estimated Calories', str(metrics['estimated_calories']))
    b4.metric('PRs', str(len(prs)))

    if prs:
        st.markdown('### New Personal Record')
        for p in prs[:6]:
            st.markdown(f"- {p['exercise']}: {p['record']} ({p['previous']} -> {p['new']}, +{p['improvement']})")

    st.caption('Comparison with previous workout: based on recent cloud history for the same exercise patterns.')
    st.caption('Suggested next workout: progress weight by 2.5-5 lbs where reps were completed with manageable RPE.')

    c1, c2, c3 = st.columns(3)
    if c1.button('View History', key=f'{flow_key}_summary_history', use_container_width=True):
        st.session_state['main_nav'] = 'History'
        st.rerun()
    if c2.button('View Progress', key=f'{flow_key}_summary_progress', use_container_width=True):
        st.session_state['main_nav'] = 'Progress Analytics'
        st.rerun()
    if c3.button('Return to Dashboard', key=f'{flow_key}_summary_dashboard', use_container_width=True):
        st.session_state['main_nav'] = 'Dashboard'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def group_sessions(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df is None or log_df.empty:
        return pd.DataFrame(columns=['session_key', 'date', 'focus', 'sets', 'exercises', 'total_volume', 'avg_rpe', 'pr_count'])

    df = log_df.copy()
    if 'workout_session_id' not in df.columns:
        df['workout_session_id'] = ''
    if 'date' not in df.columns:
        df['date'] = ''
    if 'day' not in df.columns:
        df['day'] = ''
    if 'exercise' not in df.columns:
        df['exercise'] = ''
    if 'volume' not in df.columns:
        df['volume'] = 0
    if 'rpe' not in df.columns:
        df['rpe'] = 0

    df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    df['rpe'] = pd.to_numeric(df['rpe'], errors='coerce').fillna(0)
    df['session_key'] = df['workout_session_id'].astype(str).str.strip()
    empty_sid = df['session_key'].eq('')
    df.loc[empty_sid, 'session_key'] = (
        df.loc[empty_sid, 'date'].astype(str).str.strip() + '|' + df.loc[empty_sid, 'day'].astype(str).str.strip()
    )

    grouped = df.groupby('session_key', as_index=False).agg(
        date=('date', 'max'),
        focus=('day', 'max'),
        sets=('exercise', 'count'),
        exercises=('exercise', lambda s: int(s.astype(str).str.strip().str.lower().nunique())),
        total_volume=('volume', 'sum'),
        avg_rpe=('rpe', 'mean'),
    )
    grouped['pr_count'] = 0
    grouped = grouped.sort_values('date', ascending=False)
    return grouped


def make_workout_session_id(flow_key: str) -> str:
    state_key = f'{flow_key}_session_id'
    existing = str(st.session_state.get(state_key, '')).strip()
    if existing:
        return existing
    new_id = build_workout_session_id()
    st.session_state[state_key] = new_id
    return new_id


def get_pending_sets(flow_key: str):
    state_key = f'{flow_key}_pending_sets'
    if state_key not in st.session_state:
        st.session_state[state_key] = []
    return st.session_state[state_key]


def clear_pending_sets(flow_key: str):
    st.session_state[f'{flow_key}_pending_sets'] = []
    st.session_state[f'{flow_key}_session_id'] = ''


def build_set_row(day: str, exercise: str, result: dict, session_id: str):
    weight = float(result.get('weight', 0.0) or 0.0)
    reps = int(float(result.get('reps', 0) or 0))
    return {
        'date': str(date.today()),
        'workout_date': str(date.today()),
        'day': str(day),
        'exercise': str(exercise),
        'set_number': int(float(result.get('set_number', 1) or 1)),
        'weight_lbs': weight,
        'reps': reps,
        'rpe': float(result.get('rpe', 0.0) or 0.0),
        'pain': int(float(result.get('body_feedback_score', result.get('pain', 0)) or 0)),
        'body_feedback_score': int(float(result.get('body_feedback_score', result.get('pain', 0)) or 0)),
        'notes': str(result.get('body_feedback_notes', result.get('notes', ''))),
        'body_feedback_notes': str(result.get('body_feedback_notes', result.get('notes', ''))),
        'volume': float(weight * reps),
        'workout_session_id': str(session_id),
    }


def save_rows_to_cloud_then_backup(rows, save_source_label='phone_workout'):
    session_id = str(rows[0].get('workout_session_id', '') if rows else '')
    save_result = unified_save_workout_session(
        session_data={
            'session_id': session_id,
            'save_source_label': save_source_label,
        },
        completed_sets=rows,
    )
    supabase_ok = bool(save_result.get('ok'))
    exact_error = str(save_result.get('cloud_error', '') or '')

    csv_ok = bool(save_result.get('csv_backup_ok', True))
    csv_error = str(save_result.get('csv_backup_error', '') or '')

    sets_attempted = int(save_result.get('sets_attempted', len(rows)))
    sets_inserted = int(save_result.get('sets_inserted', 0))
    duplicates_skipped = int(save_result.get('duplicates_skipped', 0))
    verified_rows = int(save_result.get('verified_rows', 0))
    session_id = str(save_result.get('session_id', session_id))
    session_id_supported = bool(save_result.get('session_id_supported', False))
    session_id_used = bool(session_id_supported and session_id)
    unique_exercises = len(set([str(r.get('exercise', '')).strip().lower() for r in rows if str(r.get('exercise', '')).strip()]))
    verified_cloud_count = int(save_result.get('after_count', 0))
    history_source = str(save_result.get('history_source', 'Supabase Cloud' if supabase_ok else 'Local CSV Backup'))

    if supabase_ok:
        sync_message = 'Workout saved permanently'
    else:
        sync_message = 'Cloud save failed'
    update_cloud_sync_state(
        ok=supabase_ok,
        message=sync_message,
        inserted=sets_inserted,
        error=exact_error,
    )

    previous_debug = st.session_state.get('last_save_debug', {})
    st.session_state['last_save_debug'] = {
        'attempted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'success' if supabase_ok else 'error',
        'error': str(exact_error or csv_error or ''),
        'last_saved_exercise': str(rows[-1].get('exercise', '')) if rows else '',
        'last_save_source': 'supabase' if supabase_ok else 'backup_only',
        'last_workout_session_id': session_id,
        'session_id_supported': session_id_supported,
        'session_id_used': session_id_used,
        'sets_attempted': sets_attempted,
        'sets_inserted': sets_inserted,
        'duplicates_skipped': duplicates_skipped,
        'verified_rows': verified_rows,
        'history_source': history_source,
        'last_successful_sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if supabase_ok else str(previous_debug.get('last_successful_sync_time', '')),
        'save_source_label': save_source_label,
        'workout': dict(rows[-1]) if rows else {},
    }

    return {
        'supabase_ok': supabase_ok,
        'supabase_error': exact_error,
        'csv_ok': csv_ok,
        'csv_error': csv_error,
        'sets_attempted': sets_attempted,
        'sets_inserted': sets_inserted,
        'duplicates_skipped': duplicates_skipped,
        'verified_rows': verified_rows,
        'exercises_saved': unique_exercises,
        'session_id': session_id,
        'session_id_supported': session_id_supported,
        'session_id_used': session_id_used,
        'already_saved': bool(save_result.get('already_saved', False)),
        'status': str(save_result.get('status', '')),
        'history_source': history_source,
        'verified_cloud_row_count': verified_cloud_count,
    }


def render_cloud_save_success(save_result: dict):
    if bool(save_result.get('already_saved', False)):
        st.info('Already saved')
    else:
        st.success('Workout saved permanently')
    st.caption('Cloud: Supabase')
    if bool(save_result.get('session_id_supported', False)) and bool(save_result.get('session_id_used', False)):
        st.caption(f"Session ID: {str(save_result.get('session_id', ''))}")
    else:
        st.caption('Session ID tracking: unavailable until Supabase schema migration is applied.')
    st.caption(f"Sets saved: {int(save_result.get('sets_inserted', 0))}")
    st.caption(f"Exercises saved: {int(save_result.get('exercises_saved', 0))}")
    st.caption(f"Duplicates skipped: {int(save_result.get('duplicates_skipped', 0))}")
    st.caption(f"Verified rows: {int(save_result.get('verified_rows', 0))}")
    st.caption(f"Verified cloud row count: {int(save_result.get('verified_cloud_row_count', 0))}")


def render_cloud_save_failure(save_result: dict):
    st.error('Cloud save failed')
    st.error(f"Exact error: {str(save_result.get('supabase_error') or 'Unknown Supabase error')}")
    if save_result.get('csv_ok'):
        st.warning('Backup-only save: row written to local CSV.')
    else:
        st.error(f"CSV backup failed: {str(save_result.get('csv_error') or 'Unknown CSV error')}")


def resolve_body_feedback_score(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    if 'body_feedback_score' in df.columns:
        return pd.to_numeric(df['body_feedback_score'], errors='coerce').fillna(0)
    if 'pain_score' in df.columns:
        return pd.to_numeric(df['pain_score'], errors='coerce').fillna(0)
    if 'pain' in df.columns:
        return pd.to_numeric(df['pain'], errors='coerce').fillna(0)
    return pd.Series([0] * len(df), index=df.index, dtype=float)


def resolve_body_feedback_notes(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=str)
    if 'body_feedback_notes' in df.columns:
        return df['body_feedback_notes'].astype(str)
    if 'pain_notes' in df.columns:
        return df['pain_notes'].astype(str)
    if 'notes' in df.columns:
        return df['notes'].astype(str)
    return pd.Series([''] * len(df), index=df.index, dtype=str)

def save_log(rows):
    return save_rows_to_cloud_then_backup(rows, save_source_label='legacy_single')

def image_path(row):
    f = str(row.get('image_file','')).strip()
    p = ASSETS / f
    if f and p.exists(): return p
    # try map file
    if MAP.exists():
        try:
            m = pd.read_csv(MAP)
            hit = m[m['exercise'].astype(str).str.lower()==str(row.get('exercise','')).lower()]
            if not hit.empty:
                p = ASSETS / str(hit.iloc[0]['image_file'])
                if p.exists(): return p
        except Exception: pass
    fallback = ASSETS / 'image_coming_soon.png'
    return fallback if fallback.exists() else None

def img_tag(path):
    if path and Path(path).exists():
        mime = 'image/png' if str(path).lower().endswith('png') else 'image/jpeg'
        data = base64.b64encode(Path(path).read_bytes()).decode()
        return f'<img src="data:{mime};base64,{data}" class="exercise-photo" />'
    return '<div class="no-image">Image Coming Soon</div>'

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
html, body, [class*="css"] {font-family: Inter, sans-serif;}
.stApp {background: #07111f; color:#f8fafc;}
[data-testid="stHeader"] {background: rgba(7,17,31,.85);}
section[data-testid="stSidebar"] {background: linear-gradient(180deg,#06111f,#08213b); border-right:1px solid #1d3655;}
section[data-testid="stSidebar"] * {color:#f8fafc !important;}
.hero {border:1px solid #254264; background:linear-gradient(135deg,#0e2138,#0a1728); border-radius:24px; padding:28px; margin:12px 0 22px 0;}
.kicker {letter-spacing:.25em; font-size:.82rem; color:#22c55e; font-weight:900; text-transform:uppercase;}
.title {font-size:2.1rem; font-weight:900; line-height:1.1; margin-top:8px;}
.sub {color:#9cc7ff; margin-top:10px;}
.metric-card {background:#0f1f34; border:1px solid #254264; border-radius:18px; padding:16px; min-height:118px; display:flex; flex-direction:column; justify-content:space-between;}
.metric-label {color:#9cc7ff; font-size:.82rem; line-height:1.2;}
.metric-value {font-size:1.35rem; font-weight:900; color:white; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; word-break:keep-all; overflow-wrap:normal;}
.metric-value-wrap {font-size:1.1rem; font-weight:900; color:white; line-height:1.2; white-space:normal;}
.metric-subvalue {font-size:1rem; font-weight:850; color:#dbeafe; line-height:1.2; margin-top:4px; white-space:nowrap;}
.exercise-card {background:linear-gradient(135deg,#0f1f34,#0a1728); border:1px solid #254264; border-radius:22px; padding:18px; margin:18px 0; box-shadow: 0 8px 28px rgba(0,0,0,.2);}
.exercise-head {display:flex; align-items:center; gap:12px; margin-bottom:12px;}
.num {background:#1d7cff; color:#fff; border-radius:999px; width:34px; height:34px; display:flex; align-items:center; justify-content:center; font-weight:900;}
.ex-title {font-size:1.35rem; font-weight:900;}
.badge {display:inline-block; padding:6px 10px; margin-right:8px; border-radius:999px; border:1px solid #1d7cff; color:#86c5ff; background:#0b2b4f; font-weight:800; font-size:.8rem;}
.badge.green {border-color:#22c55e; color:#7cff9d; background:#07351f;}
.exercise-photo-wrap {background:#081322; border:1px solid #1d3655; border-radius:16px; padding:8px; min-height:245px; display:flex; align-items:center; justify-content:center; overflow:hidden;}
.exercise-photo {width:100%; height:245px; object-fit:contain; border-radius:12px; background:#06111f;}
.no-image {width:100%; height:245px; display:flex; align-items:center; justify-content:center; border-radius:12px; background:#0b1e33; color:#9cc7ff; font-weight:800;}
.set-header, .set-row {display:grid; grid-template-columns: 55px 1fr 1fr 1fr 1.3fr 90px; gap:10px; align-items:center;}
.set-header {color:#9cc7ff; font-weight:900; font-size:.76rem; border-bottom:1px solid #1d3655; padding:8px 0;}
.set-row {padding:8px 0; border-bottom:1px solid rgba(37,66,100,.45);}
.volume {color:#2cff88; font-weight:900;}
.side-card {background:#0f1f34; border:1px solid #254264; border-radius:18px; padding:18px; margin-bottom:16px;}
.side-title {font-weight:900; color:white; font-size:1.05rem; margin-bottom:12px;}
.safe {background:#063326; border:1px solid #157a51; color:#b8ffd5; padding:16px; border-radius:16px; margin-top:24px;}
.small {font-size:.86rem; color:#9cc7ff;}
.stButton>button {background:#12375f; color:white; border:1px solid #2b70bb; border-radius:12px; font-weight:800;}
.stDownloadButton>button {background:#12375f; color:white; border:1px solid #2b70bb; border-radius:12px; font-weight:800;}
input, textarea, select {border-radius:10px !important;}
@media (max-width: 900px) {.set-header, .set-row {grid-template-columns: 36px 1fr 1fr;}.hide-mobile{display:none}.exercise-photo{height:210px}.exercise-photo-wrap{min-height:210px}}

/* brighter Streamlit sidebar collapse arrows / menu controls */
[data-testid="collapsedControl"] {
    background: #22c55e !important;
    color: #04111f !important;
    border: 2px solid #60a5fa !important;
    box-shadow: 0 0 18px rgba(34,197,94,.75) !important;
    border-radius: 12px !important;
}
[data-testid="collapsedControl"] svg {stroke:#04111f !important; fill:#04111f !important;}
button[kind="header"] {
    background: #22c55e !important;
    color: #04111f !important;
    border-radius: 10px !important;
    box-shadow: 0 0 12px rgba(34,197,94,.55) !important;
}
button[kind="header"] svg {stroke:#04111f !important; fill:#04111f !important;}
/* make sidebar radio selection more obvious */
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {border-color:#22c55e !important;}

.goalbar {height:12px;background:#132940;border-radius:999px;overflow:hidden;border:1px solid #254264}.goalfill{height:100%;background:linear-gradient(90deg,#22c55e,#60a5fa);border-radius:999px}.macro-card{background:#0f1f34;border:1px solid #254264;border-radius:18px;padding:16px;margin:8px 0}.macro-value{font-size:1.45rem;font-weight:900;color:#fff}.macro-good{color:#22c55e;font-weight:900}.macro-warn{color:#fbbf24;font-weight:900}

/* 2.5.1 repair: brighter supplement cards */
.supp-bright-card{border-radius:18px;padding:16px;margin:10px 0;color:white;border:1px solid rgba(255,255,255,.18);box-shadow:0 10px 24px rgba(0,0,0,.22)}
.supp-performance{background:linear-gradient(135deg,#075985,#2563eb)}
.supp-protein{background:linear-gradient(135deg,#064e3b,#10b981)}
.supp-recovery{background:linear-gradient(135deg,#14532d,#22c55e)}
.supp-general{background:linear-gradient(135deg,#581c87,#a855f7)}
.supp-workout{background:linear-gradient(135deg,#7c2d12,#f97316)}
.supp-hydration{background:linear-gradient(135deg,#164e63,#06b6d4)}
.supp-title{font-size:1.12rem;font-weight:950;margin-bottom:4px}.supp-meta{font-size:.86rem;opacity:.95}.supp-pill{display:inline-block;margin-top:8px;background:rgba(255,255,255,.18);padding:5px 8px;border-radius:999px;font-weight:850;font-size:.78rem}



/* 3.1 Professional UI polish */
.stApp {background: radial-gradient(circle at top left, #10284a 0%, #07111f 34%, #050b14 100%) !important;}
.block-container {padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1480px;}
[data-testid="stToolbar"] {display:none;}
.hero {box-shadow: 0 18px 45px rgba(0,0,0,.28); border:1px solid rgba(96,165,250,.32) !important;}
.metric-card, .side-card, .exercise-card, .macro-card {box-shadow: 0 14px 34px rgba(0,0,0,.22);}
.metric-card {background:linear-gradient(145deg,#10263f,#0c1a2d) !important;}
.metric-card:hover, .side-card:hover, .exercise-card:hover {border-color:#60a5fa !important;}
.stTabs [data-baseweb="tab-list"] {gap:10px; background:#081322; padding:8px; border-radius:18px; border:1px solid #1d3655;}
.stTabs [data-baseweb="tab"] {border-radius:14px; padding:10px 14px; color:#c8ddff; font-weight:900;}
.stTabs [aria-selected="true"] {background:#2563eb !important; color:white !important;}
.stSelectbox div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input, .stTextArea textarea {background:#0b1e33 !important; color:#f8fafc !important; border:1px solid #2b527a !important;}
.stCheckbox label span {color:#f8fafc !important; font-weight:700;}
.stDataFrame {border:1px solid #254264; border-radius:16px; overflow:hidden;}
div[data-testid="stMetric"] {background:#0f1f34; border:1px solid #254264; border-radius:18px; padding:14px;}
section[data-testid="stSidebar"] [role="radiogroup"] label {background:rgba(255,255,255,.035); border:1px solid rgba(96,165,250,.10); border-radius:14px; padding:8px 10px; margin:5px 0;}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:rgba(37,99,235,.20); border-color:#60a5fa;}
section[data-testid="stSidebar"] h2 {font-size:1.45rem !important;}
.professional-chip {display:inline-flex;align-items:center;gap:6px;padding:7px 11px;border-radius:999px;background:#0b2b4f;border:1px solid #60a5fa;color:#c8ddff;font-weight:900;font-size:.78rem;margin-right:6px;}

/* 3.2 Mobile navigation fix */
.mobile-nav-title{display:none;}
div[role="radiogroup"]{gap:8px; flex-wrap:wrap;}
div[role="radiogroup"] label{background:#0f1f34 !important; border:1px solid #254264 !important; border-radius:14px !important; padding:8px 12px !important; margin:4px 2px !important; color:#f8fafc !important; font-weight:900 !important;}
div[role="radiogroup"] label:hover{border-color:#60a5fa !important; background:#12375f !important;}
div[role="radiogroup"] label[data-checked="true"], div[role="radiogroup"] label:has(input:checked){background:linear-gradient(135deg,#2563eb,#22c55e) !important; border-color:#22c55e !important; color:white !important; box-shadow:0 0 18px rgba(34,197,94,.35) !important;}
@media (max-width: 900px){
  section[data-testid="stSidebar"]{display:none !important;}
  .mobile-nav-title{display:block; position:sticky; top:0; z-index:999; background:#07111f; border:1px solid #254264; border-radius:14px; padding:10px 12px; margin-bottom:8px; font-weight:950; color:#22c55e;}
  div[role="radiogroup"]{position:sticky; top:48px; z-index:998; background:#07111f; padding:8px; border:1px solid #254264; border-radius:16px; margin-bottom:14px; box-shadow:0 12px 30px rgba(0,0,0,.3);}
  div[role="radiogroup"] label{font-size:.82rem !important; padding:8px 10px !important;}
  .hero{padding:18px !important;}
  .title{font-size:1.55rem !important;}
}



/* 3.2.2 TOP NAV CONTRAST FIX */
/* Make horizontal top navigation readable on dark background */
div[role="radiogroup"] label,
div[role="radiogroup"] label *,
div[role="radiogroup"] label p,
div[role="radiogroup"] label span {
    color: #f8fafc !important;
    opacity: 1 !important;
    font-weight: 900 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.55) !important;
}

div[role="radiogroup"] label {
    background: linear-gradient(135deg, #10263f, #0b1e33) !important;
    border: 1.5px solid #3b82f6 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,.28) !important;
}

div[role="radiogroup"] label:hover {
    background: linear-gradient(135deg, #1d4ed8, #0f766e) !important;
    border-color: #60a5fa !important;
}

div[role="radiogroup"] label[data-checked="true"],
div[role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(135deg, #2563eb, #22c55e) !important;
    border: 2px solid #86efac !important;
    box-shadow: 0 0 18px rgba(34,197,94,.55) !important;
}

div[role="radiogroup"] label[data-checked="true"] *,
div[role="radiogroup"] label:has(input:checked) * {
    color: #ffffff !important;
    opacity: 1 !important;
}

/* Make the small radio dots visible but not distracting */
div[role="radiogroup"] input[type="radio"] + div,
div[role="radiogroup"] [data-testid="stMarkdownContainer"] {
    color: #f8fafc !important;
    opacity: 1 !important;
}


/* X.4.1 Executive Dashboard - stable Streamlit-safe HTML */
.x-hero {position:relative; overflow:hidden; border:1px solid rgba(59,130,246,.45); background: radial-gradient(circle at 75% 30%, rgba(37,99,235,.35), transparent 32%), linear-gradient(135deg,#08111F 0%,#0B1B35 55%,#0B1220 100%); border-radius:28px; padding:38px 42px; margin:18px 0 26px 0; box-shadow:0 25px 70px rgba(0,0,0,.45);}
.x-kicker {letter-spacing:.30em; color:#22C55E; font-size:.78rem; font-weight:950; text-transform:uppercase;}
.x-title {font-size:3.05rem; font-weight:950; color:#fff; line-height:1.02; margin:14px 0 10px 0;}
.x-subtitle {font-size:1.08rem; color:#BFD7FF; max-width:690px; line-height:1.55;}
.x-recovery {position:absolute; right:42px; top:34px; text-align:right;}
.x-recovery .big {font-size:4rem; line-height:1; color:#22C55E; font-weight:950;}
.x-recovery .label {letter-spacing:.18em; color:#fff; font-weight:900; margin-top:8px;}
.x-recovery .status {color:#7CFF9B; font-weight:900; margin-top:8px;}
.x-mission {display:grid; grid-template-columns: 1.2fr .9fr; gap:22px; align-items:center; border:1px solid rgba(59,130,246,.45); background:linear-gradient(135deg,#0D1B2F,#0B1424); border-radius:26px; padding:30px 34px; margin:0 0 22px 0; box-shadow:0 16px 45px rgba(0,0,0,.38);}
.x-mission-label {color:#60A5FA; font-weight:950; letter-spacing:.20em; text-transform:uppercase; font-size:.78rem;}
.x-mission-title {font-size:2.35rem; font-weight:950; color:white; margin:10px 0 20px;}
.x-pills {display:flex; flex-wrap:wrap; gap:14px;}
.x-pill {background:#10243C; border:1px solid #254264; color:#EAF2FF; border-radius:18px; padding:12px 16px; font-weight:850;}
.x-pill.green {background:rgba(34,197,94,.13); border-color:rgba(34,197,94,.55);}
.x-pill.blue {background:rgba(59,130,246,.14); border-color:rgba(59,130,246,.58);}
.x-pill.amber {background:rgba(245,158,11,.12); border-color:rgba(245,158,11,.55);}
.x-start {background:linear-gradient(135deg,#0EA5E9,#2563EB); border-radius:22px; padding:28px; text-align:center; color:white; font-size:1.35rem; font-weight:950; box-shadow:0 18px 55px rgba(37,99,235,.45); border:1px solid rgba(147,197,253,.65);}
.x-stat {background:linear-gradient(145deg,#0F1F34,#0A1728); border:1px solid rgba(59,130,246,.30); border-radius:22px; padding:22px; min-height:150px; box-shadow:0 16px 40px rgba(0,0,0,.28);}
.x-stat-icon {font-size:2rem; margin-bottom:12px;}
.x-stat-label {color:#B8C2D1; font-size:.82rem; letter-spacing:.10em; text-transform:uppercase; font-weight:900;}
.x-stat-value {font-size:2rem; font-weight:950; color:white; margin-top:6px;}
.x-stat-sub {color:#9CC7FF; font-size:.9rem; margin-top:8px;}
.x-progress {height:9px; background:#142842; border-radius:999px; overflow:hidden; margin-top:15px; border:1px solid #24334A;}
.x-progress-fill {height:100%; border-radius:999px; background:linear-gradient(90deg,#2563EB,#22C55E);}
.x-ai {display:grid; grid-template-columns: 1fr .55fr .55fr; gap:18px; background:linear-gradient(135deg,rgba(139,92,246,.18),rgba(15,31,52,.96)); border:1px solid rgba(139,92,246,.45); border-radius:24px; padding:24px 28px; margin:24px 0; box-shadow:0 16px 45px rgba(0,0,0,.32);}
.x-ai-kicker {color:#A78BFA; font-size:.78rem; letter-spacing:.18em; font-weight:950; text-transform:uppercase;}
.x-ai-title {font-size:1.65rem; font-weight:950; color:#fff; margin-top:8px;}
.x-ai-sub {color:#C8D3E6; margin-top:6px;}
.x-ai-mini {border-left:1px solid rgba(255,255,255,.12); padding-left:18px;}
.x-ai-mini .ok {color:#22C55E; font-weight:950; font-size:1.1rem;}
.x-ai-mini .warn {color:#F59E0B; font-weight:950; font-size:1.1rem;}
.x-week {background:#0F1F34; border:1px solid #254264; border-radius:20px; padding:18px; min-height:150px; box-shadow:0 12px 32px rgba(0,0,0,.22);}
.x-week.today {border-color:#22C55E; box-shadow:0 0 28px rgba(34,197,94,.18);}
.x-week-day {font-size:1.1rem; font-weight:950; color:white;}
.x-week-badge {display:inline-block; margin:12px 0 8px; color:#93C5FD; border:1px solid #2563EB; border-radius:999px; padding:7px 10px; font-size:.78rem; font-weight:900;}
.dashboard-tight .x-hero{margin:10px 0 14px 0; padding:26px 28px;}
.dashboard-tight .side-card{margin-bottom:10px;}
.dashboard-title{font-size:1.1rem; font-weight:900; color:#dbeafe; margin:8px 0 10px 0; letter-spacing:.04em;}
.matrix-grid{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:10px 0 8px 0;}
.matrix-card{background:linear-gradient(145deg,#101d31,#0b1627); border:1px solid #294665; border-radius:16px; padding:14px; box-shadow:0 10px 24px rgba(0,0,0,.24);}
.matrix-top{display:flex; justify-content:space-between; align-items:center; gap:8px;}
.matrix-name{font-size:1rem; font-weight:900; color:#f8fafc;}
.matrix-badge{display:inline-block; padding:4px 9px; border-radius:999px; font-size:.7rem; font-weight:900; letter-spacing:.06em; text-transform:uppercase; border:1px solid transparent;}
.matrix-ready{color:#bbf7d0; background:rgba(34,197,94,.16); border-color:rgba(34,197,94,.55);}
.matrix-moderate{color:#fef08a; background:rgba(250,204,21,.16); border-color:rgba(250,204,21,.55);}
.matrix-recovering{color:#fdba74; background:rgba(249,115,22,.16); border-color:rgba(249,115,22,.55);}
.matrix-fatigued{color:#fca5a5; background:rgba(239,68,68,.14); border-color:rgba(239,68,68,.55);}
.matrix-meta{color:#b8c2d1; font-size:.8rem; margin-top:6px;}
.matrix-pct{font-size:1.35rem; font-weight:900; color:#fff; margin-top:8px;}
.matrix-action{font-size:.78rem; color:#dbeafe; margin-top:8px; min-height:34px;}
.matrix-bar{height:8px; background:#12243a; border:1px solid #243a55; border-radius:999px; overflow:hidden; margin-top:8px;}
.matrix-fill{height:100%; border-radius:999px; background:linear-gradient(90deg,#2563eb,#22c55e);}
@media(max-width:1100px){.matrix-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:760px){.matrix-grid{grid-template-columns:1fr;}.dashboard-tight .x-hero{padding:20px 18px;}}
@media(max-width: 850px){.x-hero{padding:28px 22px}.x-title{font-size:2.2rem}.x-recovery{position:relative; right:auto; top:auto; text-align:left; margin-top:24px}.x-recovery .big{font-size:3rem}.x-mission{grid-template-columns:1fr}.x-ai{grid-template-columns:1fr}.x-ai-mini{border-left:none; padding-left:0; border-top:1px solid rgba(255,255,255,.12); padding-top:14px}}


/* Sprint X.5 Smart Workout Experience */
.smart-shell{background:linear-gradient(135deg,#08111F,#0B1B35);border:1px solid rgba(96,165,250,.45);border-radius:28px;padding:28px;margin:18px 0 24px;box-shadow:0 24px 70px rgba(0,0,0,.45)}
.smart-top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;flex-wrap:wrap}.smart-kicker{letter-spacing:.25em;color:#22C55E;font-size:.78rem;font-weight:950;text-transform:uppercase}.smart-title{font-size:2.7rem;font-weight:950;color:#fff;margin:10px 0 8px}.smart-sub{color:#BFD7FF;font-size:1rem}.smart-score{font-size:3.2rem;font-weight:950;color:#22C55E;text-align:right}.smart-score-label{color:#fff;font-weight:900;letter-spacing:.16em;text-align:right}.smart-card{background:linear-gradient(145deg,#0F1F34,#0A1728);border:1px solid rgba(96,165,250,.32);border-radius:24px;padding:22px;margin:16px 0;box-shadow:0 16px 45px rgba(0,0,0,.32)}
.smart-photo-box{background:#081322;border:1px solid #1d3655;border-radius:22px;padding:10px;display:flex;align-items:center;justify-content:center;min-height:330px}.smart-photo{width:100%;height:330px;object-fit:contain;border-radius:16px;background:#06111f}.smart-exercise-title{font-size:2rem;color:white;font-weight:950;margin-bottom:8px}.smart-chip{display:inline-block;background:#0B2B4F;border:1px solid #60A5FA;color:#C8DDFF;border-radius:999px;padding:8px 12px;font-weight:900;font-size:.82rem;margin-right:8px;margin-bottom:8px}.smart-chip.green{background:rgba(34,197,94,.13);border-color:#22C55E;color:#B7FFCE}.smart-chip.purple{background:rgba(139,92,246,.16);border-color:#8B5CF6;color:#DDD6FE}.smart-control{background:#0B1E33;border:1px solid #254264;border-radius:18px;padding:16px}.smart-big-value{font-size:2rem;font-weight:950;color:white}.smart-complete{background:linear-gradient(135deg,#22C55E,#16A34A);border-radius:20px;padding:18px;text-align:center;color:white;font-size:1.2rem;font-weight:950;margin-top:14px;box-shadow:0 15px 40px rgba(34,197,94,.35)}
.smart-timer{background:radial-gradient(circle at center,rgba(34,197,94,.20),rgba(15,31,52,.95));border:1px solid rgba(34,197,94,.50);border-radius:24px;padding:24px;text-align:center}.smart-timer-number{font-size:3.6rem;line-height:1;color:white;font-weight:950}.smart-timer-label{color:#86EFAC;font-weight:950;letter-spacing:.15em;margin-top:8px}.smart-progress{height:14px;background:#132940;border:1px solid #24334A;border-radius:999px;overflow:hidden;margin:14px 0}.smart-progress-fill{height:100%;background:linear-gradient(90deg,#2563EB,#22C55E);border-radius:999px}.smart-ai{background:linear-gradient(135deg,rgba(139,92,246,.22),rgba(15,31,52,.98));border:1px solid rgba(139,92,246,.55);border-radius:22px;padding:20px;color:white}.smart-muted{color:#B8C2D1}.smart-nav-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}@media(max-width:900px){.smart-title{font-size:2rem}.smart-score{text-align:left;font-size:2.5rem}.smart-score-label{text-align:left}.smart-photo,.smart-photo-box{height:250px;min-height:250px}}

.mobile-nav-shell{position:sticky; top:0; z-index:12; backdrop-filter:blur(8px); background:rgba(7,17,31,.92); border:1px solid rgba(59,130,246,.35); border-radius:16px; padding:8px 10px; margin:0 0 12px 0}
.rest-timer-card{background:linear-gradient(135deg,#0f1f34,#0a1728);border:1px solid rgba(96,165,250,.35);border-radius:20px;padding:16px;margin-top:12px}
.rest-countdown{font-size:2.4rem;font-weight:900;color:#22c55e;text-align:center;margin:6px 0 10px 0}
.session-summary{background:linear-gradient(135deg,#0f1f34,#0a1728);border:1px solid rgba(34,197,94,.45);border-radius:24px;padding:18px;margin:14px 0}
.history-session-card{background:linear-gradient(135deg,#0f1f34,#0a1728);border:1px solid rgba(96,165,250,.35);border-radius:18px;padding:14px;margin:10px 0}
.chart-shell{background:#0e1a2d;border:1px solid rgba(96,165,250,.24);border-radius:16px;padding:10px}

@media (max-width: 850px){
    section[data-testid="stSidebar"]{display:none !important;}
    div[data-testid="stHorizontalBlock"] button[kind="secondary"]{min-height:44px; font-size:0.95rem; font-weight:800;}
    .title{font-size:1.6rem}
    .x-title{font-size:1.85rem}
    .mobile-nav-shell div[role="radiogroup"]{overflow-x:auto; white-space:nowrap; display:flex; gap:6px; padding-bottom:2px}
    .mobile-nav-shell label{flex:0 0 auto}
}



/* Sprint X.6 Elite Workout Experience */
.x6-hero{background:linear-gradient(135deg,#07111f,#0b2a4d 55%,#12375f);border:1px solid rgba(96,165,250,.42);border-radius:28px;padding:28px;margin:18px 0 22px 0;box-shadow:0 22px 60px rgba(0,0,0,.45)}
.x6-kicker{font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;color:#22c55e;font-weight:950}.x6-title{font-size:2.8rem;line-height:1.02;color:#fff;font-weight:950;margin:.35rem 0}.x6-sub{color:#b8c2d1;font-size:1rem}.x6-card{background:linear-gradient(180deg,#111827,#0f1f34);border:1px solid rgba(148,163,184,.16);border-radius:26px;padding:22px;box-shadow:0 18px 46px rgba(0,0,0,.38);margin-bottom:18px}.x6-photo-wrap{height:420px;background:radial-gradient(circle at center,#172554,#07111f);border:1px solid rgba(96,165,250,.25);border-radius:24px;display:flex;align-items:center;justify-content:center;overflow:hidden}.x6-photo-wrap img{width:100%;height:100%;object-fit:contain;padding:16px}.x6-ex-name{font-size:2.15rem;color:#fff;font-weight:950;line-height:1.08}.x6-pill{display:inline-block;margin:8px 8px 0 0;padding:9px 13px;border-radius:999px;background:rgba(37,99,235,.18);border:1px solid rgba(96,165,250,.35);color:#dbeafe;font-weight:900}.x6-pill.green{background:rgba(34,197,94,.18);border-color:rgba(34,197,94,.42);color:#dcfce7}.x6-pill.purple{background:rgba(139,92,246,.18);border-color:rgba(139,92,246,.42);color:#ede9fe}.x6-progress{height:16px;background:#0b1729;border:1px solid #24334a;border-radius:999px;overflow:hidden;margin:14px 0}.x6-progress-fill{height:100%;background:linear-gradient(90deg,#2563eb,#22c55e);border-radius:999px}.x6-big-metric{font-size:3rem;color:#fff;font-weight:950;line-height:1}.x6-label{color:#93a4bd;font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;font-weight:950}.x6-coach{background:linear-gradient(135deg,rgba(139,92,246,.26),rgba(15,31,52,.98));border:1px solid rgba(139,92,246,.55);border-radius:24px;padding:20px;color:white;box-shadow:0 14px 40px rgba(0,0,0,.32)}.x6-timer{background:linear-gradient(135deg,rgba(34,197,94,.24),rgba(15,31,52,.98));border:1px solid rgba(34,197,94,.50);border-radius:24px;padding:22px;text-align:center;margin-top:12px}.x6-timer-num{font-size:3.8rem;color:#fff;font-weight:950;line-height:1}.x6-mini{background:#0b1729;border:1px solid #24334a;border-radius:18px;padding:16px}.x6-list-item{background:#0f1f34;border:1px solid #24334a;border-radius:18px;padding:12px 14px;margin:8px 0;color:#fff}.x6-complete button{background:linear-gradient(135deg,#16a34a,#22c55e)!important;color:white!important;border:none!important;min-height:64px!important;border-radius:20px!important;font-size:1.18rem!important;font-weight:950!important;box-shadow:0 14px 35px rgba(34,197,94,.35)!important}.x6-finish button{background:linear-gradient(135deg,#f59e0b,#f97316)!important;color:white!important;border:none!important;min-height:56px!important;border-radius:18px!important;font-weight:950!important}.x6-nav button{min-height:52px!important;border-radius:16px!important;font-weight:900!important}@media(max-width:900px){.x6-photo-wrap{height:300px}.x6-title{font-size:2rem}.x6-ex-name{font-size:1.55rem}.x6-big-metric{font-size:2.3rem}}

</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Navigation — desktop sidebar + phone-friendly top menu
nav_options = ["Dashboard","Today's Workout","Gym Mode","AI Coach","Workout Builder","Weekly Plan","System Check","Nutrition","Supplements","Body Stats","Smart Scale","Recovery Center","Progress Analytics","Exercise Library","History","Data Manager"]
st.sidebar.markdown("## 🏋️ Brian Fit 6.0")
st.sidebar.caption("X.13 Mobile Performance Platform")
st.sidebar.markdown('<div class="safe"><b>✅ Data safe</b><br><br><span class="small">Primary:</span> <b>Supabase</b><br><span class="small">Backup:</span> <b>data/workout_log.csv</b></div>', unsafe_allow_html=True)

page = get_mobile_primary_page()
st.session_state['main_nav'] = page

workouts = load_workouts()
log = load_log()
days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

if page == "Dashboard":
    today = date.today().strftime('%A')
    today_df = workouts[workouts.day == today]
    focus = " / ".join(today_df['muscle_group'].astype(str).dropna().unique().tolist()) if not today_df.empty else "Recovery / Mobility"

    nut = read_csv_safe(NUTRITION, ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes'])
    body_df = read_csv_safe(BODY, ['date','body_weight_lbs','goal_weight_lbs','waist_in','body_fat_pct','muscle_mass_lbs','bmi','water_pct','protein_pct','bone_mass_lbs','bmr_cal','metabolic_age','visceral_fat','lean_body_mass_lbs','notes'])
    recovery_df = read_csv_safe(RECOVERY, RECOVERY_COLUMNS)
    supplements_df = read_csv_safe(SUPPLEMENTS, ['date','creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes','notes'])

    coach_brief = build_daily_brief(
        workouts_df=workouts,
        recovery_df=recovery_df,
        body_df=body_df,
        nutrition_df=nut,
        supplements_df=supplements_df,
        workout_log_df=log,
    )

    muscle_snapshot = build_muscle_readiness_snapshot(
        workout_log_df=log,
        recovery_df=recovery_df,
        body_df=body_df,
    )

    recovery_latest = get_latest_recovery(RECOVERY)
    if recovery_latest:
        recovery_score = int(pd.to_numeric(pd.Series([recovery_latest.get('recovery_pct', 72)]), errors='coerce').fillna(72).iloc[0])
    else:
        recovery_score = 72

    log_view = log.copy()
    if not log_view.empty and 'date' in log_view.columns:
        log_view['date'] = pd.to_datetime(log_view['date'], errors='coerce')
        log_view = log_view.dropna(subset=['date'])

    streak = workout_streak_days(log)
    sessions_7 = 0 if log_view.empty else int(log_view[log_view['date'] >= (pd.Timestamp(date.today()) - pd.Timedelta(days=6))]['date'].dt.date.nunique())
    weekly_progress_pct = min(100, int((sessions_7 / 5.0) * 100))

    if log_view.empty:
        last_workout_text = 'No workouts logged yet.'
    else:
        latest_date = log_view['date'].max()
        latest_rows = log_view[log_view['date'] == latest_date]
        last_workout_text = f"{latest_date.date()} • {len(latest_rows)} sets • {latest_rows['exercise'].nunique()} exercises"

    perf_scores = performance_scores(log)
    pr_summary = build_pr_summary(log)
    workout_grade = compute_workout_grade(log)
    rec_card = recovery_recommendation(recovery_score, workout_grade, muscle_snapshot)

    readiness_status = 'Ready' if recovery_score >= 85 else ('Moderate' if recovery_score >= 70 else 'Recovery Focus')
    muscles = muscle_snapshot.get('muscles', {})

    def _muscle_pct(name: str) -> float:
        item = muscles.get(name, {})
        return float(item.get('readiness_percent', 65) or 65)

    muscle_recovery_avg = (
        _muscle_pct('chest')
        + _muscle_pct('back')
        + _muscle_pct('shoulders')
        + _muscle_pct('biceps')
        + _muscle_pct('triceps')
        + _muscle_pct('core')
        + ((_muscle_pct('quads') + _muscle_pct('hamstrings') + _muscle_pct('glutes') + _muscle_pct('calves')) / 4.0)
    ) / 7.0

    today_s = str(date.today())
    today_nut = nut[nut['date'].astype(str) == today_s] if not nut.empty and 'date' in nut.columns else pd.DataFrame()
    water_today = int(pd.to_numeric(today_nut.get('water_oz', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_nut.empty else 0
    protein_today = int(pd.to_numeric(today_nut.get('protein_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_nut.empty else 0

    st.markdown(textwrap.dedent(f"""
    <div class="x-hero" style="margin-bottom:14px;">
        <div class="x-kicker">Brian Fit 6.0 • X.13 Mobile Performance Platform</div>
      <div class="x-title" style="font-size:2.35rem;">Good Morning Brian</div>
      <div class="x-sub">Recovery {recovery_score}% • Readiness {readiness_status} • Today's Focus: {focus}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
        <div class="small"><b>Last Workout:</b> {last_workout_text}<br><b>Workout Streak:</b> {streak} day(s)</div>
        <div class="small"><b>Weekly Progress:</b> {weekly_progress_pct}% ({sessions_7}/5 sessions)<br><b>AI Note:</b> {coach_brief.next_best_action}</div>
      </div>
    </div>
    """), unsafe_allow_html=True)

    start_col, _ = st.columns([0.28, 0.72])
    with start_col:
        if st.button('▶ START WORKOUT', use_container_width=True, key='x8_start_workout'):
            st.session_state['main_nav'] = "Today's Workout"
            st.rerun()

    metric_cards = [
        ('💪', 'Strength Score', f'{perf_scores["strength_score"]:.1f}', 'Power index'),
        ('🏃', 'Fitness Score', f'{perf_scores["fitness_score"]:.1f}', 'Conditioning index'),
        ('📈', 'Weekly Volume', f'{int(perf_scores["weekly_volume"]):,}', 'lbs lifted'),
        ('🏆', 'Personal Records', f'{int(pr_summary["total_prs"])}', 'exercise PRs'),
        ('🎯', 'Workout Grade', str(workout_grade.label), f'{workout_grade.overall_score:.1f}/100'),
        ('🧠', 'Muscle Recovery', f'{muscle_recovery_avg:.0f}%', 'readiness average'),
    ]

    st.markdown('### Key Metrics')
    card_cols = st.columns(6)
    for col, (icon, label, value, subtext) in zip(card_cols, metric_cards):
        if label == 'Workout Grade':
            col.markdown(
                f'<div class="metric-card"><div class="metric-label">{icon} {label}</div><div class="metric-value-wrap">{value}</div><div class="metric-subvalue">{subtext}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            col.markdown(
                f'<div class="metric-card"><div class="metric-label">{icon} {label}</div><div class="metric-value">{value}</div><div class="small">{subtext}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('### AI Coach')
    st.markdown(
        f"""
        <div class="side-card" style="margin-bottom:10px;">
          <div class="side-title">Today\'s Recommendation</div>
          <div class="small"><b>Recommendation:</b> {coach_brief.next_best_action}</div>
          <div class="small" style="margin-top:7px;"><b>Training Plan:</b> {coach_brief.training_recommendation}</div>
          <div class="small" style="margin-top:7px;"><b>Water Goal:</b> {water_today}/100 oz today</div>
          <div class="small" style="margin-top:7px;"><b>Protein Goal:</b> {protein_today}/160g today</div>
          <div class="small" style="margin-top:7px;"><b>Sleep Goal:</b> 7.5 - 9.0 hours</div>
          <div class="small" style="margin-top:7px;"><b>Recovery Note:</b> {rec_card['note']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('### Progress Snapshot')
    chart_c1, chart_c2, chart_c3 = st.columns(3)

    if log_view.empty:
        chart_c1.info('No workout data for weekly volume trend.')
        chart_c2.info('No workout data for frequency trend.')
    else:
        vols = log_view.groupby(log_view['date'].dt.date, as_index=False)['volume'].sum().tail(14)
        vols.columns = ['date', 'volume']
        chart_c1.markdown('<div class="small"><b>Weekly Volume Trend</b></div>', unsafe_allow_html=True)
        chart_c1.line_chart(vols.set_index('date')['volume'])

        freq = log_view.groupby(log_view['date'].dt.date).size().reset_index(name='sessions').tail(14)
        freq.columns = ['date', 'sessions']
        chart_c2.markdown('<div class="small"><b>Workout Frequency</b></div>', unsafe_allow_html=True)
        chart_c2.bar_chart(freq.set_index('date')['sessions'])

    bw_df = body_df.copy()
    if not bw_df.empty and 'date' in bw_df.columns and 'body_weight_lbs' in bw_df.columns:
        bw_df['date'] = pd.to_datetime(bw_df['date'], errors='coerce')
        bw_df['body_weight_lbs'] = pd.to_numeric(bw_df['body_weight_lbs'], errors='coerce')
        bw_df = bw_df.dropna(subset=['date', 'body_weight_lbs']).sort_values('date').tail(14)
    if bw_df.empty:
        chart_c3.info('No body-weight data yet.')
    else:
        chart_c3.markdown('<div class="small"><b>Body Weight Trend</b></div>', unsafe_allow_html=True)
        chart_c3.line_chart(bw_df.set_index('date')['body_weight_lbs'])

    st.markdown('### PR Timeline')
    if log_view.empty:
        st.info('No PRs yet. Complete workouts to unlock personal records.')
    else:
        pr_source = log_view.copy()
        pr_source['exercise'] = pr_source['exercise'].astype(str).str.strip()
        pr_source = pr_source[pr_source['exercise'].ne('')]
        if pr_source.empty:
            st.info('No PRs yet. Complete workouts to unlock personal records.')
        else:
            for c in ['weight_lbs', 'reps', 'volume']:
                pr_source[c] = pd.to_numeric(pr_source.get(c, 0), errors='coerce').fillna(0)
            pr_source['est_1rm'] = pr_source['weight_lbs'] * (1 + (pr_source['reps'] / 30.0))
            maxes = pr_source.groupby('exercise', as_index=False).agg(
                max_weight=('weight_lbs', 'max'),
                max_reps=('reps', 'max'),
                max_1rm=('est_1rm', 'max'),
                max_volume=('volume', 'max'),
            )
            merged = pr_source.merge(maxes, on='exercise', how='left')
            events = []
            for _, r in merged.iterrows():
                tags = []
                if r['weight_lbs'] == r['max_weight'] and r['weight_lbs'] > 0:
                    tags.append('Heaviest')
                if r['reps'] == r['max_reps'] and r['reps'] > 0:
                    tags.append('Most Reps')
                if r['est_1rm'] == r['max_1rm'] and r['est_1rm'] > 0:
                    tags.append('Best 1RM')
                if r['volume'] == r['max_volume'] and r['volume'] > 0:
                    tags.append('Top Volume')
                if tags:
                    events.append({
                        'date': str(pd.Timestamp(r['date']).date()),
                        'exercise': r['exercise'],
                        'records': ', '.join(tags),
                        'weight_lbs': round(float(r['weight_lbs']), 1),
                        'reps': int(r['reps']),
                        'est_1rm': round(float(r['est_1rm']), 1),
                        'volume': round(float(r['volume']), 1),
                    })
            if not events:
                st.info('No PRs yet. Complete workouts to unlock personal records.')
            else:
                events_df = pd.DataFrame(events).drop_duplicates(subset=['date', 'exercise', 'records']).sort_values('date', ascending=False).head(12)
                st.dataframe(events_df, use_container_width=True)

elif page == "Today's Workout":
    day = st.selectbox("Workout Day", days, index=date.today().weekday() if date.today().weekday()<7 else 0, key="x6_day")
    active = workouts[workouts.day == day].reset_index(drop=True)
    group = active.muscle_group.iloc[0] if not active.empty else "Recovery / Rest"
    log_now = load_log()
    completed_today = 0
    total_volume_today = 0
    if not log_now.empty and 'date' in log_now.columns and 'day' in log_now.columns:
        todays = log_now[(log_now['date'].astype(str) == str(date.today())) & (log_now['day'].astype(str) == day)].copy()
        completed_today = len(todays)
        if 'volume' in todays.columns:
            total_volume_today = int(pd.to_numeric(todays['volume'], errors='coerce').fillna(0).sum())
    target_sets_today = 0 if active.empty else int(pd.to_numeric(active.get('target_sets', pd.Series([3]*len(active))), errors='coerce').fillna(3).sum())
    progress_pct = 0 if target_sets_today == 0 else min(100, int((completed_today / max(1, target_sets_today)) * 100))

    st.markdown(f"""
    <div class="x6-hero">
      <div class="x6-kicker">Brian Fitness Tracker X • Sprint X.6 Elite Workout Experience</div>
      <div class="x6-title">{day} — {group}</div>
      <div class="x6-sub">One-exercise command center with large visuals, set logging, rest timing, progress, and workout finish summary.</div>
      <div class="x6-progress"><div class="x6-progress-fill" style="width:{progress_pct}%;"></div></div>
      <div class="x6-sub">Progress {progress_pct}% • {completed_today}/{target_sets_today} sets complete • {total_volume_today:,} lbs today</div>
    </div>
    """, unsafe_allow_html=True)

    if active.empty:
        st.success("Recovery day. Use mobility, walking, sauna, swimming, or rest.")
    else:
        flow_key = 'x6'
        session_id = make_workout_session_id(flow_key)
        pending_sets = get_pending_sets(flow_key)
        saving_key = f'{flow_key}_saving'
        is_saving = bool(st.session_state.get(saving_key, False))
        if f'{flow_key}_started_at' not in st.session_state or st.session_state.get(f'{flow_key}_started_at') is None:
            st.session_state[f'{flow_key}_started_at'] = datetime.now()

        if 'x6_idx' not in st.session_state:
            st.session_state.x6_idx = 0
        st.session_state.x6_idx = max(0, min(int(st.session_state.x6_idx), len(active)-1))
        row = active.iloc[st.session_state.x6_idx]
        sets = int(row.target_sets) if str(row.target_sets).isdigit() else 3
        target_reps_display = str(row.target_reps)
        try:
            reps_default = int(target_reps_display.split('-')[-1].split()[0])
        except Exception:
            reps_default = 12
        recent_ex = pd.DataFrame()
        if not log_now.empty and 'exercise' in log_now.columns:
            recent_ex = log_now[log_now['exercise'].astype(str) == str(row.exercise)].copy()
        last_weight, last_reps, best_weight = get_recent_exercise_stats(log_now, row.exercise)
        if last_weight <= 0:
            last_weight = float(row.base_weight)
        if best_weight <= 0:
            best_weight = float(row.base_weight)

        photo_html = img_tag(image_path(row)).replace('class="exercise-photo"', 'class="x6-photo"')
        # Fetch exercise intelligence
        ex_intel = ExerciseIntelligence()
        exercise_data = ex_intel.get_profile(row.exercise)
        # Use Workout Command Center component to render UI and capture events/values
        result = workout_command_center(
            row=row.to_dict(),
            idx=st.session_state.x6_idx,
            total=len(active),
            photo_html=photo_html,
            last_weight=last_weight,
            last_reps=last_reps,
            best_weight=best_weight,
            sets=sets,
            reps_default=reps_default,
            ai_cue="Control the eccentric. Own every rep.",
            completed_today=completed_today,
            total_volume_today=total_volume_today,
            day=day,
            exercise_data=exercise_data,
            key_prefix="x6",
        )
        # Preserve existing logging behavior: when complete, save log and advance
        if result.get('complete'):
            st.session_state[saving_key] = True
            set_row = build_set_row(day=day, exercise=row.exercise, result=result, session_id=session_id)
            single_set_result = save_completed_set(set_row)
            save_result = {
                'supabase_ok': bool(single_set_result.get('ok')),
                'supabase_error': str(single_set_result.get('cloud_error', '') or ''),
                'csv_ok': bool(single_set_result.get('csv_backup_ok', True)),
                'csv_error': str(single_set_result.get('csv_backup_error', '') or ''),
                'sets_attempted': int(single_set_result.get('sets_attempted', 1)),
                'sets_inserted': int(single_set_result.get('sets_inserted', 0)),
                'duplicates_skipped': int(single_set_result.get('duplicates_skipped', 0)),
                'verified_rows': int(single_set_result.get('verified_rows', 0)),
                'exercises_saved': 1,
                'session_id': str(single_set_result.get('session_id', session_id)),
                'session_id_supported': bool(single_set_result.get('session_id_supported', False)),
                'session_id_used': bool(single_set_result.get('session_id_supported', False) and str(single_set_result.get('session_id', session_id))),
                'already_saved': bool(single_set_result.get('already_saved', False)),
                'status': str(single_set_result.get('status', '')),
                'history_source': str(single_set_result.get('history_source', 'Supabase Cloud' if single_set_result.get('ok') else 'Local CSV Backup')),
                'verified_cloud_row_count': int(single_set_result.get('after_count', 0)),
            }
            update_cloud_sync_state(
                ok=bool(save_result.get('supabase_ok')),
                message='Workout saved permanently' if bool(save_result.get('supabase_ok')) else 'Cloud save failed',
                inserted=int(save_result.get('sets_inserted', 0)),
                error=str(save_result.get('supabase_error', '')),
            )
            previous_debug = st.session_state.get('last_save_debug', {})
            st.session_state['last_save_debug'] = {
                'attempted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success' if bool(save_result.get('supabase_ok')) else 'error',
                'error': str(save_result.get('supabase_error', '') or save_result.get('csv_error', '') or ''),
                'last_saved_exercise': str(row.exercise),
                'last_save_source': 'supabase' if bool(save_result.get('supabase_ok')) else 'backup_only',
                'last_workout_session_id': str(save_result.get('session_id', session_id)),
                'session_id_supported': bool(save_result.get('session_id_supported', False)),
                'session_id_used': bool(save_result.get('session_id_used', False)),
                'sets_attempted': int(save_result.get('sets_attempted', 1)),
                'sets_inserted': int(save_result.get('sets_inserted', 0)),
                'duplicates_skipped': int(save_result.get('duplicates_skipped', 0)),
                'verified_rows': int(save_result.get('verified_rows', 0)),
                'history_source': str(save_result.get('history_source', 'Supabase Cloud' if bool(save_result.get('supabase_ok')) else 'Local CSV Backup')),
                'last_successful_sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if bool(save_result.get('supabase_ok')) else str(previous_debug.get('last_successful_sync_time', '')),
                'save_source_label': 'today_complete_set',
                'workout': dict(set_row),
            }
            if save_result.get('supabase_ok'):
                # Keep an in-session mirror so Finish can submit full workout session safely on mobile reruns.
                pending_sets[:] = [
                    s for s in pending_sets
                    if not (
                        str(s.get('exercise', '')).strip().lower() == str(set_row.get('exercise', '')).strip().lower()
                        and int(float(s.get('set_number', 0) or 0)) == int(float(set_row.get('set_number', 0) or 0))
                    )
                ]
                pending_sets.append(set_row)
                timer_state = get_rest_timer_state(flow_key)
                timer_state['remaining'] = int(timer_state.get('duration', 90))
                timer_state['running'] = False
                timer_state['started_at'] = None
                timer_state['last_completed_set_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                render_cloud_save_success(save_result)
                if st.session_state.x6_idx < len(active)-1:
                    st.session_state[saving_key] = False
                    st.session_state.x6_idx += 1
                    st.rerun()
            else:
                render_cloud_save_failure(save_result)
            st.session_state[saving_key] = False
        if result.get('prev'):
            st.session_state.x6_idx = max(0, st.session_state.x6_idx - 1)
            st.rerun()
        if result.get('next'):
            st.session_state.x6_idx = min(len(active)-1, st.session_state.x6_idx + 1)
            st.rerun()
        if result.get('finish'):
            st.session_state[saving_key] = True
            session_sets = list(pending_sets)
            if not session_sets:
                st.warning('No completed sets in this session yet. Complete at least one set before finishing.')
            else:
                save_result = save_rows_to_cloud_then_backup(session_sets, save_source_label='today_finish_workout')
                if save_result.get('supabase_ok'):
                    render_cloud_save_success(save_result)
                    clear_pending_sets(flow_key)
                else:
                    render_cloud_save_failure(save_result)
            st.session_state[saving_key] = False

        nav1, nav2, nav3, nav4 = st.columns(4)
        with nav1:
            if st.button("← Previous", use_container_width=True, disabled=st.session_state.x6_idx <= 0, key="x6_prev"):
                st.session_state.x6_idx -= 1
                st.rerun()
        with nav2:
            if st.button("Next →", use_container_width=True, disabled=st.session_state.x6_idx >= len(active)-1, key="x6_next"):
                st.session_state.x6_idx += 1
                st.rerun()
        with nav3:
            st.download_button("Export Log", LOG.read_bytes(), file_name="workout_log.csv", use_container_width=True, key="x6_export")
        with nav4:
            st.markdown('<div class="x6-finish">', unsafe_allow_html=True)
            finish = st.button("🏁 Finish Workout", use_container_width=True, key="x6_finish", disabled=is_saving)
            st.markdown('</div>', unsafe_allow_html=True)
        if finish:
            st.session_state[saving_key] = True
            session_sets = list(pending_sets)
            if not session_sets:
                st.warning('No completed sets in this session yet. Complete at least one set before finishing.')
            else:
                save_result = save_rows_to_cloud_then_backup(session_sets, save_source_label='today_finish_button')
                if save_result.get('supabase_ok'):
                    render_cloud_save_success(save_result)
                    render_session_summary(save_result, session_sets, flow_key=flow_key)
                    clear_pending_sets(flow_key)
                    st.session_state[f'{flow_key}_started_at'] = None
                else:
                    render_cloud_save_failure(save_result)
            st.session_state[saving_key] = False

        session_metrics = build_session_metrics(list(pending_sets), started_at=st.session_state.get(f'{flow_key}_started_at'))
        m1, m2, m3 = st.columns(3)
        m1.metric('Sets Completed', str(session_metrics.get('set_count', 0)))
        m2.metric('Session Volume', f"{int(session_metrics.get('total_volume', 0)):,} lbs")
        m3.metric('Session Duration', f"{int(session_metrics.get('duration_min', 0))} min")
        render_rest_timer(flow_key)

        st.markdown("### Workout Flow")
        for idx, ex in active.iterrows():
            status = "✅" if idx < st.session_state.x6_idx else ("▶️" if idx == st.session_state.x6_idx else "○")
            st.markdown(f'<div class="x6-list-item"><b>{status} {idx+1}. {ex.exercise}</b> <span class="x6-sub">• {ex.target_sets} × {ex.target_reps} • {ex.muscle_group}</span></div>', unsafe_allow_html=True)



elif page == "Gym Mode":
    day = st.selectbox("Workout Day", days, index=date.today().weekday() if date.today().weekday()<7 else 0, key="gym_day")
    active = workouts[workouts.day==day].reset_index(drop=True)
    group = active.muscle_group.iloc[0] if not active.empty else 'Recovery / Rest'
    st.markdown(f'<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Gym Mode</div><div class="sub">{day} — {group}. One exercise at a time with larger controls.</div></div>', unsafe_allow_html=True)
    if active.empty:
        st.success("Recovery day. Mobility, walking, sauna, swimming, or rest.")
    else:
        flow_key = 'gym'
        session_id = make_workout_session_id(flow_key)
        pending_sets = get_pending_sets(flow_key)
        saving_key = f'{flow_key}_saving'
        is_saving = bool(st.session_state.get(saving_key, False))
        if f'{flow_key}_started_at' not in st.session_state or st.session_state.get(f'{flow_key}_started_at') is None:
            st.session_state[f'{flow_key}_started_at'] = datetime.now()

        idx = st.number_input("Exercise number", min_value=1, max_value=len(active), value=1, step=1) - 1
        row = active.iloc[int(idx)]
        st.markdown(f'<div class="exercise-card"><div class="exercise-head"><div class="num">{idx+1}</div><div><div class="ex-title">{row.exercise}</div><span class="badge">Target: {row.target_sets} × {row.target_reps}</span><span class="badge green">{row.muscle_group}</span></div></div>', unsafe_allow_html=True)
        # Replace Gym Mode set logging UI with Workout Command Center for consistent UX
        photo_html = img_tag(image_path(row)).replace('class="exercise-photo"', 'class="exercise-photo"')
        # Fetch exercise intelligence
        ex_intel = ExerciseIntelligence()
        exercise_data = ex_intel.get_profile(row.exercise)
        result = workout_command_center(
            row=row.to_dict(),
            idx=int(idx),
            total=len(active),
            photo_html=photo_html,
            last_weight=get_recent_exercise_stats(load_log(), row.exercise)[0] or float(row.base_weight),
            last_reps=get_recent_exercise_stats(load_log(), row.exercise)[1],
            best_weight=get_recent_exercise_stats(load_log(), row.exercise)[2] or float(row.base_weight),
            sets=row.target_sets,
            reps_default=12,
            ai_cue="Coach: stay controlled and log every set.",
            completed_today=0,
            total_volume_today=0,
            day=day,
            exercise_data=exercise_data,
            key_prefix="gym",
        )
        if result.get('complete'):
            st.session_state[saving_key] = True
            set_row = build_set_row(day=day, exercise=row.exercise, result=result, session_id=session_id)
            single_set_result = save_completed_set(set_row)
            save_result = {
                'supabase_ok': bool(single_set_result.get('ok')),
                'supabase_error': str(single_set_result.get('cloud_error', '') or ''),
                'csv_ok': bool(single_set_result.get('csv_backup_ok', True)),
                'csv_error': str(single_set_result.get('csv_backup_error', '') or ''),
                'sets_attempted': int(single_set_result.get('sets_attempted', 1)),
                'sets_inserted': int(single_set_result.get('sets_inserted', 0)),
                'duplicates_skipped': int(single_set_result.get('duplicates_skipped', 0)),
                'verified_rows': int(single_set_result.get('verified_rows', 0)),
                'exercises_saved': 1,
                'session_id': str(single_set_result.get('session_id', session_id)),
                'session_id_supported': bool(single_set_result.get('session_id_supported', False)),
                'session_id_used': bool(single_set_result.get('session_id_supported', False) and str(single_set_result.get('session_id', session_id))),
                'already_saved': bool(single_set_result.get('already_saved', False)),
                'status': str(single_set_result.get('status', '')),
                'history_source': str(single_set_result.get('history_source', 'Supabase Cloud' if single_set_result.get('ok') else 'Local CSV Backup')),
                'verified_cloud_row_count': int(single_set_result.get('after_count', 0)),
            }
            update_cloud_sync_state(
                ok=bool(save_result.get('supabase_ok')),
                message='Workout saved permanently' if bool(save_result.get('supabase_ok')) else 'Cloud save failed',
                inserted=int(save_result.get('sets_inserted', 0)),
                error=str(save_result.get('supabase_error', '')),
            )
            previous_debug = st.session_state.get('last_save_debug', {})
            st.session_state['last_save_debug'] = {
                'attempted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success' if bool(save_result.get('supabase_ok')) else 'error',
                'error': str(save_result.get('supabase_error', '') or save_result.get('csv_error', '') or ''),
                'last_saved_exercise': str(row.exercise),
                'last_save_source': 'supabase' if bool(save_result.get('supabase_ok')) else 'backup_only',
                'last_workout_session_id': str(save_result.get('session_id', session_id)),
                'session_id_supported': bool(save_result.get('session_id_supported', False)),
                'session_id_used': bool(save_result.get('session_id_used', False)),
                'sets_attempted': int(save_result.get('sets_attempted', 1)),
                'sets_inserted': int(save_result.get('sets_inserted', 0)),
                'duplicates_skipped': int(save_result.get('duplicates_skipped', 0)),
                'verified_rows': int(save_result.get('verified_rows', 0)),
                'history_source': str(save_result.get('history_source', 'Supabase Cloud' if bool(save_result.get('supabase_ok')) else 'Local CSV Backup')),
                'last_successful_sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if bool(save_result.get('supabase_ok')) else str(previous_debug.get('last_successful_sync_time', '')),
                'save_source_label': 'gym_complete_set',
                'workout': dict(set_row),
            }
            if save_result.get('supabase_ok'):
                pending_sets[:] = [
                    s for s in pending_sets
                    if not (
                        str(s.get('exercise', '')).strip().lower() == str(set_row.get('exercise', '')).strip().lower()
                        and int(float(s.get('set_number', 0) or 0)) == int(float(set_row.get('set_number', 0) or 0))
                    )
                ]
                pending_sets.append(set_row)
                timer_state = get_rest_timer_state(flow_key)
                timer_state['remaining'] = int(timer_state.get('duration', 90))
                timer_state['running'] = False
                timer_state['started_at'] = None
                timer_state['last_completed_set_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                render_cloud_save_success(save_result)
            else:
                render_cloud_save_failure(save_result)
            st.session_state[saving_key] = False
        if result.get('finish'):
            st.session_state[saving_key] = True
            session_sets = list(pending_sets)
            if not session_sets:
                st.warning('No completed sets in this session yet. Complete at least one set before finishing.')
            else:
                save_result = save_rows_to_cloud_then_backup(session_sets, save_source_label='gym_finish_workout')
                if save_result.get('supabase_ok'):
                    render_cloud_save_success(save_result)
                    render_session_summary(save_result, session_sets, flow_key=flow_key)
                    clear_pending_sets(flow_key)
                    st.session_state[f'{flow_key}_started_at'] = None
                else:
                    render_cloud_save_failure(save_result)
            st.session_state[saving_key] = False
        session_metrics = build_session_metrics(list(pending_sets), started_at=st.session_state.get(f'{flow_key}_started_at'))
        s1, s2, s3 = st.columns(3)
        s1.metric('Sets Completed', str(session_metrics.get('set_count', 0)))
        s2.metric('Session Volume', f"{int(session_metrics.get('total_volume', 0)):,} lbs")
        s3.metric('Session Duration', f"{int(session_metrics.get('duration_min', 0))} min")
        render_rest_timer(flow_key)
        n1,n2=st.columns(2)
        with n1:
            if idx > 0: st.caption(f"Previous: {active.iloc[idx-1].exercise}")
        with n2:
            if idx < len(active)-1: st.caption(f"Next: {active.iloc[idx+1].exercise}")
        st.markdown('</div>', unsafe_allow_html=True)


elif page == "AI Coach":
    st.markdown('<div class="hero"><div class="kicker">PROJECT TITAN</div><div class="title">AI Coach Center</div><div class="sub">Central coaching brain powered by recovery, training, nutrition, body intelligence, supplements, and weekly performance data.</div></div>', unsafe_allow_html=True)

    log = load_log()
    workouts_df = load_workouts()
    recovery_df = read_csv_safe(RECOVERY, RECOVERY_COLUMNS)
    nut = read_csv_safe(NUTRITION, ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes'])
    body = read_csv_safe(BODY, BODY_COLUMNS)
    sup = read_csv_safe(SUPPLEMENTS, ['date','creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes','notes'])

    brief = build_daily_brief(
        workouts_df=workouts_df,
        recovery_df=recovery_df,
        body_df=body,
        nutrition_df=nut,
        supplements_df=sup,
        workout_log_df=log,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="metric-label">Recovery Status</div><div class="metric-value" style="font-size:1.15rem;">{brief.recovery_status}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-label">Training</div><div class="metric-value" style="font-size:1.15rem;">{brief.training_recommendation}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-label">Nutrition</div><div class="metric-value" style="font-size:1.15rem;">{brief.nutrition_status}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-label">Body Trend</div><div class="metric-value" style="font-size:1.15rem;">{brief.body_trend}</div></div>', unsafe_allow_html=True)

    st.markdown('## Daily Brief')
    st.markdown(f'<div class="side-card"><div class="side-title">Daily Readiness Summary</div><div class="small">{brief.readiness_summary}</div></div>', unsafe_allow_html=True)

    st.markdown('## Training Guidance')
    st.markdown(f'<div class="side-card"><div class="side-title">Workout Intensity Recommendation</div><div class="small">{brief.workout_intensity_recommendation}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="side-card"><div class="side-title">Muscle Readiness Focus</div><div class="small"><b>Focus:</b> {brief.muscle_recovery_focus}</div><div class="small" style="margin-top:8px;"><b>Avoid:</b> {brief.avoid_muscles}</div></div>', unsafe_allow_html=True)

    st.markdown('## Nutrition Guidance')
    st.markdown(f'<div class="side-card"><div class="side-title">Nutrition Recommendation</div><div class="small">{brief.nutrition_recommendation}</div></div>', unsafe_allow_html=True)

    st.markdown('## Recovery Guidance')
    recovery_guidance = brief.recovery_warning if brief.recovery_warning else 'No readiness note. Continue with planned recovery fundamentals.'
    st.markdown(f'<div class="side-card"><div class="side-title">Readiness Note</div><div class="small">{recovery_guidance}</div></div>', unsafe_allow_html=True)

    st.markdown('## Body Intelligence Insight')
    st.markdown(f'<div class="side-card"><div class="side-title">Body Composition Insight</div><div class="small">{brief.body_composition_insight}</div></div>', unsafe_allow_html=True)

    st.markdown('## Weekly Coaching Notes')
    st.markdown(f'<div class="side-card"><div class="side-title">Weekly Notes</div><div class="small">{brief.weekly_coaching_notes}</div><div class="small" style="margin-top:10px;"><b>Next Best Action:</b> {brief.next_best_action}</div></div>', unsafe_allow_html=True)

    st.markdown('## AI Training Recommendation')
    if log.empty:
        st.info('Not enough workout history yet. Complete more sets for progression recommendations.')
    else:
        recs = []
        ai_df = log.copy()
        for c in ['weight_lbs', 'reps', 'rpe', 'volume']:
            if c in ai_df.columns:
                ai_df[c] = pd.to_numeric(ai_df[c], errors='coerce').fillna(0)
            else:
                ai_df[c] = 0
        ai_df['exercise'] = ai_df.get('exercise', pd.Series(dtype=str)).astype(str)
        recent = ai_df.tail(120)

        for ex, ex_df in recent.groupby('exercise'):
            if not str(ex).strip() or ex_df.empty:
                continue
            last3 = ex_df.tail(3)
            avg_reps = float(last3['reps'].mean())
            avg_rpe = float(last3['rpe'].mean())
            max_w = float(last3['weight_lbs'].max())
            min_reps = float(last3['reps'].min())

            if avg_reps >= 10 and avg_rpe <= 7.5:
                increment = 5.0 if max_w >= 80 else 2.5
                recs.append(f"{ex}: increase to {max_w + increment:.1f} lbs next session (stable reps + manageable RPE).")
            elif avg_rpe >= 9 or min_reps <= 6:
                recs.append(f"{ex}: reduce load by 5-10% or add recovery day (high RPE / falling reps).")
            else:
                recs.append(f"{ex}: hold weight, target cleaner reps before progression.")

        weekly_volume = float(recent['volume'].tail(40).sum())
        if weekly_volume > 15000:
            recs.append('Recent training volume is high: prioritize recovery and sleep before adding load.')

        if not recs:
            st.info('Not enough stable exercise patterns yet for progression guidance.')
        else:
            st.markdown('<div class="side-card"><div class="side-title">AI Training Recommendation</div>', unsafe_allow_html=True)
            for item in recs[:8]:
                st.markdown(f"- {item}")
            st.caption('Rule-based coaching from workout history. Not medical advice.')
            st.markdown('</div>', unsafe_allow_html=True)


elif page == "Workout Builder":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Workout Builder</div><div class="sub">Add exercises to your weekly plan without editing CSV files.</div></div>', unsafe_allow_html=True)
    st.info("Use this page to add a new exercise to the weekly schedule. It updates data/workouts.csv.")
    library = workouts.copy()
    readiness_snapshot = build_muscle_readiness_snapshot(
        workout_log_df=load_log(),
        recovery_df=read_csv_safe(RECOVERY, RECOVERY_COLUMNS),
        body_df=read_csv_safe(BODY, BODY_COLUMNS),
    )

    muscle_readiness = {
        str(item.get('muscle', '')): item
        for item in (readiness_snapshot.get('rows').to_dict('records') if readiness_snapshot.get('rows') is not None and not readiness_snapshot.get('rows').empty else [])
    }

    def _group_status(group_name: str) -> str:
        text = str(group_name or '').lower().replace('+', ' ')
        statuses = []
        for token in text.split():
            canonical = normalize_muscle_name(token)
            if canonical and canonical in muscle_readiness:
                statuses.append(str(muscle_readiness[canonical].get('status', 'Yellow')))
        if 'Red' in statuses:
            return 'Red'
        if 'Orange' in statuses:
            return 'Orange'
        if 'Yellow' in statuses:
            return 'Yellow'
        if 'Green' in statuses:
            return 'Green'
        return 'Yellow'

    st.markdown('### Muscle Readiness Recommendations')
    top_ready_builder = readiness_snapshot.get('top_ready', []) or []
    top_fatigued_builder = readiness_snapshot.get('top_fatigued', []) or []
    st.markdown(
        f'<div class="side-card"><div class="side-title">Workout Builder Readiness</div>'
        f'<div class="small"><b>Prefer:</b> {", ".join([m["muscle"].title() for m in top_ready_builder[:3]]) or "No clear green muscles yet"}</div>'
        f'<div class="small" style="margin-top:8px;"><b>Avoid (Red):</b> {", ".join([m["muscle"].title() for m in top_fatigued_builder if m.get("status") == "Red"]) or "None"}</div>'
        f'<div class="small" style="margin-top:8px;"><b>Recommended Workout:</b> {readiness_snapshot.get("recommended_workout", "Moderate full-body technique session")}</div></div>',
        unsafe_allow_html=True,
    )

    search = st.text_input("Search current exercise library", placeholder="lat pulldown, chest press, row...")
    if search:
        shown = library[library['exercise'].astype(str).str.contains(search, case=False, na=False)]
    else:
        shown = library

    if not shown.empty:
        shown = shown.copy()
        shown['readiness_status'] = shown['muscle_group'].apply(_group_status)
        shown['readiness_hint'] = shown['readiness_status'].map({
            'Green': 'Preferred',
            'Yellow': 'Moderate',
            'Orange': 'Use Caution',
            'Red': 'Avoid Today',
        }).fillna('Moderate')

        # Do not remove rows automatically; only sort to prefer Green and push Red lower.
        shown['readiness_rank'] = shown['readiness_status'].map({'Green': 0, 'Yellow': 1, 'Orange': 2, 'Red': 3}).fillna(1)
        shown = shown.sort_values(['readiness_rank', 'day', 'exercise']).drop(columns=['readiness_rank'])
    st.markdown("### Current Plan Table")
    st.dataframe(shown[['day','muscle_group','exercise','readiness_hint','target_sets','target_reps','base_weight','image_file']], use_container_width=True)

    st.markdown("### Add Exercise to Plan")
    c1,c2,c3 = st.columns(3)
    with c1:
        new_day = st.selectbox("Workout Day", days, key="builder_day")
        new_group = st.text_input("Muscle Group", value="Custom")
    with c2:
        new_ex = st.text_input("Exercise Name", placeholder="Example: Cable Curl")
        new_img = st.text_input("Image file", placeholder="example: bicep_curl.png")
    with c3:
        new_sets = st.number_input("Target sets", min_value=1, max_value=10, value=3, step=1)
        new_reps = st.text_input("Target reps", value="10-12")
        new_weight = st.number_input("Starting weight", min_value=0.0, value=0.0, step=5.0)
    if st.button("➕ Add exercise to workouts.csv"):
        if not new_ex.strip():
            st.error("Enter an exercise name first.")
        else:
            df = load_workouts()
            row = {
                'day': new_day,
                'muscle_group': new_group.strip() or 'Custom',
                'exercise': new_ex.strip(),
                'target_sets': int(new_sets),
                'target_reps': new_reps.strip() or '10-12',
                'base_weight': float(new_weight),
                'image_file': new_img.strip()
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_csv(WORKOUTS, index=False)
            st.success(f"Added {new_ex} to {new_day}. Reopen the page or refresh to see it in the workout.")

    st.markdown("### Image Filename Helper")
    st.caption("Use lowercase filenames with underscores. Example: Shoulder Press Machine → shoulder_press_machine.png")
    if new_ex.strip():
        suggested = ''.join(ch.lower() if ch.isalnum() else '_' for ch in new_ex.strip()).strip('_')
        while '__' in suggested: suggested = suggested.replace('__','_')
        st.code(f"{suggested}.png")

elif page == "Weekly Plan":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Weekly Plan</div><div class="sub">Days, muscle groups, and exercise count</div></div>', unsafe_allow_html=True)
    for day in days:
        d=workouts[workouts.day==day]
        group=d.muscle_group.iloc[0] if not d.empty else 'Rest'
        names = ', '.join(d['exercise'].astype(str).head(6).tolist()) if not d.empty else 'Recovery / Rest day'
        if len(d) > 6: names += ', ...'
        st.markdown(f'<div class="side-card"><div class="side-title">{day} — {group}</div><div class="small">{len(d)} exercises</div><div style="margin-top:8px;color:#c8ddff">{names}</div></div>', unsafe_allow_html=True)


elif page == "System Check":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">System Check + Backup</div><div class="sub">Daily-use stability tools: validate workouts, images, files, and backups.</div></div>', unsafe_allow_html=True)
    issues=[]
    st.markdown("## Required Files")
    required_files=[WORKOUTS, LOG, MAP, NUTRITION, BODY, SUPPLEMENTS]
    for f in required_files:
        ok=f.exists()
        st.markdown(f"{'✅' if ok else '❌'} `{f.relative_to(APP_DIR)}`")
        if not ok: issues.append(f"Missing {f.relative_to(APP_DIR)}")
    st.markdown("## Workout Database Validator")
    df=load_workouts()
    if df.empty:
        st.error("No workout exercises found.")
        issues.append("No workout exercises found")
    else:
        # wrong muscle/day checks
        bad_wed=df[(df['day'].astype(str).str.lower()=='wednesday') & (df['exercise'].astype(str).str.lower().str.contains('calf', na=False))]
        if not bad_wed.empty:
            st.error("Standing/calf exercise still found on Wednesday.")
            issues.append("Calf exercise on Wednesday")
        else:
            st.success("Wednesday workout split is clean: no calf exercises found.")
        dup=df[df.duplicated(subset=['day','exercise'], keep=False)]
        if not dup.empty:
            st.warning(f"Duplicate day/exercise rows found: {len(dup)}")
            issues.append("Duplicate exercises")
        else:
            st.success("No duplicate day/exercise rows.")
        st.dataframe(df[['day','muscle_group','exercise','target_sets','target_reps','image_file']], use_container_width=True)
    st.markdown("## Image Validator")
    image_files=list(ASSETS.glob('*.png'))+list(ASSETS.glob('*.jpg'))+list(ASSETS.glob('*.jpeg'))
    st.write(f"Images installed: **{len(image_files)}**")
    missing=[]
    if not df.empty:
        for _,r in df.iterrows():
            img=str(r.get('image_file','')).strip()
            if img and not (ASSETS/img).exists():
                missing.append((r.get('exercise',''), img))
    if missing:
        st.warning(f"Missing mapped images: {len(missing)}")
        st.dataframe(pd.DataFrame(missing, columns=['exercise','image_file']), use_container_width=True)
        issues.append("Missing mapped images")
    else:
        st.success("All mapped workout images found.")
    st.markdown("## Backup / Export")
    bc1,bc2,bc3=st.columns(3)
    if LOG.exists():
        bc1.download_button("Export workout_log.csv", LOG.read_bytes(), file_name="workout_log.csv")
    if WORKOUTS.exists():
        bc2.download_button("Export workouts.csv", WORKOUTS.read_bytes(), file_name="workouts.csv")
    if MAP.exists():
        bc3.download_button("Export exercise_image_map.csv", MAP.read_bytes(), file_name="exercise_image_map.csv")
    if not issues:
        st.success("System status: ready for daily use.")
    else:
        st.error("System status: review issues above before adding more features.")


elif page == "Nutrition":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Nutrition Engine</div><div class="sub">Track calories, protein, macros, water, and meals.</div></div>', unsafe_allow_html=True)
    cols = ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes']
    nut = read_csv_safe(NUTRITION, cols)
    today_s = str(date.today())
    left, right = st.columns([1.15,.85])
    with left:
        st.markdown('### Add meal / nutrition entry')
        c1,c2,c3 = st.columns(3)
        entry_date = c1.text_input('Date', value=today_s, key='nut_date')
        meal = c2.selectbox('Meal', ['Breakfast','Lunch','Dinner','Snack','Post-workout','Other'], key='meal')
        calories = c3.number_input('Calories', min_value=0, value=0, step=50, key='cal')
        c4,c5,c6,c7 = st.columns(4)
        protein = c4.number_input('Protein g', min_value=0, value=0, step=5, key='protein')
        carbs = c5.number_input('Carbs g', min_value=0, value=0, step=5, key='carbs')
        fat = c6.number_input('Fat g', min_value=0, value=0, step=5, key='fat')
        water = c7.number_input('Water oz', min_value=0, value=0, step=8, key='water')
        notes = st.text_input('Notes', placeholder='Chicken, rice, protein shake, etc.', key='nut_notes')
        if st.button('💾 Save nutrition entry'):
            append_csv(NUTRITION, {'date':entry_date,'meal':meal,'calories':calories,'protein_g':protein,'carbs_g':carbs,'fat_g':fat,'water_oz':water,'notes':notes}, cols)
            st.success('Nutrition entry saved.')
    with right:
        today_df = nut[nut['date'].astype(str)==today_s] if not nut.empty else nut
        cal = int(pd.to_numeric(today_df.get('calories', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_df.empty else 0
        pro = int(pd.to_numeric(today_df.get('protein_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_df.empty else 0
        carb = int(pd.to_numeric(today_df.get('carbs_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_df.empty else 0
        fatg = int(pd.to_numeric(today_df.get('fat_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_df.empty else 0
        wat = int(pd.to_numeric(today_df.get('water_oz', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_df.empty else 0
        st.markdown('<div class="side-card"><div class="side-title">Today\'s Nutrition</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{cal:,} calories</div><div class="small">Protein: <b>{pro}g</b> • Carbs: <b>{carb}g</b> • Fat: <b>{fatg}g</b></div><br><div class="metric-label">Water</div><div class="goalbar"><div class="goalfill" style="width:{min(100, wat)}%"></div></div><div class="small">{wat} / 100 oz</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="side-card"><div class="side-title">Simple Goals</div><div class="small">Protein: 150g/day<br>Water: 100 oz/day<br>Calories: set based on goal weight</div></div>', unsafe_allow_html=True)
    st.markdown('### Nutrition History')
    if nut.empty: st.info('No nutrition entries saved yet.')
    else: st.dataframe(nut.tail(100), use_container_width=True)
    if NUTRITION.exists(): st.download_button('Export nutrition_log.csv', NUTRITION.read_bytes(), file_name='nutrition_log.csv')

elif page == "Supplements":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Supplement Engine</div><div class="sub">Track supplement consistency, timing, and weekly completion. Not medical advice.</div></div>', unsafe_allow_html=True)
    cols=['date','creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes','notes']
    plan_cols=['supplement','category','default_time','target_days_per_week','notes']
    sup=read_csv_safe(SUPPLEMENTS, cols)
    plan=read_csv_safe(SUPPLEMENT_PLAN, plan_cols)
    if plan.empty:
        default_plan = pd.DataFrame([
            {'supplement':'Creatine','category':'Performance','default_time':'Anytime','target_days_per_week':7,'notes':'Common daily consistency supplement.'},
            {'supplement':'Protein Powder','category':'Protein','default_time':'Post workout / meal gap','target_days_per_week':5,'notes':'Use when food protein is low.'},
            {'supplement':'Multivitamin','category':'General','default_time':'Morning with meal','target_days_per_week':7,'notes':'Optional daily check.'},
            {'supplement':'Fish Oil','category':'General','default_time':'With meal','target_days_per_week':7,'notes':'Optional daily check.'},
            {'supplement':'Pre-workout','category':'Workout','default_time':'Before workout','target_days_per_week':3,'notes':'Only when needed; track timing.'},
            {'supplement':'Magnesium','category':'Recovery','default_time':'Evening','target_days_per_week':7,'notes':'Optional recovery/sleep habit.'},
            {'supplement':'Vitamin D','category':'General','default_time':'Morning with meal','target_days_per_week':7,'notes':'Optional daily check.'},
            {'supplement':'Electrolytes','category':'Hydration','default_time':'Training / sauna','target_days_per_week':4,'notes':'Useful for sweating days.'},
        ])
        default_plan.to_csv(SUPPLEMENT_PLAN, index=False)
        plan=default_plan

    today_s=str(date.today())
    today_sup = sup[sup['date'].astype(str)==today_s] if not sup.empty else pd.DataFrame(columns=cols)
    completed_today=0
    if not today_sup.empty:
        last=today_sup.iloc[-1]
        for field in cols[1:-1]:
            if str(last.get(field,'')).lower() in ['true','1','yes']:
                completed_today += 1
    c1,c2,c3=st.columns(3)
    c1.markdown(f'<div class="metric-card"><div class="metric-label">Today Completed</div><div class="metric-value">{completed_today}/8</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-label">Plan Items</div><div class="metric-value">{len(plan)}</div></div>', unsafe_allow_html=True)
    streak_days = sup['date'].nunique() if not sup.empty else 0
    c3.markdown(f'<div class="metric-card"><div class="metric-label">Days Logged</div><div class="metric-value">{streak_days}</div></div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(['Daily Checklist','Supplement Plan','History & Export'])
    with tab1:
        entry_date=st.text_input('Date', value=today_s, key='sup_date')
        st.markdown('### Today\'s Supplements')
        a,b,c,d=st.columns(4)
        creatine=a.checkbox('Creatine')
        protein=b.checkbox('Protein Powder')
        multi=c.checkbox('Multivitamin')
        fish=d.checkbox('Fish Oil')
        e,f,g,h=st.columns(4)
        pre=e.checkbox('Pre-workout')
        magnesium=f.checkbox('Magnesium')
        vitamin_d=g.checkbox('Vitamin D')
        electrolytes=h.checkbox('Electrolytes')
        notes=st.text_input('Supplement notes', placeholder='Example: took creatine post workout; no pre-workout today')
        if st.button('💾 Save supplement day'):
            append_csv(SUPPLEMENTS, {'date':entry_date,'creatine':creatine,'protein_powder':protein,'multivitamin':multi,'fish_oil':fish,'pre_workout':pre,'magnesium':magnesium,'vitamin_d':vitamin_d,'electrolytes':electrolytes,'notes':notes}, cols)
            st.success('Supplement day saved.')
    with tab2:
        st.markdown('### Supplement Plan')
        for _, r in plan.iterrows():
            cat = str(r.get('category','General'))
            css_cat = {
                'Performance':'supp-performance', 'Protein':'supp-protein', 'Recovery':'supp-recovery',
                'General':'supp-general', 'Workout':'supp-workout', 'Hydration':'supp-hydration'
            }.get(cat, 'supp-general')
            st.markdown(f'''<div class="supp-bright-card {css_cat}">
                <div class="supp-title">💊 {r.get('supplement','Supplement')}</div>
                <div class="supp-meta">{cat} • {r.get('default_time','Anytime')} • Goal: {r.get('target_days_per_week','')} days/week</div>
                <span class="supp-pill">{r.get('notes','')}</span>
            </div>''', unsafe_allow_html=True)
        with st.expander('View raw supplement plan table'):
            st.dataframe(plan, use_container_width=True)
        with st.expander('Add supplement to plan'):
            sname=st.text_input('Supplement name')
            cat=st.selectbox('Category', ['Performance','Protein','General','Workout','Recovery','Hydration','Other'])
            timing=st.text_input('Default time', value='Morning / Workout / Evening')
            target=st.number_input('Target days per week', min_value=0, max_value=7, value=7)
            pnotes=st.text_input('Plan notes')
            if st.button('Add to supplement plan') and sname.strip():
                plan = pd.concat([plan, pd.DataFrame([{'supplement':sname,'category':cat,'default_time':timing,'target_days_per_week':target,'notes':pnotes}])], ignore_index=True)
                plan.to_csv(SUPPLEMENT_PLAN, index=False)
                st.success('Supplement added to plan. Refresh page to see updated list.')
    with tab3:
        if sup.empty:
            st.info('No supplement entries yet.')
        else:
            st.dataframe(sup.tail(90), use_container_width=True)
            # Weekly consistency summary
            calc=sup.copy()
            for field in cols[1:-1]:
                calc[field]=calc[field].astype(str).str.lower().isin(['true','1','yes']).astype(int)
            totals=calc[cols[1:-1]].sum().sort_values(ascending=False).reset_index()
            totals.columns=['supplement','times_taken']
            st.markdown('### Consistency Summary')
            st.dataframe(totals, use_container_width=True)
            st.download_button('Export supplement_log.csv', SUPPLEMENTS.read_bytes(), file_name='supplement_log.csv')

elif page == "Body Stats":
    render_body_stats_page()

elif page == "Smart Scale":
    # Ensure Smart Scale route uses current page module code each rerun.
    import importlib
    import pages.smart_scale_import as smart_scale_page

    importlib.reload(smart_scale_page)
    smart_scale_page.render_smart_scale_import_page(BODY)

elif page == "Recovery Center":
    render_recovery_center(
        recovery_path=RECOVERY,
        nutrition_path=NUTRITION,
        body_path=BODY,
        workout_log_path=LOG,
    )


elif page == "Progress Analytics":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Progress Engine</div><div class="sub">Personal records, volume trends, body stats, nutrition, and consistency analytics.</div></div>', unsafe_allow_html=True)
    log = load_log()
    nut = read_csv_safe(NUTRITION, ['date','meal','calories','protein_g','carbs_g','fat_g','water_oz','notes'])
    body = read_csv_safe(BODY, ['date','body_weight_lbs','goal_weight_lbs','waist_in','notes'])
    sup = read_csv_safe(SUPPLEMENTS, ['date','creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes','notes'])

    # Normalize numeric fields safely
    if not log.empty:
        for col in ['weight_lbs','reps','volume','rpe','pain','pain_score','body_feedback_score']:
            if col in log.columns:
                log[col] = pd.to_numeric(log[col], errors='coerce').fillna(0)
        log['date'] = log['date'].astype(str)
    if not nut.empty:
        for col in ['calories','protein_g','carbs_g','fat_g','water_oz']:
            if col in nut.columns:
                nut[col] = pd.to_numeric(nut[col], errors='coerce').fillna(0)
        nut['date'] = nut['date'].astype(str)
    if not body.empty:
        for col in ['body_weight_lbs','goal_weight_lbs','waist_in']:
            if col in body.columns:
                body[col] = pd.to_numeric(body[col], errors='coerce')
        body['date'] = body['date'].astype(str)

    total_sessions = log['date'].nunique() if not log.empty and 'date' in log.columns else 0
    total_volume = int(log['volume'].sum()) if not log.empty and 'volume' in log.columns else 0
    avg_rpe = float(log['rpe'].mean()) if not log.empty and 'rpe' in log.columns else 0
    body_feedback_series = resolve_body_feedback_score(log)
    avg_body_feedback = float(body_feedback_series.mean()) if not body_feedback_series.empty else 0.0
    pr_count = log.groupby('exercise')['weight_lbs'].max().shape[0] if not log.empty and 'exercise' in log.columns else 0
    comeback_score = min(100, int((total_sessions * 5) + (min(total_volume, 50000) / 1000) + (pr_count * 2) - (avg_body_feedback * 3))) if total_sessions else 0
    pr_summary = build_pr_summary(log)
    workout_grade = compute_workout_grade(log)
    perf_scores = performance_scores(log)

    progress_cards = [
        ('Comeback Score', f'{comeback_score}/100', None),
        ('Workout Sessions', f'{total_sessions}', None),
        ('Total Volume', f'{total_volume:,} lbs', None),
        ('Avg Body Check-In', f'{avg_body_feedback:.1f}/10', None),
        ('Workout Grade', str(workout_grade.label), f'{workout_grade.overall_score:.1f}/100'),
        ('Strength Score', f'{perf_scores["strength_score"]:.1f}', None),
    ]

    for row_cards in [progress_cards[:3], progress_cards[3:]]:
        cols = st.columns(3)
        for col, (label, value, subvalue) in zip(cols, row_cards):
            if subvalue is None:
                col.markdown(
                    f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                col.markdown(
                    f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value-wrap">{value}</div><div class="metric-subvalue">{subvalue}</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        f"""
        <div class="side-card" style="margin-top:10px;">
          <div class="side-title">Workout Grade Engine</div>
          <div class="small"><b>Date:</b> {workout_grade.date}</div>
          <div class="small" style="margin-top:6px;"><b>Volume:</b> {workout_grade.volume_score} • <b>Intensity:</b> {workout_grade.intensity_score}</div>
          <div class="small"><b>Consistency:</b> {workout_grade.consistency_score} • <b>Completion:</b> {workout_grade.completion_score}</div>
          <div class="small" style="margin-top:6px;"><b>Overall:</b> {workout_grade.overall_score} / 100 ({workout_grade.label})</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(['Strength', 'Body', 'Nutrition', 'Supplements'])
    with tab1:
        if log.empty:
            st.info('No workout history yet. Save workouts to unlock strength analytics.')
        else:
            st.markdown('### Weekly Workout Volume')
            daily = log.groupby('date', as_index=False)['volume'].sum().sort_values('date')
            st.markdown('<div class="chart-shell">', unsafe_allow_html=True)
            st.line_chart(daily.set_index('date')['volume'])
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('### Workout Frequency')
            freq = log.groupby('date', as_index=False).size()
            freq.columns = ['date', 'sessions']
            st.markdown('<div class="chart-shell">', unsafe_allow_html=True)
            st.bar_chart(freq.set_index('date')['sessions'])
            st.markdown('</div>', unsafe_allow_html=True)

            if 'exercise' in log.columns:
                st.markdown('### Exercise Strength Trend')
                top_ex = (
                    log.groupby('exercise', as_index=False)['volume']
                    .sum()
                    .sort_values('volume', ascending=False)
                    .head(1)
                )
                if not top_ex.empty:
                    ex_name = str(top_ex.iloc[0]['exercise'])
                    ex_df = log[log['exercise'].astype(str) == ex_name].copy()
                    ex_df['estimated_1rm'] = pd.to_numeric(ex_df['weight_lbs'], errors='coerce').fillna(0) * (
                        1 + (pd.to_numeric(ex_df['reps'], errors='coerce').fillna(0) / 30.0)
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"Top exercise: {ex_name}")
                        st.markdown('<div class="chart-shell">', unsafe_allow_html=True)
                        st.line_chart(ex_df.groupby('date', as_index=False)['weight_lbs'].max().set_index('date')['weight_lbs'])
                        st.markdown('</div>', unsafe_allow_html=True)
                    with c2:
                        st.markdown('Estimated 1RM Trend')
                        st.markdown('<div class="chart-shell">', unsafe_allow_html=True)
                        st.line_chart(ex_df.groupby('date', as_index=False)['estimated_1rm'].max().set_index('date')['estimated_1rm'])
                        st.markdown('</div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('### Personal Records')
                st.dataframe(pr_summary.get('rows', pd.DataFrame()), use_container_width=True)
            with c2:
                st.markdown('### Top Exercises by Volume')
                top = log.groupby('exercise', as_index=False)['volume'].sum().sort_values('volume', ascending=False).head(15)
                st.bar_chart(top.set_index('exercise')['volume'])

            if 'day' in log.columns:
                st.markdown('### Muscle-Group Volume')
                group_vol = log.groupby('day', as_index=False)['volume'].sum().sort_values('volume', ascending=False)
                st.markdown('<div class="chart-shell">', unsafe_allow_html=True)
                st.bar_chart(group_vol.set_index('day')['volume'])
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('### Coach Notes')
            st.markdown('<div class="side-card"><div class="side-title">Smart Progress Read</div><div class="small">If you complete all target reps with body feedback under 3/10 and RPE under 8, increase next week by 5 lb for upper-body machines or 2.5 lb for cable movements.</div></div>', unsafe_allow_html=True)
    with tab2:
        if body.empty:
            st.info('No body stats yet. Use Body Stats page to start tracking weight and waist.')
        else:
            st.markdown('### Body Weight Trend')
            bw = body.dropna(subset=['body_weight_lbs']).sort_values('date')
            if not bw.empty:
                st.line_chart(bw.set_index('date')['body_weight_lbs'])
            st.markdown('### Body Stats Table')
            st.dataframe(body.tail(100), use_container_width=True)
    with tab3:
        if nut.empty:
            st.info('No nutrition entries yet. Use Nutrition page to start tracking calories and protein.')
        else:
            st.markdown('### Daily Nutrition Totals')
            daily_nut = nut.groupby('date', as_index=False).agg(calories=('calories','sum'), protein_g=('protein_g','sum'), water_oz=('water_oz','sum')).sort_values('date')
            c1,c2 = st.columns(2)
            with c1:
                st.line_chart(daily_nut.set_index('date')['protein_g'])
                st.caption('Protein grams per day')
            with c2:
                st.line_chart(daily_nut.set_index('date')['calories'])
                st.caption('Calories per day')
            st.dataframe(daily_nut.tail(30), use_container_width=True)
    with tab4:
        if sup.empty:
            st.info('No supplement entries yet. Use Supplements page to start tracking consistency.')
        else:
            calc=sup.copy()
            fields=['creatine','protein_powder','multivitamin','fish_oil','pre_workout','magnesium','vitamin_d','electrolytes']
            for field in fields:
                if field in calc.columns:
                    calc[field]=calc[field].astype(str).str.lower().isin(['true','1','yes']).astype(int)
            totals=calc[[f for f in fields if f in calc.columns]].sum().sort_values(ascending=False).reset_index()
            totals.columns=['supplement','times_taken']
            st.markdown('### Supplement Consistency')
            st.bar_chart(totals.set_index('supplement')['times_taken'])
            st.dataframe(totals, use_container_width=True)

elif page == "Exercise Library":
    # Ensure Exercise Library route always uses latest page/component code on rerun.
    import importlib
    import pages.exercise_library as exercise_library_page

    importlib.reload(exercise_library_page)
    exercise_library_page.render_exercise_library_page(ASSETS)

elif page == "History":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Workout History</div><div class="sub">Saved completed sets</div></div>', unsafe_allow_html=True)
    log, source, cloud_error = load_log(return_meta=True)
    if source == 'cloud':
        st.caption('Source: Supabase Cloud')
    else:
        st.caption('Source: Local CSV Backup')
    if source == 'csv_fallback' and cloud_error:
        st.warning('Cloud unavailable')
    if source == 'csv_fallback_empty_cloud':
        st.info('Supabase returned no rows. Showing local CSV backup.')
    if log.empty:
        st.info('No workouts saved yet.')
    else:
        display_log = log.copy()
        display_log['body_feedback_score'] = resolve_body_feedback_score(display_log)
        display_log['body_feedback_notes'] = resolve_body_feedback_notes(display_log)
        sessions = group_sessions(display_log)
        for _, s in sessions.iterrows():
            sid = str(s.get('session_key', ''))
            session_rows = display_log.copy()
            if 'workout_session_id' in session_rows.columns and sid:
                session_rows = session_rows[session_rows['workout_session_id'].astype(str).str.strip() == sid]
                if session_rows.empty:
                    session_rows = display_log[(display_log['date'].astype(str) + '|' + display_log['day'].astype(str)) == sid]
            st.markdown('<div class="history-session-card">', unsafe_allow_html=True)
            h1, h2, h3, h4 = st.columns(4)
            h1.metric('Date', str(s.get('date', '')))
            h2.metric('Focus', str(s.get('focus', '')))
            h3.metric('Exercises', str(int(s.get('exercises', 0))))
            h4.metric('Sets', str(int(s.get('sets', 0))))
            h5, h6, h7 = st.columns(3)
            h5.metric('Total Volume', f"{int(float(s.get('total_volume', 0) or 0)):,} lbs")
            h6.metric('Average RPE', f"{float(s.get('avg_rpe', 0) or 0):.1f}")
            h7.metric('PR Count', str(int(s.get('pr_count', 0))))
            with st.expander(f"Open session {sid[:36]}"):
                preferred_cols = [
                    'date','day','exercise','set_number','weight_lbs','reps','rpe','body_feedback_score','body_feedback_notes','volume','workout_session_id'
                ]
                cols = [c for c in preferred_cols if c in session_rows.columns]
                st.dataframe(session_rows[cols], use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.expander('Raw data view'):
            preferred_cols = [
                'date','day','exercise','set_number','weight_lbs','reps','rpe','body_feedback_score','body_feedback_notes','volume','workout_session_id'
            ]
            cols = [c for c in preferred_cols if c in display_log.columns]
            st.dataframe(display_log.tail(400)[cols], use_container_width=True)

elif page == "Data Manager":
    st.markdown('<div class="hero"><div class="kicker">Brian Fitness Tracker X</div><div class="title">Data Manager</div><div class="sub">Important files before updates</div></div>', unsafe_allow_html=True)
    st.code('data/workout_log.csv\ndata/workouts.csv\ndata/exercise_image_map.csv\ndata/nutrition_log.csv\ndata/body_stats.csv\ndata/supplement_log.csv\ndata/supplement_plan.csv\nassets/exercises/')

    body_df = read_csv_safe(BODY, BODY_COLUMNS)
    if not body_df.empty and 'date' in body_df.columns and 'import_source' in body_df.columns:
        body_df = body_df.copy()
        body_df['date'] = pd.to_datetime(body_df['date'], errors='coerce')
        body_df = body_df.dropna(subset=['date'])
        if not body_df.empty:
            src_norm = body_df['import_source'].astype(str).str.strip().str.upper()
            scale_rows = body_df[src_norm.isin(['RENPHO', 'CSV IMPORT'])]
            manual_rows = body_df[src_norm.eq('MANUAL')]
            if not scale_rows.empty and not manual_rows.empty:
                latest_scale = scale_rows['date'].max()
                latest_manual = manual_rows['date'].max()
                if latest_manual > latest_scale:
                    st.warning(
                        f"Data warning: manual rows are newer ({latest_manual.strftime('%Y-%m-%d')}) than latest smart-scale rows ({latest_scale.strftime('%Y-%m-%d')}). Dashboard latest weight may prefer smart-scale data when available."
                    )

    st.markdown('### Cloud Database')
    cloud_health = health_check()
    cloud_rows = int(cloud_health.get('workout_count', 0) or 0)
    status_label = 'Connected' if cloud_health.get('connected') else 'Disconnected'
    database_health = str(cloud_health.get('status', 'unavailable'))
    health_message = str(cloud_health.get('message', ''))
    cloud_rows_export, cloud_error = get_workouts() if cloud_health.get('connected') else ([], 'not_connected')
    normalized_cloud = normalize_cloud_workouts(cloud_rows_export) if cloud_health.get('connected') and not cloud_error else pd.DataFrame()
    if not normalized_cloud.empty and 'workout_session_id' in normalized_cloud.columns:
        sid_series = normalized_cloud['workout_session_id'].astype(str).str.strip()
        supabase_session_count = int(sid_series[sid_series.ne('')].nunique())
    else:
        supabase_session_count = 0 if normalized_cloud.empty else int(normalized_cloud[['date', 'day']].drop_duplicates().shape[0])

    if cloud_health.get('connected'):
        st.success('Cloud database is connected and available.')
    else:
        st.warning('Cloud database is disconnected. Local CSV backup remains available.')

    last_sync = st.session_state.get('cloud_sync_status', {})
    last_sync_time = str(last_sync.get('timestamp', 'No sync attempts this session'))
    last_service_result = get_last_save_result()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric('Cloud Status', status_label)
    c2.metric('Supabase Row Count', str(cloud_rows) if cloud_health.get('connected') else 'N/A')
    c3.metric('Supabase Session Count', str(supabase_session_count) if cloud_health.get('connected') else 'N/A')
    c4.metric('Last Sync Time', last_sync_time)
    c5.metric('Database Health', database_health)

    local_csv_rows = len(load_log_local())
    history_df, history_source, _ = load_log(return_meta=True)
    h_source_label = 'Supabase Cloud' if history_source == 'cloud' else 'Local CSV Backup'
    m1, m2 = st.columns(2)
    m1.metric('Local CSV Row Count', str(local_csv_rows))
    m2.metric('History Source', h_source_label)

    last_save_debug = st.session_state.get('last_save_debug', {})
    ls1, ls2, ls3, ls4 = st.columns(4)
    ls1.metric('Last Save Attempted', str(last_save_debug.get('attempted_at', 'Never')))
    ls2.metric('Last Save Status', str(last_save_debug.get('status', 'unknown')))
    ls3.metric('Last Save Error', str(last_save_debug.get('error', '')) or 'None')
    ls4.metric('Last Saved Exercise', str(last_save_debug.get('last_saved_exercise', 'None')))

    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric('Last Save Source', str(last_save_debug.get('last_save_source', 'unknown')))
    d2.metric('Last Workout Session ID', str(last_save_debug.get('last_workout_session_id', 'None')))
    d3.metric('Sets Attempted', str(last_save_debug.get('sets_attempted', 0)))
    d4.metric('Sets Inserted', str(last_save_debug.get('sets_inserted', 0)))
    d5.metric('Duplicates Skipped', str(last_save_debug.get('duplicates_skipped', 0)))
    d6.metric('Last Successful Sync Time', str(last_save_debug.get('last_successful_sync_time', 'None')))
    session_schema_supported = bool(last_service_result.get('session_id_supported', last_save_debug.get('session_id_supported', False)))
    session_schema_status = 'supported' if session_schema_supported else 'missing'
    st.caption(f"Session ID column support: {session_schema_status}")

    if health_message:
        st.caption(health_message)
    if last_sync:
        st.caption(f"Last sync result: {last_sync.get('message', '')}")

    st.markdown('### Cloud Diagnostics')
    with st.expander('Show Supabase diagnostic details', expanded=False):
        st.write({
            'connected': bool(cloud_health.get('connected')),
            'status': str(cloud_health.get('status', 'unknown')),
            'workout_count': int(cloud_health.get('workout_count', 0) or 0),
            'last_checked': str(cloud_health.get('last_checked', '')),
            'message': str(cloud_health.get('message', '')),
            'error': str(cloud_health.get('error', '')),
        })
        if last_sync:
            st.write({
                'last_sync_ok': bool(last_sync.get('ok')),
                'last_sync_inserted': int(last_sync.get('inserted', 0) or 0),
                'last_sync_time': str(last_sync.get('timestamp', '')),
                'last_sync_message': str(last_sync.get('message', '')),
                'last_sync_error': str(last_sync.get('error', '')),
            })

    if cloud_health.get('connected'):
        if cloud_error:
            st.warning('Cloud unavailable')
        else:
            export_df = normalized_cloud
            st.download_button(
                'Export Workout History',
                export_df.to_csv(index=False).encode('utf-8'),
                file_name='workout_history_cloud.csv',
            )

    if st.button('Verify Latest Workout in Supabase', use_container_width=True):
        if cloud_error:
            st.error('Verification failed: cloud unavailable')
        else:
            last_sid = str(last_save_debug.get('last_workout_session_id', '')).strip()
            latest_ex = str(last_save_debug.get('last_saved_exercise', '')).strip().lower()
            if normalized_cloud.empty:
                st.warning('No cloud rows found to verify.')
            else:
                matched = normalized_cloud.copy()
                if last_sid and 'workout_session_id' in matched.columns:
                    matched = matched[matched['workout_session_id'].astype(str).str.strip() == last_sid]
                if matched.empty and latest_ex:
                    matched = normalized_cloud[normalized_cloud['exercise'].astype(str).str.strip().str.lower() == latest_ex]
                if matched.empty:
                    st.error('Latest workout not found in Supabase.')
                else:
                    st.success(f"Verified {len(matched)} row(s) in Supabase for the latest workout context.")

    st.markdown('### Schema Migration')
    st.caption('Run this in Supabase SQL Editor to add workout_session_id for duplicate-safe session saves:')
    if cloud_health.get('connected') and not session_schema_supported:
        st.warning('Current Supabase schema is missing workout_session_id. Session-level duplicate prevention is limited until migration is applied.')
    st.code(
        """alter table public.workouts
add column if not exists workout_session_id text;

create unique index if not exists workouts_unique_session_set
on public.workouts (
    workout_session_id,
    exercise,
    set_number
);""",
        language='sql',
    )

    if LOG.exists():
        st.download_button('Export workout_log.csv', LOG.read_bytes(), file_name='workout_log.csv')
    if NUTRITION.exists():
        st.download_button('Export nutrition_log.csv', NUTRITION.read_bytes(), file_name='nutrition_log.csv')
    if BODY.exists():
        st.download_button('Export body_stats.csv', BODY.read_bytes(), file_name='body_stats.csv')
    if SUPPLEMENTS.exists():
        st.download_button('Export supplement_log.csv', SUPPLEMENTS.read_bytes(), file_name='supplement_log.csv')
    if SUPPLEMENT_PLAN.exists():
        st.download_button('Export supplement_plan.csv', SUPPLEMENT_PLAN.read_bytes(), file_name='supplement_plan.csv')
