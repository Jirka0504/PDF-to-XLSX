from __future__ import annotations
import re

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def money_to_str(s: str) -> str:
    # Keep as string to avoid locale issues; user can format in Excel.
    return normalize_ws(s).replace(",", ".")
