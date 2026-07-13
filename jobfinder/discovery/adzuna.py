"""Channel A2 — Adzuna official API (co-primary India-native, free tier, keyed).

The cleaner of the two India-native channels: an official, documented API (no
scraping, no ToS grey-area). Off unless ADZUNA_APP_ID + ADZUNA_APP_KEY are set.
Sends only the search query — no personal data, no resume.

Response shape VERIFIED live on 2026-07-11 against this account:
  GET https://api.adzuna.com/v1/api/jobs/in/search/1
      ?app_id&app_key&results_per_page&what=<title>&where=India&max_days_old=30
  200 -> {"count": N, "mean": .., "results": [{
            "title", "company": {"display_name"}, "location": {"display_name","area"},
            "redirect_url", "description", "created", "id",
            "salary_min", "salary_max", "salary_is_predicted", "contract_time",
            "category": {"label"}}]}
  (e.g. "Agentic AI Manager @ Marico Limited, Mumbai" — 1,794 matches for "AI manager".)

Quota-safe (see quota.py): a per-run request cap + a persisted monthly counter.
On a 429 / quota error the channel auto-pauses for the month and discovery
degrades to the ATS floor — it NEVER hard-fails.
"""

from __future__ import annotations

import os

import requests

from ..schema import JobPosting
from . import quota
from .base import Query

API = "https://api.adzuna.com/v1/api/jobs/in/search"   # country "in" is in the path
TIMEOUT = 30
CHANNEL = "adzuna"
_UA = "job-finder-india/1.0 (+https://github.com/harshgarg95/job-finder-india)"
DEFAULT_PER_RUN = 3
DEFAULT_MONTHLY_CAP = 250


def _budget(cfg: dict) -> dict:
    return ((cfg.get("run", {}) or {}).get("discovery", {}) or {}).get(CHANNEL, {}) or {}


def _cap(cfg: dict) -> int:
    return int(_budget(cfg).get("monthly_cap", DEFAULT_MONTHLY_CAP))


def _per_run(cfg: dict) -> int:
    return int(_budget(cfg).get("max_requests_per_run", DEFAULT_PER_RUN))


def _map(j: dict) -> JobPosting:
    company = (j.get("company") or {}).get("display_name", "") or ""
    location = (j.get("location") or {}).get("display_name", "") or ""
    predicted = str(j.get("salary_is_predicted", "0")) == "1"
    # Honesty at the data layer: Adzuna's *predicted* salary is its own estimate,
    # not what the employer stated — don't present it as the JD's comp.
    smin = None if predicted else j.get("salary_min")
    smax = None if predicted else j.get("salary_max")
    return JobPosting(
        title=j.get("title", "") or "",
        company=company,
        source="adzuna",
        url=j.get("redirect_url", "") or "",
        location=location,
        description=j.get("description", "") or "",     # snippet; enrich deep-fetches the full JD
        salary_min=smin, salary_max=smax,
        salary_currency="INR" if (smin is not None or smax is not None) else None,
        employment_type=j.get("contract_time"),          # "full_time" / "part_time"
        posted_at=(j.get("created") or "")[:10] or None,
        link_source="adzuna",
    )


class AdzunaProvider:
    id = "adzuna"

    def enabled(self, cfg: dict) -> bool:
        src = (cfg.get("sources", {}) or {}).get("adzuna")
        if src is not None and not src.get("enabled"):
            self._skip = "off in config/sources.yml"
            return False
        if not (os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")):
            self._skip = "no ADZUNA_APP_ID / ADZUNA_APP_KEY in .env"
            return False
        cap = _cap(cfg)
        if quota.exhausted(CHANNEL, cap):
            self._skip = (f"monthly quota reached ({cap}/mo) — resets next month; "
                          "running on ATS + other channels")
            return False
        return True

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        aid, akey = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
        if not (aid and akey):
            return []
        cap = _cap(cfg)
        per_run = _per_run(cfg)
        rpp = min(50, max(1, query.limit_per_channel))
        where = query.location or "India"
        titles = (query.titles[:per_run] or [query.raw_keywords or "jobs"])
        out: list[JobPosting] = []
        errors: list[str] = []
        made = 0
        for title in titles:
            if made >= per_run or quota.exhausted(CHANNEL, cap):
                break
            try:
                r = requests.get(
                    f"{API}/1",
                    params={"app_id": aid, "app_key": akey, "results_per_page": rpp,
                            "what": title, "where": where, "max_days_old": 30},
                    headers={"User-Agent": _UA, "Accept": "application/json"},
                    timeout=TIMEOUT)
                made += 1
                quota.record(CHANNEL, 1)                  # count every request against the monthly cap
                if r.status_code >= 300:
                    if quota.is_quota_error(r.status_code, r.text):
                        quota.mark_exhausted(CHANNEL, cap)
                        errors.append(f"quota/rate limit (HTTP {r.status_code}) → paused for the month")
                        break
                    errors.append(f"'{title}': HTTP {r.status_code} {r.text[:100]}")
                    continue
                for j in (r.json().get("results") or []):
                    jp = _map(j)
                    if jp.title:
                        out.append(jp)
            except requests.Timeout:
                errors.append(f"'{title}': timeout")
            except Exception as e:                        # noqa: BLE001 — never hard-fail a run
                errors.append(f"'{title}': {e}")
        self.last_errors = errors
        return out
