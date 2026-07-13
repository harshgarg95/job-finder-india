"""Reactive request-quota safety for metered free-tier channels (Adzuna, JSearch).

Mirrors the Apify spend-safety idea, adapted to REQUEST-COUNT free tiers that have
no cheap credit-probe endpoint: a per-run request cap + a persisted monthly counter.
When a channel's monthly cap is reached — or an API returns a 429 / quota error —
the channel is skipped and discovery AUTO-DEGRADES to the ATS floor + other channels.
It never hard-fails. A new calendar month resets the counter automatically.

State lives in data/.state/quota_<channel>.json = {"month": "YYYY-MM", "count": N}.
"""

from __future__ import annotations

from datetime import date

from .. import state

_QUOTA_HINTS = ("rate limit", "ratelimit", "quota", "exceeded", "too many requests",
                "monthly", "limit reached", "usage limit")


def _month() -> str:
    return date.today().strftime("%Y-%m")


def _key(channel: str) -> str:
    return f"quota_{channel}"


def used_this_month(channel: str) -> int:
    st = state.read(_key(channel))
    return int(st.get("count", 0)) if st.get("month") == _month() else 0


def remaining(channel: str, monthly_cap: int) -> int:
    return max(0, int(monthly_cap) - used_this_month(channel))


def record(channel: str, n: int = 1) -> None:
    m = _month()
    st = state.read(_key(channel))
    base = int(st.get("count", 0)) if st.get("month") == m else 0
    state.write(_key(channel), {"month": m, "count": base + n})


def exhausted(channel: str, monthly_cap: int) -> bool:
    return used_this_month(channel) >= int(monthly_cap)


def mark_exhausted(channel: str, monthly_cap: int) -> None:
    """Force the channel to 'used up this month' after a 429/quota error."""
    state.write(_key(channel), {"month": _month(), "count": int(monthly_cap)})


def is_quota_error(status: int, body: str) -> bool:
    """429 is definitive; 402/403 count only with a quota/rate message in the body."""
    if status == 429:
        return True
    b = (body or "").lower()
    return status in (402, 403) and any(h in b for h in _QUOTA_HINTS)
