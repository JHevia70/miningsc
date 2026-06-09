"""
Normalises OCR-read mineral names to canonical names using mineral_map.json.

The mineral_map maps lowercase substrings → canonical name.
We strip game suffixes like (ORE), (RAW), (Ore) before matching.
"""

import json
import re
from pathlib import Path
from typing import Optional

def _load_map() -> dict[str, str]:
    p = Path(__file__).parent.parent / "tools" / "mineral_map.json"
    if not p.exists():
        # Bundled path (PyInstaller)
        import sys
        if getattr(sys, "frozen", False):
            p = Path(sys._MEIPASS) / "tools" / "mineral_map.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}

_MAP: dict[str, str] = _load_map()

_SUFFIX = re.compile(r'\s*\((?:ORE|RAW|Ore|Raw)\)\s*$', re.IGNORECASE)
_NONALPHA = re.compile(r'[^A-Z0-9\s]')


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two strings."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j] + (ca != cb), curr[-1] + 1, prev[j + 1] + 1))
        prev = curr
    return prev[-1]


def normalize(name: str) -> Optional[str]:
    """
    Given an OCR mineral name like 'TORITE(ORE)' or 'TOMTE(OME)',
    return the canonical name ('Torite') or None if unrecognised.

    Tries in order:
    1. Direct key match
    2. Substring match
    3. Fuzzy match (edit distance ≤ 2 for names ≥5 chars, ≤1 for shorter)
    """
    if not name:
        return None
    clean = _SUFFIX.sub('', name).strip()
    clean = re.sub(r'[^A-Za-z\s]', '', clean).strip()
    key = clean.lower()
    if not key:
        return None

    # 1. Direct match
    if key in _MAP:
        return _MAP[key]

    # 2. Substring match
    for substr, canon in _MAP.items():
        if substr in key:
            return canon

    # 3. Fuzzy match against each map key
    best_canon, best_dist = None, 999
    for substr, canon in _MAP.items():
        # Only compare against keys of similar length (±2 chars)
        if abs(len(substr) - len(key)) > 2:
            continue
        threshold = 3 if len(substr) >= 6 else 2 if len(substr) >= 4 else 1
        d = _edit_distance(key, substr)
        if d <= threshold and d < best_dist:
            best_dist = d
            best_canon = canon

    return best_canon
