from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import time
from typing import Dict, Iterator

import streamlit as st


_COLD_START_KEY = "_perf_cold_start_seen"
_RENDER_METRICS_KEY = "perf_sections"
_RENDER_META_KEY = "perf_last_page"
_QUERY_COUNT_KEY = "perf_query_counts"


def clear_render_metrics() -> None:
    st.session_state[_RENDER_METRICS_KEY] = {}
    st.session_state[_QUERY_COUNT_KEY] = {}


def record_metric(name: str, elapsed_ms: float) -> None:
    sections = st.session_state.setdefault(_RENDER_METRICS_KEY, {})
    sections[str(name)] = round(float(elapsed_ms), 2)


def record_query_call(name: str) -> None:
    counts = st.session_state.setdefault(_QUERY_COUNT_KEY, {})
    key = str(name)
    counts[key] = int(counts.get(key, 0)) + 1


@contextmanager
def timed_section(name: str) -> Iterator[None]:
    started = time.perf_counter()
    success = False
    try:
        yield
        success = True
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        record_metric(name, elapsed_ms)
        log_rows = st.session_state.setdefault("perf_log", [])
        log_rows.append(
            {
                "name": str(name),
                "elapsed_ms": round(elapsed_ms, 2),
                "status": "ok" if success else "error",
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )


def get_render_metrics() -> Dict[str, object]:
    sections = dict(st.session_state.get(_RENDER_METRICS_KEY, {}))
    query_counts = dict(st.session_state.get(_QUERY_COUNT_KEY, {}))
    if not sections:
        return {
            "render_ms": 0.0,
            "slowest_section": "",
            "slowest_ms": 0.0,
            "sections": sections,
            "query_counts": query_counts,
        }
    slowest_name = max(sections, key=lambda key: float(sections[key]))
    total_ms = round(sum(float(v) for v in sections.values()), 2)
    return {
        "render_ms": total_ms,
        "slowest_section": str(slowest_name),
        "slowest_ms": float(sections[slowest_name]),
        "sections": sections,
        "query_counts": query_counts,
    }


def mark_cold_start() -> bool:
    if not st.session_state.get(_COLD_START_KEY, False):
        st.session_state[_COLD_START_KEY] = True
        return True
    return False


def is_cold_start() -> bool:
    return bool(st.session_state.get(_COLD_START_KEY, False))


def save_render_summary(page_name: str) -> Dict[str, object]:
    summary = get_render_metrics()
    summary["page"] = str(page_name)
    summary["rendered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state[_RENDER_META_KEY] = summary
    return summary
