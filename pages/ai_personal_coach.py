from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from engines.coaching_memory_engine import build_coaching_memory
from engines.performance_intelligence import build_pr_summary, workout_streak_days


def _text(value: Any, default: str = 'Not available') -> str:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    out = str(value).strip()
    if not out or out.lower() == 'nan':
        return default
    return out


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_df(value: Any) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _h_m(hours: Any) -> str:
    h = _num(hours, -1)
    if h < 0:
        return 'Not available'
    mins = int(round(h * 60.0))
    return f'{mins // 60}h {mins % 60:02d}m'


def _latest_pr(log_df: pd.DataFrame) -> str:
    summary = build_pr_summary(log_df)
    rows = summary.get('rows', pd.DataFrame()) if isinstance(summary, dict) else pd.DataFrame()
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return 'Not available'
    top = rows.iloc[0]
    return f"{_text(top.get('exercise'), 'Exercise')} {_num(top.get('heaviest_weight'), 0):.0f} lb"


def _potential_pr(log_df: pd.DataFrame, adaptive_plan: Dict[str, Any]) -> str:
    if log_df.empty or 'exercise' not in log_df.columns:
        return 'Not available'
    df = log_df.copy()
    df['exercise'] = df['exercise'].astype(str).str.strip()
    df['weight_lbs'] = pd.to_numeric(df.get('weight_lbs', 0), errors='coerce').fillna(0)
    focus = _text(adaptive_plan.get('recommended_focus'), '')
    candidates = [item for item in ['Bench', 'Press', 'Row', 'Pulldown', 'Squat', 'Deadlift'] if item.lower() in focus.lower()]
    if not candidates:
        candidates = ['Bench', 'Row', 'Pulldown']
    for token in candidates:
        ex = df[df['exercise'].str.contains(token, case=False, na=False)].copy()
        if len(ex.index) >= 2:
            ex = ex.sort_values('date')
            recent = float(ex['weight_lbs'].tail(6).max())
            prev = float(ex['weight_lbs'].head(max(1, len(ex.index) - 6)).max()) if len(ex.index) > 6 else float(ex['weight_lbs'].iloc[:-1].max())
            delta = recent - prev
            if delta >= 2.5:
                return f"{_text(ex.iloc[-1].get('exercise'), token)} +{delta:.0f} lb"
            if delta > 0:
                return f"{_text(ex.iloc[-1].get('exercise'), token)} +{delta:.1f} lb"
    return 'Not available'


def _weekly_workouts(log_df: pd.DataFrame) -> int:
    if log_df.empty or 'date' not in log_df.columns:
        return 0
    d = pd.to_datetime(log_df['date'], errors='coerce').dropna()
    if d.empty:
        return 0
    cut = pd.Timestamp.now() - pd.Timedelta(days=6)
    return int(d[d >= cut].dt.date.nunique())


def _yesterday_apple(apple_daily_df: pd.DataFrame) -> Dict[str, Any]:
    out = {'calories': None, 'sleep': None, 'steps': None}
    if apple_daily_df.empty or 'activity_date' not in apple_daily_df.columns:
        return out
    df = apple_daily_df.copy()
    df['activity_date'] = pd.to_datetime(df['activity_date'], errors='coerce', utc=True)
    df = df.dropna(subset=['activity_date']).sort_values('activity_date')
    if df.empty:
        return out
    y = (pd.Timestamp.utcnow() - pd.Timedelta(days=1)).date()
    y_rows = df[df['activity_date'].dt.date == y]
    if y_rows.empty:
        y_rows = df.tail(1)
    row = y_rows.iloc[-1]
    out['calories'] = int(_num(row.get('active_energy_kcal'), 0)) if str(row.get('active_energy_kcal', '')).strip() != '' else None
    out['sleep'] = row.get('sleep_hours')
    out['steps'] = int(_num(row.get('steps'), 0)) if str(row.get('steps', '')).strip() != '' else None
    return out


def _yesterday_cardio_summary(cardio_df: pd.DataFrame) -> str:
    if cardio_df.empty or 'activity_date' not in cardio_df.columns:
        return 'Yesterday cardio data was not available.'
    df = cardio_df.copy()
    df['activity_date'] = pd.to_datetime(df['activity_date'], errors='coerce')
    df['duration_minutes'] = pd.to_numeric(df.get('duration_minutes', 0), errors='coerce').fillna(0)
    df['activity_type'] = df.get('activity_type', pd.Series(dtype=str)).astype(str)
    y = (pd.Timestamp.now() - pd.Timedelta(days=1)).date()
    y_rows = df[df['activity_date'].dt.date == y]
    if y_rows.empty:
        return 'No cardio session was logged yesterday.'
    total = int(y_rows['duration_minutes'].sum())
    top = y_rows.groupby('activity_type')['duration_minutes'].sum().sort_values(ascending=False)
    if top.empty:
        return f'Yesterday you completed {total} minutes of cardio.'
    top_name = str(top.index[0])
    return f'Yesterday you played {top_name} for {total} minutes.'


def _coach_conversation(log_df: pd.DataFrame, cardio_df: pd.DataFrame, readiness_result: Dict[str, Any], adaptive_plan: Dict[str, Any]) -> str:
    readiness = int(_num(readiness_result.get('readiness_score'), 0))
    status = _text(readiness_result.get('recovery_status'), 'Unknown')
    focus = _text(adaptive_plan.get('recommended_focus'), 'today\'s plan')
    duration = int(_num(adaptive_plan.get('duration_minutes'), 56))
    potential_pr = _potential_pr(log_df, adaptive_plan)
    lower_reason = []
    upper_reason = []
    for item in (readiness_result.get('limiting_factors', []) or []):
        t = _text(item, '').lower()
        if any(k in t for k in ['leg', 'lower', 'quad', 'hamstring', 'glute', 'calf', 'pickleball']):
            lower_reason.append(_text(item, ''))
    for item in (readiness_result.get('positive_factors', []) or []):
        t = _text(item, '').lower()
        if any(k in t for k in ['upper', 'chest', 'back', 'shoulder', 'arm']):
            upper_reason.append(_text(item, ''))

    lines = [
        'Good morning Brian.',
        _yesterday_cardio_summary(cardio_df),
    ]
    if lower_reason:
        lines.append('Your lower body still needs recovery.')
    if upper_reason:
        lines.append('Your upper body is fully recovered.')
    lines.append(f"Today's recommendation is {focus}.")
    lines.append(f'Estimated workout time is {duration} minutes.')
    if potential_pr != 'Not available':
        lines.append(f'There is a high chance of improving {potential_pr} today.')
    lines.append(f'Recovery is {readiness}/100 ({status}).')
    return '\n\n'.join(lines)


def _focus_block(adaptive_plan: Dict[str, Any], readiness_result: Dict[str, Any]) -> Dict[str, str]:
    category = _text(adaptive_plan.get('recommended_category'), 'Strength').title()
    if category not in {'Strength', 'Cardio', 'Recovery', 'Sport', 'Mixed'}:
        category = 'Mixed'
    color_map = {
        'Strength': '#3B82F6',
        'Cardio': '#06B6D4',
        'Recovery': '#22C55E',
        'Sport': '#F59E0B',
        'Mixed': '#8B5CF6',
    }
    intensity = _text(adaptive_plan.get('intensity_level'), 'Moderate')
    score = int(_num(readiness_result.get('readiness_score'), 0))
    if score >= 85:
        cost = 'Low-Moderate'
    elif score >= 70:
        cost = 'Moderate'
    else:
        cost = 'Moderate-High'
    return {
        'category': category,
        'color': color_map.get(category, '#8B5CF6'),
        'reason': _text(adaptive_plan.get('main_reason'), 'Built from your current recovery, history, and activity context.'),
        'difficulty': intensity,
        'cost': cost,
    }


def _smart_notifications(readiness_result: Dict[str, Any], nutrition_df: pd.DataFrame) -> List[str]:
    notes: List[str] = []
    today = str(date.today())
    today_n = nutrition_df[nutrition_df.get('date', pd.Series(dtype=str)).astype(str) == today] if not nutrition_df.empty and 'date' in nutrition_df.columns else pd.DataFrame()
    protein = int(pd.to_numeric(today_n.get('protein_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_n.empty else 0
    water = int(pd.to_numeric(today_n.get('water_oz', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_n.empty else 0
    sleep_h = _num((readiness_result.get('activity_context', {}) or {}).get('sleep_hours'), 0)
    readiness = int(_num(readiness_result.get('readiness_score'), 0))

    if protein < 120:
        notes.append('Protein reminder: add a 30-40g protein meal this afternoon.')
    if water < 80:
        notes.append('Hydration reminder: drink at least 24 oz in the next hour.')
    if readiness < 70:
        notes.append('Recovery walk: 20 minutes easy pace to improve readiness.')
    if sleep_h and sleep_h < 7:
        notes.append('Sleep reminder: target 7.5-9h tonight for better recovery.')
    if readiness < 60:
        notes.append('Stretch reminder: 10 minutes mobility before training.')
    return notes[:5]


def _action_cards(readiness_result: Dict[str, Any], nutrition_df: pd.DataFrame) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = [
        {'label': 'Start Workout', 'key': 'start_workout'},
        {'label': 'Review Yesterday', 'key': 'review_yesterday'},
    ]
    readiness = int(_num(readiness_result.get('readiness_score'), 0))
    if readiness < 70:
        actions.append({'label': 'Recovery Walk', 'key': 'recovery_walk'})
        actions.append({'label': 'Stretching', 'key': 'stretch'})
    actions.append({'label': 'Log Cardio', 'key': 'log_cardio'})

    today = str(date.today())
    today_n = nutrition_df[nutrition_df.get('date', pd.Series(dtype=str)).astype(str) == today] if not nutrition_df.empty and 'date' in nutrition_df.columns else pd.DataFrame()
    water = int(pd.to_numeric(today_n.get('water_oz', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not today_n.empty else 0
    if water < 80:
        actions.append({'label': 'Hydration', 'key': 'hydration'})
    actions.append({'label': "Today's Nutrition", 'key': 'nutrition'})
    actions.append({'label': 'Sleep', 'key': 'sleep'})
    dedupe = []
    seen = set()
    for item in actions:
        if item['key'] in seen:
            continue
        seen.add(item['key'])
        dedupe.append(item)
    return dedupe[:8]


def _single_insight(log_df: pd.DataFrame, apple_daily_df: pd.DataFrame, cardio_df: pd.DataFrame) -> str:
    insights: List[str] = []
    if not log_df.empty:
        df = log_df.copy()
        df['date'] = pd.to_datetime(df.get('date'), errors='coerce')
        df['volume'] = pd.to_numeric(df.get('volume', 0), errors='coerce').fillna(0)
        month_cut = pd.Timestamp.now() - pd.Timedelta(days=30)
        prev_cut = pd.Timestamp.now() - pd.Timedelta(days=60)
        m_now = float(df[df['date'] >= month_cut]['volume'].sum())
        m_prev = float(df[(df['date'] < month_cut) & (df['date'] >= prev_cut)]['volume'].sum())
        if m_prev > 0:
            delta = ((m_now - m_prev) / m_prev) * 100.0
            insights.append(f'Bench and strength volume trend changed {delta:+.0f}% versus last month.')
    if not cardio_df.empty:
        c = cardio_df.copy()
        c['activity_date'] = pd.to_datetime(c.get('activity_date'), errors='coerce')
        c['activity_type'] = c.get('activity_type', pd.Series(dtype=str)).astype(str)
        month_cut = pd.Timestamp.now() - pd.Timedelta(days=30)
        pkl = int(((c['activity_date'] >= month_cut) & (c['activity_type'].str.lower() == 'pickleball')).sum())
        if pkl > 0:
            insights.append(f'Pickleball sessions increased this month ({pkl} logged).')
    if not apple_daily_df.empty:
        a = apple_daily_df.copy()
        a['activity_date'] = pd.to_datetime(a.get('activity_date'), errors='coerce', utc=True)
        a['sleep_hours'] = pd.to_numeric(a.get('sleep_hours', 0), errors='coerce')
        a = a.dropna(subset=['activity_date'])
        if not a.empty:
            month_cut = pd.Timestamp.utcnow() - pd.Timedelta(days=30)
            prev_cut = pd.Timestamp.utcnow() - pd.Timedelta(days=60)
            s_now = float(a[a['activity_date'] >= month_cut]['sleep_hours'].mean())
            s_prev = float(a[(a['activity_date'] < month_cut) & (a['activity_date'] >= prev_cut)]['sleep_hours'].mean())
            if s_prev > 0 and s_now > 0:
                mins = int((s_now - s_prev) * 60)
                insights.append(f'Average sleep changed by {mins:+d} minutes versus last month.')
    if not insights:
        return 'Consistency is stable. Keep your current routine and log all sessions for sharper insights.'
    idx = date.today().toordinal() % len(insights)
    return insights[idx]


def _quote() -> str:
    quotes = [
        'Small daily wins become long-term performance.',
        'Consistency builds confidence. Confidence builds results.',
        'Train with intent, recover with discipline.',
        'Focus on quality reps and quality recovery.',
    ]
    return quotes[date.today().toordinal() % len(quotes)]


def _coach_reply(question: str, context: Dict[str, Any]) -> str:
    q = question.lower().strip()
    log_df = context.get('log_df', pd.DataFrame())
    readiness_result = context.get('readiness_result', {}) or {}
    adaptive_plan = context.get('adaptive_plan', {}) or {}
    readiness = int(_num(readiness_result.get('readiness_score'), 0))
    focus = _text(adaptive_plan.get('recommended_focus'), 'today\'s planned workout')

    if not isinstance(log_df, pd.DataFrame) or log_df.empty:
        return 'I can answer generally, but I cannot use workout history yet because no prior sets are saved.'

    if 'increase' in q or 'weight' in q:
        return 'Use one-step progression only if your first set stays under RPE 8 with clean form. Otherwise hold load today.'
    if 'skip legs' in q or 'legs' in q:
        if readiness < 75:
            return 'Given today\'s recovery, reduce lower-body loading and prioritize upper body or recovery work.'
        return 'Keep legs, but reduce one set if effort rises too quickly.'
    if 'pickleball' in q:
        return 'After pickleball, keep lower-body volume conservative and control tempo on compound movements.'
    if 'shoulder' in q or 'tight' in q:
        return 'Use pain-free ranges, lower pressing load, and add warm-up sets. If pain rises, switch to safer substitutions.'
    if 'eat' in q or 'nutrition' in q:
        return 'Prioritize protein, hydration, and balanced carbs tonight to support tomorrow\'s readiness.'
    if 'substitute' in q or 'machine' in q or 'swap' in q:
        return 'Swap to the same movement pattern and start conservatively based on your recent logged performance.'
    return f"Today\'s plan is {focus}. Keep execution precise and adjust volume only if recovery signals worsen."


def _persist_structured_memory(observations: List[Dict[str, Any]], storage_path: Path) -> None:
    if not observations:
        return
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in observations:
        rows.append(
            {
                'captured_on': str(date.today()),
                'memory_type': _text(item.get('memory_type'), ''),
                'memory_key': _text(item.get('memory_key'), ''),
                'summary': _text(item.get('summary'), ''),
                'confidence': float(_num(item.get('confidence'), 0)),
            }
        )
    new_df = pd.DataFrame(rows)
    if storage_path.exists():
        old_df = pd.read_csv(storage_path)
        merged = pd.concat([old_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=['memory_type', 'memory_key', 'summary'], keep='last')
        merged.to_csv(storage_path, index=False)
    else:
        new_df.to_csv(storage_path, index=False)


def render_ai_personal_coach(payload: Dict[str, Any]) -> str:
    log_df = _safe_df(payload.get('log_df'))
    cardio_df = _safe_df(payload.get('cardio_df'))
    nutrition_df = _safe_df(payload.get('nutrition_df'))
    feedback_df = _safe_df(payload.get('feedback_df'))
    readiness_result = payload.get('readiness_result', {}) if isinstance(payload.get('readiness_result'), dict) else {}
    adaptive_plan = payload.get('adaptive_plan', {}) if isinstance(payload.get('adaptive_plan'), dict) else {}
    apple_daily_df = _safe_df(payload.get('apple_daily_df'))

    memory = build_coaching_memory(feedback_df, log_df, cardio_df)
    observations = list(memory.get('observations', []) if isinstance(memory, dict) else [])
    storage_path = Path(payload.get('memory_path', Path('data') / 'coach_memory_observations.csv'))
    _persist_structured_memory(observations, storage_path)

    readiness_score = int(_num(readiness_result.get('readiness_score'), 0))
    readiness_label = _text(readiness_result.get('recovery_status'), 'Not available')
    weekly_sessions = _weekly_workouts(log_df)
    y_apple = _yesterday_apple(apple_daily_df)
    latest_pr = _latest_pr(log_df)
    potential_pr = _potential_pr(log_df, adaptive_plan)
    quote = _quote()
    conversation = _coach_conversation(log_df, cardio_df, readiness_result, adaptive_plan)
    focus = _focus_block(adaptive_plan, readiness_result)
    notifications = _smart_notifications(readiness_result, nutrition_df)
    actions = _action_cards(readiness_result, nutrition_df)
    insight = _single_insight(log_df, apple_daily_df, cardio_df)

    streak = workout_streak_days(log_df)
    celebrations: List[str] = []
    if potential_pr != 'Not available':
        celebrations.append(f'PR opportunity: {potential_pr}')
    if streak >= 3:
        celebrations.append(f'Streak: {streak} days')
    if weekly_sessions >= 3:
        celebrations.append('Weekly consistency is on track')

    st.markdown(
        """
        <style>
        .x111-hero{background:linear-gradient(140deg,#071220,#10345d 58%,#0f6a6a);border:1px solid rgba(96,165,250,.48);border-radius:24px;padding:20px;box-shadow:0 20px 54px rgba(0,0,0,.38);}
        .x111-kicker{font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;color:#93c5fd;font-weight:900;}
        .x111-title{font-size:2.35rem;color:#fff;line-height:1.04;font-weight:900;margin-top:8px;}
        .x111-sub{color:#dbeafe;margin-top:8px;}
        .x111-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px;}
        .x111-card{background:rgba(4,13,25,.62);border:1px solid rgba(96,165,250,.34);border-radius:14px;padding:10px;transition:all .18s ease;}
        .x111-card:hover{border-color:rgba(34,197,94,.6);transform:translateY(-1px);}
        .x111-label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#9cc7ff;font-weight:800;}
        .x111-value{font-size:1.05rem;color:#fff;font-weight:900;margin-top:4px;}
        .x111-focus{border-radius:20px;padding:14px;border:1px solid rgba(255,255,255,.2);box-shadow:0 10px 28px rgba(0,0,0,.24);}
        .x111-pill{display:inline-block;padding:7px 10px;border-radius:999px;background:rgba(37,99,235,.18);border:1px solid rgba(96,165,250,.38);font-size:.78rem;font-weight:900;color:#e2e8f0;margin:6px 8px 0 0;animation:subtlePulse 2.4s ease-in-out infinite;}
        .x111-insight{background:#0a1728;border:1px solid rgba(34,197,94,.35);border-radius:16px;padding:12px;}
        .x111-sticky{position:sticky;bottom:calc(env(safe-area-inset-bottom,0px) + 8px);z-index:20;background:rgba(5,12,22,.94);backdrop-filter:blur(8px);border:1px solid rgba(96,165,250,.3);border-radius:16px;padding:10px;margin-top:12px;}
        @keyframes subtlePulse{0%{box-shadow:0 0 0 rgba(34,197,94,0);}50%{box-shadow:0 0 14px rgba(34,197,94,.16);}100%{box-shadow:0 0 0 rgba(34,197,94,0);}}
        @media (max-width: 900px){.x111-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.x111-title{font-size:1.85rem;}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class='x111-hero'>
          <div class='x111-kicker'>Brian Fit X 11.1 • Premium AI Coach Experience</div>
          <div class='x111-title'>GOOD MORNING, BRIAN</div>
          <div class='x111-sub'>{quote}</div>
          <div class='x111-grid'>
            <div class='x111-card'><div class='x111-label'>Today's Mission</div><div class='x111-value'>{_text(adaptive_plan.get('recommended_focus'), 'Not available')}</div></div>
            <div class='x111-card'><div class='x111-label'>Recovery</div><div class='x111-value'>{readiness_score}%</div></div>
            <div class='x111-card'><div class='x111-label'>Workout</div><div class='x111-value'>{_text(adaptive_plan.get('recommended_category'), 'Not available')}</div></div>
            <div class='x111-card'><div class='x111-label'>Estimated Time</div><div class='x111-value'>{int(_num(adaptive_plan.get('duration_minutes'), 56))} minutes</div></div>
            <div class='x111-card'><div class='x111-label'>Weekly Progress</div><div class='x111-value'>{weekly_sessions} of 5 workouts</div></div>
            <div class='x111-card'><div class='x111-label'>Potential PR</div><div class='x111-value'>{potential_pr}</div></div>
            <div class='x111-card'><div class='x111-label'>Calories Yesterday</div><div class='x111-value'>{_text(y_apple.get('calories'), 'Not available')}</div></div>
            <div class='x111-card'><div class='x111-label'>Sleep</div><div class='x111-value'>{_h_m(y_apple.get('sleep'))}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    primary = st.columns(4)
    action = ''
    if primary[0].button("Start Today's Workout", type='primary', width='stretch', key='ai111_start_today'):
        action = 'start_workout'
    if primary[1].button("Preview Today's Plan", width='stretch', key='ai111_preview_today'):
        action = 'preview_workout'
    if primary[2].button('Recovery Instead', width='stretch', key='ai111_recovery_instead'):
        action = 'recovery_plan'
    if primary[3].button('Ask Coach', width='stretch', key='ai111_ask_coach'):
        action = 'ask_coach'

    st.markdown('### AI Coach Conversation')
    st.markdown(f"<div class='x111-card'>{conversation.replace(chr(10), '<br><br>')}</div>", unsafe_allow_html=True)

    st.markdown('### Daily Focus')
    st.markdown(
        f"""
        <div class='x111-focus' style='background:linear-gradient(140deg,{focus['color']}22,#0b1422);border-color:{focus['color']};'>
          <div class='x111-kicker'>Today's Focus</div>
          <div style='font-size:1.7rem;color:#fff;font-weight:900;margin-top:6px;'>{focus['category']}</div>
          <div style='color:#dbeafe;margin-top:8px;'><b>Reason:</b> {focus['reason']}</div>
          <div style='color:#dbeafe;margin-top:6px;'><b>Expected difficulty:</b> {focus['difficulty']}</div>
          <div style='color:#dbeafe;margin-top:6px;'><b>Expected recovery cost:</b> {focus['cost']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('### Quick Actions')
    cols = st.columns(4)
    for idx, item in enumerate(actions):
        with cols[idx % 4]:
            if st.button(item['label'], width='stretch', key=f"ai111_action_{item['key']}"):
                action = item['key']

    st.markdown('### AI Insight')
    st.markdown(f"<div class='x111-insight'>{insight}</div>", unsafe_allow_html=True)

    st.markdown('### Motivation')
    if celebrations:
        for item in celebrations:
            st.markdown(f"<span class='x111-pill'>{item}</span>", unsafe_allow_html=True)
    else:
        st.caption('No milestone alerts yet. Keep consistent and log every session.')

    st.markdown('### Smart Notifications')
    if notifications:
        for note in notifications:
            st.info(note)
    else:
        st.caption('No notifications right now. You are on track.')

    st.markdown('### Coach Chat')
    if 'ai111_chat' not in st.session_state:
        st.session_state['ai111_chat'] = []
    prompts = [
        'Should I increase weight?',
        'Should I skip legs?',
        'I played pickleball yesterday.',
        'My shoulder feels tight.',
        'What should I eat tonight?',
        'Can I substitute this machine?',
    ]
    pick = st.selectbox('Quick prompt', ['Select a prompt'] + prompts, key='ai111_prompt')
    q_default = '' if pick == 'Select a prompt' else pick
    user_q = st.text_input('Ask coach', value=q_default, key='ai111_question')
    if st.button('Send', width='stretch', key='ai111_send') and _text(user_q, ''):
        reply = _coach_reply(
            user_q,
            {
                'log_df': log_df,
                'readiness_result': readiness_result,
                'adaptive_plan': adaptive_plan,
            },
        )
        st.session_state['ai111_chat'].append({'user': user_q, 'coach': reply})
    for msg in st.session_state.get('ai111_chat', [])[-6:]:
        st.markdown(f"You: {_text(msg.get('user'), '')}")
        st.markdown(f"Coach: {_text(msg.get('coach'), '')}")

    st.markdown('### Weekly Review')
    cardio_minutes = int(pd.to_numeric(cardio_df.get('duration_minutes', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not cardio_df.empty else 0
    protein_today = int(pd.to_numeric(nutrition_df.get('protein_g', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not nutrition_df.empty else 0
    coach_grade = 'A' if readiness_score >= 85 and weekly_sessions >= 4 else ('B' if readiness_score >= 70 and weekly_sessions >= 3 else 'C')
    wins = []
    if weekly_sessions >= 3:
        wins.append('Completed planned workout frequency.')
    if cardio_minutes >= 120:
        wins.append('Cardio minutes are on target.')
    if potential_pr != 'Not available':
        wins.append('PR trend is active.')
    while len(wins) < 3:
        wins.append('Logging consistency is improving.')
    focus_area = 'Increase protein consistency and sleep timing.' if protein_today < 130 else 'Continue progression while protecting recovery.'
    with st.expander('Open Weekly Summary', expanded=False):
        st.markdown(f'- Workouts: {weekly_sessions}')
        st.markdown(f'- Strength: {latest_pr}')
        st.markdown(f'- Cardio: {cardio_minutes} minutes')
        st.markdown(f'- Recovery: {readiness_score}% current readiness')
        st.markdown(f'- Nutrition: {protein_today}g protein logged today')
        st.markdown(f'- Coach Grade: {coach_grade}')
        st.markdown('Three Wins:')
        st.markdown(f'- {wins[0]}')
        st.markdown(f'- {wins[1]}')
        st.markdown(f'- {wins[2]}')
        st.markdown(f'One Focus Area: {focus_area}')

    if observations:
        with st.expander('Coach Memory (Structured)', expanded=False):
            for obs in observations[:6]:
                st.caption(f"{_text(obs.get('memory_type'))}: {_text(obs.get('summary'))} (confidence {float(_num(obs.get('confidence'), 0)):.2f})")

    st.markdown('<div class="x111-sticky">', unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    if s1.button('Start Workout', type='primary', width='stretch', key='ai111_sticky_start'):
        action = 'start_workout'
    if s2.button('Preview', width='stretch', key='ai111_sticky_preview'):
        action = 'preview_workout'
    if s3.button('Recovery', width='stretch', key='ai111_sticky_recovery'):
        action = 'recovery_plan'
    if s4.button('Ask Coach', width='stretch', key='ai111_sticky_ask'):
        action = 'ask_coach'
    st.markdown('</div>', unsafe_allow_html=True)

    return action
