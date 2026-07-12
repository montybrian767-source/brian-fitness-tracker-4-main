from __future__ import annotations


VALID_ROUTES = {
    'ai_personal_coach',
    'command_center',
    'dashboard',
    'workout',
    'gym_mode',
    'history_center',
    'progress',
    'apple_activity',
    'recovery_center',
    'recovery_readiness',
    'nutrition_center',
    'health_center',
    'performance_center',
    'exercise_library',
    'body_stats',
    'smart_scale_import',
    'system_center',
    'training_center',
    # Backward-compatible route keys still used across app/session state.
    'history',
}

ROUTE_ALIASES = {
    'app': 'ai_personal_coach',
    'home': 'ai_personal_coach',
    'mission': 'ai_personal_coach',
    'coach': 'ai_personal_coach',
    'ai coach': 'ai_personal_coach',
    'ai personal coach': 'ai_personal_coach',
    'ai personal trainer': 'ai_personal_coach',
    'ai_personal_trainer': 'ai_personal_coach',
    'command center': 'command_center',
    'history': 'history_center',
    'recovery': 'recovery_center',
    'nutrition': 'nutrition_center',
    'health': 'health_center',
    'performance': 'performance_center',
    'apple intelligence': 'apple_activity',
    'todays workout': 'workout',
    "today's workout": 'workout',
    'progress analytics': 'progress',
    'recovery & readiness': 'recovery_readiness',
    'recovery readiness': 'recovery_readiness',
    'system check': 'system_center',
    'history_center': 'history_center',
    'smart_scale': 'smart_scale_import',
}

ROUTE_KEY_TO_PAGE = {
    'ai_personal_coach': 'AI Personal Trainer',
    'command_center': 'Command Center',
    'dashboard': 'Dashboard',
    'workout': "Today's Workout",
    'gym_mode': 'Gym Mode',
    'history_center': 'History',
    'history': 'History',
    'progress': 'Progress Analytics',
    'apple_activity': 'Apple Activity',
    'recovery_center': 'Recovery Center',
    'recovery_readiness': 'Recovery & Readiness',
    'nutrition_center': 'Nutrition',
    'health_center': 'Dashboard',
    'performance_center': 'Progress Analytics',
    'exercise_library': 'Exercise Library',
    'body_stats': 'Body Stats',
    'smart_scale_import': 'Smart Scale',
    'system_center': 'System Center',
    'training_center': 'Weekly Plan',
}

PAGE_TO_ROUTE_KEY = {
    'AI Personal Trainer': 'ai_personal_coach',
    'Command Center': 'command_center',
    'Dashboard': 'dashboard',
    "Today's Workout": 'workout',
    'Gym Mode': 'gym_mode',
    'History': 'history_center',
    'Progress Analytics': 'progress',
    'Apple Activity': 'apple_activity',
    'Recovery Center': 'recovery_center',
    'Recovery & Readiness': 'recovery_readiness',
    'Nutrition': 'nutrition_center',
    'Exercise Library': 'exercise_library',
    'Body Stats': 'body_stats',
    'Smart Scale': 'smart_scale_import',
    'System Center': 'system_center',
    'Weekly Plan': 'training_center',
}


def default_home_route() -> str:
    return 'ai_personal_coach'


def normalize_route(route: str | None, fallback: str | None = None) -> str:
    fallback_key = str(fallback or default_home_route()).strip().lower().replace('-', '_').replace(' ', '_')
    if fallback_key not in VALID_ROUTES:
        fallback_key = default_home_route()

    raw = str(route or '').strip()
    if not raw:
        return fallback_key

    alias_key = raw.lower()
    alias_value = ROUTE_ALIASES.get(alias_key)
    if alias_value:
        return alias_value

    value = alias_key.replace('-', '_').replace(' ', '_')
    if value in VALID_ROUTES:
        return value

    page_key = PAGE_TO_ROUTE_KEY.get(raw)
    if page_key:
        return page_key

    return fallback_key


def page_from_route(route: str | None) -> str:
    key = normalize_route(route)
    return ROUTE_KEY_TO_PAGE.get(key, 'AI Personal Trainer')


def route_from_page(page: str | None) -> str:
    raw = str(page or '').strip()
    mapped = PAGE_TO_ROUTE_KEY.get(raw)
    if mapped:
        return mapped
    return normalize_route(raw)
