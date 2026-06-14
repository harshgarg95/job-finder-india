"""Channel B, Layer 3 — Apify BYO-token, Naukri (optional, OFF by default).

Closes the India gap (Naukri) that ATS + Google Jobs miss. This is the one
channel that brings *structured Indian experience + CTC bands* to the scorer —
the data nobody else feeds a holistic scorer (docs/research/02).

Strictly opt-in and account-bounded:
  - OFF unless APIFY_TOKEN is set AND discovery.apify_naukri.enabled: true.
  - Runs bill to the USER's own Apify account ($5/mo free credit, no card).
  - The user accepts Naukri's ToS directly; job-finder is only an orchestrator.
  - Token is sent ONLY as `Authorization: Bearer` to api.apify.com — never in a
    URL, never logged, never persisted (Apify's own security guidance).

NOTE: the structured Naukri actors are low-adoption community actors and their
input/output schemas drift. The actor handle and field names are therefore
configurable (see config keys below) so users can switch actors without a code
change. Default actor: epicscrapers/naukri-scraper (cleanest field names + best
rating per docs/research/02); memo23/naukri-scraper is the cheaper alternative.

⚠️ UNTESTED LIVE in this build (no token on the build machine; runs cost money).
The mapping below follows the documented schemas; validate with one real run
before relying on Naukri comp numbers (the Phase-1 gate flagged in the build
plan).
"""

from __future__ import annotations

import os

import requests

from ..schema import JobPosting
from .base import Query

API_BASE = "https://api.apify.com/v2/acts"
TIMEOUT = 300  # run-sync waits for the actor to finish

DEFAULT_ACTOR = "epicscrapers/naukri-scraper"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _map_item(item: dict) -> JobPosting:
    """Map a Naukri actor row to JobPosting. Defensive across the epicscrapers
    and memo23 shapes (field names differ; we try both)."""
    salary = item.get("salaryDetail") or {}
    smin = _to_float(salary.get("minimumSalary")) if salary else _to_float(item.get("salaryMin"))
    smax = _to_float(salary.get("maximumSalary")) if salary else _to_float(item.get("salaryMax"))
    currency = salary.get("currency") if salary else item.get("salaryCurrency")

    return JobPosting(
        title=item.get("title", "") or "",
        company=item.get("companyName") or (item.get("companyDetail") or {}).get("name", "") or "",
        source="apify:naukri",
        url=item.get("jdURL") or item.get("staticUrl") or item.get("jobUrl", "") or "",
        location=", ".join(item.get("locations", [])) if isinstance(item.get("locations"), list)
                 else (item.get("locationText") or item.get("location", "") or ""),
        description=item.get("jobDescription") or item.get("description", "") or "",
        experience_min=_to_float(item.get("minimumExperience")) if item.get("minimumExperience") is not None
                       else _to_float(item.get("experienceMin")),
        experience_max=_to_float(item.get("maximumExperience")) if item.get("maximumExperience") is not None
                       else _to_float(item.get("experienceMax")),
        salary_min=smin,
        salary_max=smax,
        salary_currency=currency or ("INR" if (smin or smax) else None),
        salary_text=item.get("experienceText") and None or item.get("salaryText"),
        skills=item.get("tagsAndSkills", "").split(",") if isinstance(item.get("tagsAndSkills"), str)
               else (item.get("keySkills") or item.get("skills") or []),
        posted_at=item.get("createdDate") or item.get("postedDate"),
    )


class ApifyNaukriProvider:
    id = "apify_naukri"

    def enabled(self, cfg: dict) -> bool:
        sub = (cfg.get("discovery", {}) or {}).get("apify_naukri", {}) or {}
        return bool(os.environ.get("APIFY_TOKEN")) and bool(sub.get("enabled"))

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            return []
        sub = (cfg.get("discovery", {}) or {}).get("apify_naukri", {}) or {}
        actor = sub.get("actor", DEFAULT_ACTOR).replace("/", "~")
        max_items = int(sub.get("max_items", min(60, query.limit_per_channel)))

        # Actor input. Field names vary per actor; allow override via cfg.input.
        keywords = query.titles or ([query.raw_keywords] if query.raw_keywords else [])
        actor_input = {
            "keyword": ", ".join(keywords),
            "maxItems": max_items,
            "location": query.location,
        }
        actor_input.update(sub.get("input", {}) or {})

        url = f"{API_BASE}/{actor}/run-sync-get-dataset-items"
        r = requests.post(
            url,
            params={"timeout": TIMEOUT, "memory": 1024, "limit": max_items},
            json=actor_input,
            headers={"Authorization": f"Bearer {token}"},  # never in URL
            timeout=TIMEOUT + 30,
        )
        r.raise_for_status()
        items = r.json()
        if not isinstance(items, list):
            return []
        return [_map_item(it) for it in items if it.get("title")]
