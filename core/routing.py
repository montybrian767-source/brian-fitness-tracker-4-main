from __future__ import annotations


VALID_ROUTES = {
    # Mobile MVP routes.
    'home',
    'workout',
    'history',
    'progress',
    'apple_health',
    'profile',
    # Legacy routes kept for backward compatibility / developer mode.
    'ai_personal_coach',
    'command_center',
    'dashboard',
    'gym_mode',
    'history_center',
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
    'exercise_media_manager',
    'training_center',
}

ROUTE_ALIASES = {
    # Mobile MVP aliases.
    'home': 'home',
    'workout': 'workout',
    'history': 'history',
    'progress': 'progress',
    'apple health': 'apple_health',
    'apple_health': 'apple_health',
    'profile': 'profile',
    # Legacy aliases.
    'app': 'ai_personal_coach',
    'mission': 'ai_personal_coach',
    'coach': 'ai_personal_coach',
    'ai coach': 'ai_personal_coach',
    'ai personal coach': 'ai_personal_coach',
    'ai personal trainer': 'ai_personal_coach',
    'ai_personal_trainer': 'ai_personal_coach',
    'command center': 'command_center',
    'dashboard': 'dashboard',
    'recovery': 'recovery_center',
    'nutrition': 'nutrition_center',
    'health': 'health_center',
    'performance': 'performance_center',
    'apple intelligence': 'apple_activity',
    'apple activity': 'apple_activity',
    'todays workout': 'workout',
    "today's workout": 'workout',
    'progress analytics': 'progress',
    'recovery & readiness': 'recovery_readiness',
    'recovery readiness': 'recovery_readiness',
    'system check': 'system_center',
    'exercise media manager': 'exercise_media_manager',
    'media manager': 'exercise_media_manager',
    'history_center': 'history',
    'workout_history': 'history',
    'session_history': 'history',
    'smart_scale': 'smart_scale_import',
}

ROUTE_KEY_TO_PAGE = {
    # Mobile MVP pages.
    'home': 'Home',
    'workout': 'Workout',
    'history': 'History',
    'progress': 'Progress',
    'apple_health': 'Apple Health',
    'profile': 'Profile',
    # Legacy pages.
    'ai_personal_coach': 'AI Personal Trainer',
    'command_center': 'Command Center',
    'dashboard': 'Dashboard',
    'gym_mode': 'Gym Mode',
    'history_center': 'History',
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
    'exercise_media_manager': 'Exercise Media Manager',
    'training_center': 'Weekly Plan',
}

PAGE_TO_ROUTE_KEY = {
    # Mobile MVP pages.
    'Home': 'home',
    'Workout': 'workout',
    'History': 'history',
    'Progress': 'progress',
    'Apple Health': 'apple_health',
    'Profile': 'profile',
    # Legacy pages.
    'AI Personal Trainer': 'ai_personal_coach',
    'Command Center': 'command_center',
    'Dashboard': 'dashboard',
    "Today's Workout": 'workout',
    'Gym Mode': 'gym_mode',
    'Progress Analytics': 'progress',
    'Apple Activity': 'apple_activity',
    'Recovery Center': 'recovery_center',
    'Recovery & Readiness': 'recovery_readiness',
    'Nutrition': 'nutrition_center',
    'Exercise Library': 'exercise_library',
    'Body Stats': 'body_stats',
    'Smart Scale': 'smart_scale_import',
    'System Center': 'system_center',
    'Exercise Media Manager': 'exercise_media_manager',
    'Weekly Plan': 'training_center',
}


def default_home_route() -> str:
    return 'home'


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
    return ROUTE_KEY_TO_PAGE.get(key, 'Home')


def route_from_page(page: str | None) -> str:
    raw = str(page or '').strip()
    mapped = PAGE_TO_ROUTE_KEY.get(raw)
    if mapped:
        return mapped
    return normalize_route(raw)
