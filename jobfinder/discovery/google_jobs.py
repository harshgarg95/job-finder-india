"""Channel B, Layer 2 — Google Jobs via SerpAPI (optional, BYO key).

You query *Google*, not the platform, so legitimacy is clean. Google's index
surfaces LinkedIn-posted and many board listings, deduplicated. Weak on Naukri
(use the Apify channel for that). Off unless SERPAPI_KEY is set in your .env.

Cost is the user's own SerpAPI quota. We send only the search query — no
personal data, no resume.
"""

from __future__ import annotations

import concurrent.futures as cf
import os

import requests

from ..schema import JobPosting
from . import link_resolver
from .base import Query

ENDPOINT = "https://serpapi.com/search.json"
TIMEOUT = 30


def _apply_options(job: dict) -> list[dict]:
    # apply_options are the real per-source apply links. We deliberately ignore
    # share_link (always a google.com/search page, never a real JD).
    opts = list(job.get("apply_options", []) or [])
    for r in job.get("related_links") or []:
        if r.get("link"):
            opts.append({"title": r.get("text", "related"), "link": r["link"]})
    return opts


def _extensions(job: dict) -> dict:
    # detected_extensions holds posted_at, schedule_type, work_from_home, etc.
    return job.get("detected_extensions", {}) or {}


class GoogleJobsProvider:
    id = "google_jobs"

    def enabled(self, cfg: dict) -> bool:
        src = (cfg.get("sources", {}) or {}).get("google_jobs")
        if src is not None and not src.get("enabled"):
            self._skip = "off in config/sources.yml (set enabled: true + SERPAPI_KEY in .env)"
            return False
        if not os.environ.get("SERPAPI_KEY"):
            self._skip = "no SERPAPI_KEY in .env"
            return False
        return True

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        key = os.environ.get("SERPAPI_KEY")
        if not key:
            return []
        sub = (cfg.get("discovery", {}) or {}).get("google_jobs", {}) or {}
        verify = sub.get("verify_links", True)        # authenticate links (default on)
        drop_unverified = sub.get("drop_unverified", False)

        titles = query.titles or ([query.raw_keywords] if query.raw_keywords else ["jobs"])
        out: list[JobPosting] = []
        options: list[list[dict]] = []               # parallel apply_options per job
        seen_urls: set[str] = set()
        per_query = max(10, query.limit_per_channel // max(1, len(titles)))

        for title in titles:
            collected = 0
            page_token = None
            while collected < per_query:
                params = {"engine": "google_jobs", "q": f"{title} {query.location}".strip(),
                          "hl": "en", "api_key": key}
                if query.location:
                    params["location"] = query.location
                if page_token:
                    params["next_page_token"] = page_token
                r = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    err = str(data["error"])
                    # SerpAPI reports "no results" as an error — that's a normal
                    # empty query, not a failure. Only real errors (bad key,
                    # exhausted quota) should abort the run.
                    if "hasn't returned any results" in err.lower() or "no results" in err.lower():
                        break
                    raise RuntimeError(f"SerpAPI: {err}")
                results = data.get("jobs_results", []) or []
                if not results:
                    break
                for job in results:
                    opts = _apply_options(job)
                    dedup_key = (opts[0]["link"] if opts else "") or \
                                f"{job.get('company_name','')}::{job.get('title','')}"
                    if dedup_key in seen_urls:
                        continue
                    seen_urls.add(dedup_key)
                    ext = _extensions(job)
                    out.append(JobPosting(
                        title=job.get("title", "") or "",
                        company=job.get("company_name", "") or "",
                        source="google_jobs",
                        url=opts[0]["link"] if opts else "",
                        location=job.get("location", "") or query.location,
                        description=job.get("description", "") or "",
                        employment_type=ext.get("schedule_type"),
                        remote="remote" if ext.get("work_from_home") else None,
                        posted_at=ext.get("posted_at"),
                    ))
                    options.append(opts)
                    collected += 1
                page_token = (data.get("serpapi_pagination") or {}).get("next_page_token")
                if not page_token:
                    break

        if verify:
            self._verify_all(out, options)
            if drop_unverified:
                out = [j for j in out if j.link_verified]
        return out

    @staticmethod
    def _verify_all(jobs: list[JobPosting], options: list[list[dict]]) -> None:
        """Resolve + HTTP-verify each job's best apply link in parallel. Sets
        url / link_verified / link_source on each job (the 'authentication')."""
        def work(i):
            res = link_resolver.resolve_best(options[i], jobs[i].company, jobs[i].title, verify=True)
            return i, res
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            for i, res in ex.map(work, range(len(jobs))):
                if res.url:
                    jobs[i].url = res.url
                jobs[i].link_verified = res.verified
                jobs[i].link_source = res.source
