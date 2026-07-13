"""Channel A3 — JSearch (OpenWeb Ninja) India-native SUPPLEMENT, gap-fill only.

JSearch indexes Google-for-Jobs (LinkedIn / Naukri / Indeed surfaced), so it
overlaps Adzuna. It is therefore a SUPPLEMENT, spent ONLY when the co-primary
Adzuna comes back thin (the registry's gap-fill gate) — because its free tier is
scarcer than Adzuna's. Off unless JSEARCH_API_KEY is set.

Two hosts (config/sources.yml → jsearch.host):
  • "rapidapi"    → https://jsearch.p.rapidapi.com/search-v2
                    headers: X-RapidAPI-Key, X-RapidAPI-Host: jsearch.p.rapidapi.com
  • "openwebninja"→ https://api.openwebninja.com/jsearch/search-v2  (direct portal)
                    header: X-API-Key

VERIFIED live on 2026-07-11 (RapidAPI host, JSearch **v5**): the endpoint is
`GET /search-v2` — v5 renamed it from `/search` (which now 404s). Free tier is
**200 requests/month** (X-RateLimit-Requests-Limit). The v5 response wraps the
jobs: `data` is `{"jobs": [...], "cursor": "..."}`, so the list is `data["jobs"]`;
each job's fields are exactly as mapped below (confirmed against a real 200).

`fetch()` still self-skips on any non-200 (guard), so a future API change degrades
to Adzuna + ATS rather than feeding bad data. It NEVER hard-fails.

Quota-safe (quota.py): per-run request cap + persisted monthly counter; 429 →
auto-pause for the month.
"""

from __future__ import annotations

import os

import requests

from ..schema import JobPosting
from . import quota
from .base import Query

TIMEOUT = 30
CHANNEL = "jsearch"
DEFAULT_PER_RUN = 3
DEFAULT_MONTHLY_CAP = 200          # VERIFIED from RapidAPI X-RateLimit-Requests-Limit header
DEFAULT_TRIGGER_BELOW = 40         # only fill in when Adzuna returns < this many

_HOSTS = {
    "rapidapi": {
        "url": "https://jsearch.p.rapidapi.com/search-v2",     # v5 endpoint (was /search)
        "headers": lambda key: {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
    },
    "openwebninja": {
        "url": "https://api.openwebninja.com/jsearch/search-v2",   # direct portal (unverified path)
        "headers": lambda key: {"X-API-Key": key},
    },
}


def _jobs_from(payload: dict) -> list:
    """Extract the jobs list. JSearch v5 (/search-v2) nests them under
    data["jobs"] (data is {"jobs": [...], "cursor": "..."}); older shapes put a
    bare list directly under data. Handle both so a host/version change is safe."""
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        return data.get("jobs") or []
    if isinstance(data, list):
        return data
    return []


def _budget(cfg: dict) -> dict:
    return ((cfg.get("run", {}) or {}).get("discovery", {}) or {}).get(CHANNEL, {}) or {}


def _cap(cfg: dict) -> int:
    return int(_budget(cfg).get("monthly_cap", DEFAULT_MONTHLY_CAP))


def _per_run(cfg: dict) -> int:
    return int(_budget(cfg).get("max_requests_per_run", DEFAULT_PER_RUN))


def _host(cfg: dict) -> dict:
    name = str(((cfg.get("sources", {}) or {}).get("jsearch", {}) or {}).get("host", "rapidapi")).lower()
    return _HOSTS.get(name, _HOSTS["rapidapi"])


def _map(j: dict) -> JobPosting:
    """Field map for a JSearch v5 job — VERIFIED against a real /search-v2 200."""
    loc = ", ".join(x for x in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if x)
    return JobPosting(
        title=j.get("job_title", "") or "",
        company=j.get("employer_name", "") or "",
        source="jsearch",
        url=j.get("job_apply_link", "") or "",
        location=loc,
        description=j.get("job_description", "") or "",
        salary_min=j.get("job_min_salary"), salary_max=j.get("job_max_salary"),
        salary_text=j.get("job_salary_string"),        # v5: formatted string (no separate currency field)
        employment_type=j.get("job_employment_type"),
        remote="remote" if j.get("job_is_remote") else None,
        posted_at=(j.get("job_posted_at_datetime_utc") or "")[:10] or None,
        link_source="jsearch",
    )


class JSearchProvider:
    id = "jsearch"
    gap_fill_after = "adzuna"          # the registry runs this only when Adzuna is thin

    def enabled(self, cfg: dict) -> bool:
        src = (cfg.get("sources", {}) or {}).get("jsearch")
        if src is not None and not src.get("enabled"):
            self._skip = "off in config/sources.yml"
            return False
        if not os.environ.get("JSEARCH_API_KEY"):
            self._skip = "no JSEARCH_API_KEY in .env"
            return False
        cap = _cap(cfg)
        if quota.exhausted(CHANNEL, cap):
            self._skip = (f"monthly quota reached ({cap}/mo) — resets next month; "
                          "running on ATS + Adzuna")
            return False
        return True

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        key = os.environ.get("JSEARCH_API_KEY")
        if not key:
            return []
        cap = _cap(cfg)
        per_run = _per_run(cfg)
        host = _host(cfg)
        headers = host["headers"](key)
        country = "in" if (query.location or "India").lower() in ("india", "in") else ""
        titles = (query.titles[:per_run] or [query.raw_keywords or "jobs"])
        out: list[JobPosting] = []
        errors: list[str] = []
        made = 0
        for title in titles:
            if made >= per_run or quota.exhausted(CHANNEL, cap):
                break
            q = f"{title} in {query.location}".strip() if query.location else title
            params = {"query": q, "num_pages": "1", "date_posted": "month"}   # v5: cursor-based, no page
            if country:
                params["country"] = country
            try:
                r = requests.get(host["url"], params=params, headers=headers, timeout=TIMEOUT)
                made += 1
                quota.record(CHANNEL, 1)
                if r.status_code >= 300:
                    if quota.is_quota_error(r.status_code, r.text):
                        quota.mark_exhausted(CHANNEL, cap)
                        errors.append(f"quota/rate limit (HTTP {r.status_code}) → paused for the month")
                        break
                    # GUARD: any other non-200 → skip this channel for the run rather
                    # than feed a shape we didn't get a clean 200 for. Never hard-fails.
                    errors.append(f"HTTP {r.status_code} {r.text[:120]} (non-200 → skipping JSearch this run)")
                    break
                for j in _jobs_from(r.json()):
                    jp = _map(j)
                    if jp.title:
                        out.append(jp)
            except requests.Timeout:
                errors.append(f"'{title}': timeout")
            except Exception as e:                        # noqa: BLE001 — never hard-fail a run
                errors.append(f"'{title}': {e}")
        self.last_errors = errors
        return out
