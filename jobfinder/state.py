"""Tiny machine-local state store (data/.state/*.json).

Runtime state the app manages for the user — currently only the Apify
auto-pause status. This is NOT personal data and is never transmitted; it just
lets a pause survive between runs so a credits-out channel stays off until a
cheap probe confirms credits are back. User Layer (under data/, gitignored).
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, "data", ".state")


def _path(name: str) -> str:
    return os.path.join(STATE_DIR, f"{name}.json")


def read(name: str) -> dict:
    """Return the stored dict for `name`, or {} if absent/corrupt."""
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write(name: str, data: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear(name: str) -> None:
    try:
        os.remove(_path(name))
    except FileNotFoundError:
        pass
