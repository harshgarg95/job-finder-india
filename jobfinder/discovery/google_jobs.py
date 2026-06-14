"""Channel B, Layer 2 — Google Jobs via SerpAPI (optional, BYO key).

You query *Google*, not the platform, so legitimacy is clean. Google's index
surfaces LinkedIn-posted and many board listings, deduplicated. Weak on Naukri
(use the Apify channel for that). Off unless SERPAPI_KEY is set in your .env.

Cost is the user's own SerpAPI quota. We send only the search query — no
personal data, no resume.
"""

from __future__ import annotations

import os

import requests

from ..schema import JobPosting
from .base import Query

ENDPOINT = "https://serpapi.com/search.json"
TIMEOUT = 30


def _pick_apply_url(job: dict) -> str:
    for opt in job.get("apply_options", []) or []:
        if opt.get("link"):
            return opt["link"]
    rel = job.get("related_links") or []
    if rel and rel[0].get("link"):
        return rel[0]["link"]
    return job.get("share_link", "") or ""


def _extensions(job: dict) -> dict:
    # detected_extensions holds posted_at, schedule_type, work_from_home, etc.
    return job.get("detected_extensions", {}) or {}


class GoogleJobsProvider:
    id = "google_jobs"

    def enabled(self, cfg: dict) -> bool:
        return bool(os.environ.get("SERPAPI_KEY"))

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        key = os.environ.get("SERPAPI_KEY")
        if not key:
            return []
        titles = query.titles or ([query.raw_keywords] if query.raw_keywords else ["jobs"])
        out: list[JobPosting] = []
        seen_urls: set[str] = set()
        per_query = max(10, query.limit_per_channel // max(1, len(titles)))

        for title in titles:
            collected = 0
            page_token = None
            while collected < per_query:
                params = {
                    "engine": "google_jobs",
                    "q": f"{title} {query.location}".strip(),
                    "hl": "en",
                    "api_key": key,
                }
                if query.location:
                    params["location"] = query.location
                if page_token:
                    params["next_page_token"] = page_token
                r = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    raise RuntimeError(f"SerpAPI: {data['error']}")
                results = data.get("jobs_results", []) or []
                if not results:
                    break
                for job in results:
                    url = _pick_apply_url(job)
                    dedup_key = url or f"{job.get('company_name','')}::{job.get('title','')}"
                    if dedup_key in seen_urls:
                        continue
                    seen_urls.add(dedup_key)
                    ext = _extensions(job)
                    remote = "remote" if ext.get("work_from_home") else None
                    out.append(JobPosting(
                        title=job.get("title", "") or "",
                        company=job.get("company_name", "") or "",
                        source="google_jobs",
                        url=url,
                        location=job.get("location", "") or query.location,
                        description=job.get("description", "") or "",
                        employment_type=ext.get("schedule_type"),
                        remote=remote,
                        posted_at=ext.get("posted_at"),
                    ))
                    collected += 1
                page_token = (data.get("serpapi_pagination") or {}).get("next_page_token")
                if not page_token:
                    break
        return out
