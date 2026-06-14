"""Channel A — zero-token public-ATS scan.

Reads the *public* JSON job feeds of Greenhouse, Lever, Ashby, and Workable for
a curated list of India-relevant company tenants (config/ats_tenants.india.yml).
No API key, no login, no personal data sent — just a company slug to a public
jobs API. This is the free, reliable, default discovery channel.

Pattern credit: career-ops's plugin-provider ATS scan (MIT). Reimplemented here
in Python with our own normalization and an India tenant list.

Each ATS has a fixed API host (allowlisted) and the slug goes only in the path,
so there is no SSRF surface. We normalize every feed into JobPosting.
"""

from __future__ import annotations

import re
from typing import Optional

import requests

from ..schema import JobPosting
from .base import Query

UA = "job-finder/0.1 (+https://github.com/harshgarg95/job-finder)"
TIMEOUT = 20


def _get_json(url: str) -> object:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=TIMEOUT, allow_redirects=False)
    r.raise_for_status()
    return r.json()


def _strip_html(html: str) -> str:
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text("\n")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Per-ATS fetchers: each returns a list[JobPosting] for one tenant slug ─────

def fetch_greenhouse(slug: str, company: str) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    data = _get_json(url)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out = []
    for j in jobs:
        if not j.get("absolute_url"):
            continue
        out.append(JobPosting(
            title=j.get("title", "") or "",
            company=company,
            source="ats:greenhouse",
            url=j.get("absolute_url", ""),
            location=(j.get("location") or {}).get("name", "") or "",
            description=_strip_html(j.get("content", "") or ""),
            posted_at=j.get("first_published") or j.get("updated_at"),
        ))
    return out


def fetch_lever(slug: str, company: str) -> list[JobPosting]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = _get_json(url)
    if not isinstance(data, list):
        return []
    out = []
    for j in data:
        cats = j.get("categories", {}) or {}
        desc = j.get("descriptionPlain") or _strip_html(j.get("description", "") or "")
        # Lever "lists" hold requirements/responsibilities — fold them in for scoring.
        extra = []
        for lst in j.get("lists", []) or []:
            extra.append(f"{lst.get('text','')}:\n{_strip_html(lst.get('content','') or '')}")
        full = "\n\n".join([desc] + extra).strip()
        out.append(JobPosting(
            title=j.get("text", "") or "",
            company=company,
            source="ats:lever",
            url=j.get("hostedUrl", "") or "",
            location=cats.get("location", "") or "",
            description=full,
            employment_type=cats.get("commitment"),
            remote="remote" if "remote" in (cats.get("location", "") or "").lower() else None,
            posted_at=_epoch_to_iso(j.get("createdAt")),
        ))
    return out


def fetch_ashby(slug: str, company: str) -> list[JobPosting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    data = _get_json(url)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out = []
    for j in jobs:
        comp = j.get("compensation") or {}
        salary_text = None
        summary = comp.get("compensationTierSummary")
        if summary:
            salary_text = summary
        out.append(JobPosting(
            title=j.get("title", "") or "",
            company=company,
            source="ats:ashby",
            url=j.get("jobUrl", "") or j.get("applyUrl", "") or "",
            location=j.get("location", "") or "",
            description=j.get("descriptionPlain") or _strip_html(j.get("descriptionHtml", "") or ""),
            employment_type=j.get("employmentType"),
            remote="remote" if j.get("isRemote") else None,
            salary_text=salary_text,
            posted_at=j.get("publishedAt"),
        ))
    return out


def fetch_workable(slug: str, company: str) -> list[JobPosting]:
    # Public widget JSON (details=true includes description text).
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
    data = _get_json(url)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out = []
    for j in jobs:
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x) or j.get("location", "")
        desc = _strip_html(j.get("description", "") or "")
        reqs = _strip_html(j.get("requirements", "") or "")
        full = "\n\n".join(x for x in [desc, reqs] if x)
        out.append(JobPosting(
            title=j.get("title", "") or "",
            company=company,
            source="ats:workable",
            url=j.get("url") or j.get("application_url") or j.get("shortlink", "") or "",
            location=loc,
            description=full,
            employment_type=j.get("employment_type"),
            remote="remote" if j.get("telecommuting") else None,
            posted_at=j.get("published_on") or j.get("created_at"),
        ))
    return out


_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
}


def _epoch_to_iso(ms) -> Optional[str]:
    if not ms:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except Exception:
        return None


def fetch_one(ats: str, slug: str, company: str) -> list[JobPosting]:
    """Fetch one tenant. Raises on HTTP/JSON error (caller decides how to log)."""
    fetcher = _FETCHERS.get(ats)
    if not fetcher:
        raise ValueError(f"Unknown ATS '{ats}' (known: {', '.join(_FETCHERS)})")
    return fetcher(slug, company)


# ── Provider implementation ──────────────────────────────────────────────────

class AtsProvider:
    id = "ats"

    def __init__(self, tenants: list[dict]):
        # tenants: [{company, ats, slug}, ...]
        self.tenants = tenants

    def enabled(self, cfg: dict) -> bool:
        return bool(self.tenants)  # always on; it's the free default channel

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        results: list[JobPosting] = []
        errors: list[str] = []
        for t in self.tenants:
            try:
                jobs = fetch_one(t["ats"], t["slug"], t.get("company", t["slug"]))
                for j in jobs:  # ATS links are employer-native → verified by construction
                    j.link_verified = True
                    j.link_source = f"employer-ats:{t['ats']}"
                results.extend(jobs)
            except Exception as e:  # one dead tenant must not break the scan
                errors.append(f"{t.get('company', t['slug'])}({t['ats']}:{t['slug']}): {e}")
        # Surface errors so a broken tenant is reported, not silently 0.
        self.last_errors = errors
        return results
