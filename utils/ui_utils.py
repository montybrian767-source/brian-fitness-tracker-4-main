from __future__ import annotations

import re


def safe_key(value, prefix="key"):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    if not text:
        text = "item"
    return f"{prefix}_{text}"
