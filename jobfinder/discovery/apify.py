"""Channel B, Layer 3 — Apify BYO-token, multi-platform (Naukri + LinkedIn + Indeed).

The legitimate way to reach the India-native boards and LinkedIn/Indeed that ATS
+ Google Jobs miss: cookieless community actors hitting each platform's PUBLIC
guest API (no login, no account-ban risk). OFF unless APIFY_TOKEN is set; runs
bill to the USER's own Apify account; the user accepts each board's ToS directly.

Each platform is one actor run per search (multiple title-URLs in a single run →
cost-efficient). Actor handles + field maps were confirmed against live runs on
2026-06-14; all are configurable so a user can swap actors without code changes.

Token is sent only as `Authorization: Bearer` to api.apify.com — never logged.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from ..schema import JobPosting
from .base import Query

API = "https://api.apify.com/v2/acts"
TIMEOUT = 240
DEFAULT_PLATFORMS = ["naukri", "linkedin", "indeed"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _slug(s: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in s.lower()).split())


def _epoch_iso(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except Exception:
        return None


def _strip_html(html: str) -> str:
    if not html or "<" not in html:
        return html or ""
    try:
        from bs4 import BeautifulSoup
        import re as _re
        t = BeautifulSoup(html, "html.parser").get_text("\n")
        return _re.sub(r"\n{3,}", "\n\n", t).strip()
    except Exception:
        import re as _re
        return _re.sub(r"<[^>]+>", " ", html).strip()


# ── URL builders (per platform search URLs) ─────────────────────────────────
def _naukri_url(title, loc):
    # Naukri keyword search needs ?k= (a bare SEO slug returns loosely-related
    # jobs). Format mirrors the memo23 actor's own example input.
    base = f"https://www.naukri.com/{_slug(title)}-jobs"
    if loc and loc.lower() != "india":
        base += f"-in-{_slug(loc)}"
    url = f"{base}?k={quote(title)}"
    if loc and loc.lower() != "india":
        url += f"&l={quote(loc)}"
    return url


def _linkedin_url(title, loc):
    return (f"https://www.linkedin.com/jobs/search/?keywords={quote(title)}"
            f"&location={quote(loc or 'India')}&f_TPR=r2592000")  # last 30 days


def _indeed_url(title, loc):
    return f"https://in.indeed.com/jobs?q={quote(title)}&l={quote(loc or 'India')}"


# ── Output mappers (actor item -> JobPosting) ───────────────────────────────
def _map_naukri(it):
    """Robust across Naukri actors: memo23 (full HTML `description`, locations[],
    companyDetail.name, staticUrl) and epicscrapers (snippet `jobDescription`,
    placeholders[], companyName, jdURL)."""
    # location
    loc = ""
    if isinstance(it.get("locations"), list) and it["locations"]:
        loc = ", ".join(x.get("label", "") for x in it["locations"] if x.get("label"))
    if not loc:
        for p in it.get("placeholders", []) or []:
            if p.get("type") == "location":
                loc = p.get("label", "")
    # company
    company = it.get("companyName") or (it.get("companyDetail") or {}).get("name") \
        or it.get("staticCompanyName") or ""
    # full description (memo23 `description` HTML) preferred over snippet
    desc = _strip_html(it.get("description") or "") or (it.get("jobDescription") or "")
    # url
    jd = it.get("jdURL") or ""
    url = it.get("staticUrl") or it.get("jobUrl") or \
        (("https://www.naukri.com" + jd) if jd.startswith("/") else jd)
    sd = it.get("salaryDetail") or {}
    smin, smax = _f(sd.get("minimumSalary")), _f(sd.get("maximumSalary"))
    hidden = sd.get("hideSalary") or (smin in (0, None) and smax in (0, None))
    skills = it.get("keySkills") or it.get("tagsAndSkills") or ""
    skills = skills.split(",") if isinstance(skills, str) else (skills or [])
    return JobPosting(
        title=it.get("title", "") or "", company=company,
        source="apify:naukri", url=url, location=loc, description=desc,
        experience_min=_f(it.get("minimumExperience")), experience_max=_f(it.get("maximumExperience")),
        salary_min=None if hidden else smin, salary_max=None if hidden else smax,
        salary_currency=sd.get("currency"),
        salary_text="Not disclosed" if hidden else None,
        skills=[s for s in skills if s],
        posted_at=_epoch_iso(it.get("createdDate")),
        link_verified=True, link_source="apify:naukri")


def _map_linkedin(it):
    sal = it.get("salary")
    return JobPosting(
        title=it.get("title", "") or "", company=it.get("companyName", "") or "",
        source="apify:linkedin", url=it.get("link") or it.get("applyUrl", "") or "",
        location=it.get("location", "") or "",
        description=it.get("descriptionText") or "",
        seniority_level=it.get("seniorityLevel"), employment_type=it.get("employmentType"),
        salary_text=sal if isinstance(sal, str) else None,
        posted_at=it.get("postedAt"),
        link_verified=True, link_source="apify:linkedin")


def _map_indeed(it):
    if it.get("isExpired"):
        return None
    return JobPosting(
        title=it.get("positionName", "") or "", company=it.get("company", "") or "",
        source="apify:indeed", url=it.get("url") or it.get("externalApplyLink", "") or "",
        location=it.get("location", "") or "",
        description=it.get("description") or "",
        salary_text=it.get("salary") if isinstance(it.get("salary"), str) else None,
        employment_type=it.get("jobType") if isinstance(it.get("jobType"), str) else None,
        posted_at=it.get("postedAt"),
        link_verified=True, link_source="apify:indeed")


PLATFORMS = {
    "naukri": {
        # memo23 returns the FULL JD (epicscrapers gave snippets); cheapest + most-used.
        "actor": "memo23~naukri-scraper",
        "input": lambda titles, loc, lim: {"startUrls": [{"url": _naukri_url(t, loc)} for t in titles],
                                           "maximumJobs": lim},
        "map": _map_naukri,
    },
    "linkedin": {
        "actor": "curious_coder~linkedin-jobs-scraper",
        "input": lambda titles, loc, lim: {"urls": [_linkedin_url(t, loc) for t in titles],
                                           "count": max(10, lim), "scrapeCompany": False},
        "map": _map_linkedin,
    },
    "indeed": {
        "actor": "misceres~indeed-scraper",
        "input": lambda titles, loc, lim: {"startUrls": [{"url": _indeed_url(t, loc)} for t in titles],
                                           "maxItemsPerSearch": lim, "country": "IN"},
        "map": _map_indeed,
    },
}


class ApifyProvider:
    id = "apify"

    def enabled(self, cfg: dict) -> bool:
        sub = (cfg.get("discovery", {}) or {}).get("apify", {}) or {}
        if sub.get("enabled") is False:
            return False
        return bool(os.environ.get("APIFY_TOKEN"))

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            return []
        sub = (cfg.get("discovery", {}) or {}).get("apify", {}) or {}
        platforms = sub.get("platforms", DEFAULT_PLATFORMS)
        actors = sub.get("actors", {})            # optional per-platform actor override
        per = int(sub.get("limit", min(40, query.limit_per_channel)))
        titles = query.titles[:6] or ([query.raw_keywords] if query.raw_keywords else [])
        headers = {"Authorization": f"Bearer {token}"}
        out, errors = [], []

        for plat in platforms:
            spec = PLATFORMS.get(plat)
            if not spec:
                errors.append(f"{plat}: unknown platform"); continue
            actor = actors.get(plat, spec["actor"]).replace("/", "~")
            try:
                r = requests.post(
                    f"{API}/{actor}/run-sync-get-dataset-items",
                    params={"timeout": TIMEOUT, "memory": 1024, "limit": per},
                    json=spec["input"](titles, query.location, per),
                    headers=headers, timeout=TIMEOUT + 40)
                if r.status_code >= 300:
                    errors.append(f"{plat} ({actor}): HTTP {r.status_code} {r.text[:120]}")
                    continue
                items = r.json()
                if isinstance(items, list):
                    for it in items:
                        jp = spec["map"](it)
                        if jp and jp.title:
                            out.append(jp)
            except Exception as e:
                errors.append(f"{plat} ({actor}): {e}")
        self.last_errors = errors
        return out
