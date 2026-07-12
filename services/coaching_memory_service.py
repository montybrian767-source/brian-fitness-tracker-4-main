from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.supabase_service import connect_supabase


def coaching_memory_table_available() -> bool:
    client, err = connect_supabase()
    if err or client is None:
        return False
    try:
        client.table('coaching_memory').select('id').limit(1).execute()
        return True
    except Exception:
        return False


def upsert_coaching_memory(observations: List[Dict[str, Any]]) -> Tuple[bool, str]:
    client, err = connect_supabase()
    if err or client is None:
        return False, str(err or 'supabase unavailable')
    try:
        for item in observations or []:
            memory_type = str(item.get('memory_type', '')).strip()
            memory_key = str(item.get('memory_key', '')).strip()
            summary = str(item.get('summary', '')).strip()
            if not memory_type or not memory_key or not summary:
                continue
            client.table('coaching_memory').upsert(
                {
                    'memory_type': memory_type,
                    'memory_key': memory_key,
                    'summary': summary,
                    'confidence': float(item.get('confidence', 0.0) or 0.0),
                },
                on_conflict='memory_type,memory_key',
            ).execute()
        return True, ''
    except Exception as exc:
        return False, str(exc)
