"""Resolve and verify Google Jobs apply links to a REAL job/company page.

Google Jobs' `apply_options` frequently point at low-value aggregators or dead
pages (the user's exact complaint: "random other job platforms ... not true or
don't lead to any job description page"). This module makes a listing
*trustworthy* before it reaches the user:

  1. RANK candidate links by source quality:
       employer (company domain / known ATS) > major platform (LinkedIn, Naukri)
       > acceptable board (Indeed, Wellfound, Instahyre, Foundit) > junk aggregator
  2. VERIFY the best link actually resolves over HTTP, distinguishing:
       - a legit platform that blocks bots (LinkedIn 999, Naukri 403) = REAL, keep
       - a genuinely dead (404/410) / parked / junk-aggregator page          = drop
  3. RETURN the best verified canonical link + a source label + verified flag,
     preferring the employer's own page ("go deeper, find its website"). If
     nothing verifies, the listing is flagged unverified — never fabricated.

No key needed for verification — it's plain HTTP. (The richer apply-option
lookup via SerpAPI's google_jobs_listing endpoint is optional and lives in
google_jobs.py.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

# Honest identifying UA — the project's polite-client rule: we say who we are on
# every request (page fetches, liveness checks, and the ATS JSON branches alike).
# Measured before switching (2026-07-23, n=15 pool URLs, browser-UA vs this):
# hit-rate delta ZERO — the spoofed browser UA bought nothing.
UA = "job-finder-india/1.0 (+https://github.com/harshgarg95/job-finder-india)"
TIMEOUT = 12

# Known ATS / employer-hosting domains → the canonical "company page" tier.
EMPLOYER_HOSTS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com", "workday.com",
    "smartrecruiters.com", "icims.com", "jobvite.com", "eightfold.ai", "bamboohr.com",
    "recruitee.com", "workable.com", "breezy.hr", "successfactors.com", "taleo.net",
    "oraclecloud.com", "phenom.com", "gem.com", "ripplinghq.com", "rippling.com",
)
PLATFORM_HOSTS = ("linkedin.com", "naukri.com")
BOARD_HOSTS = ("indeed.com", "wellfound.com", "angel.co", "instahyre.com", "hirist.com",
               "hirist.tech", "foundit.in", "builtin.com", "ycombinator.com", "glassdoor.")
# Low-value aggregators / re-posters / free-host spam that don't lead to a real
# JD or company page (the user's exact complaint).
JUNK_HOSTS = ("talent.com", "jooble.org", "trabajo.org", "jobrapido.com", "bebee.com",
              "lensa.com", "whatjobs.com", "careerjet.", "adzuna.", "neuvoo.", "jobcase.com",
              "simplyhired.", "shine.com", "timesjobs.com", "expertini.", "recruit.net",
              "jobsora.com", "smartjobsearcher.", "jobspresso.", "jobtome.", "jobleads.",
              "clickjobs.io", "snagajob.", "kit.com", "mitula.", "trovit.", "ai-search.io",
              "grabjobs.", "jobgoround", "jobsxl", "joborondo",
              # free-hosting providers spammers repost jobs on (checked before the
              # employer-site name match, so a company name in a free-host
              # subdomain can't masquerade as the real careers site)
              "infinityfree.me", "000webhost", "byethost", "epizy.com", "rf.gd",
              "rf.gd.", "free.nf", "kesug.com", "wuaze.com", "great-site.net",
              "liveblog365.com", "rf.gd", "infy.uk", "42web.io", "rf.gd.",
              "iitjobs.com", "jobted.", "joborondo")

# Anti-bot / rate-limit codes that DON'T mean the posting is gone.
_ANTIBOT = {401, 403, 429, 503, 999}
_DEAD = {404, 410}


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _distinctive_token(url: str) -> str:
    """A job-id-like token (long digits or uuid-ish) from the URL path. ATS
    soft-404s redirect invalid jobs to the board and DROP this token, so its
    survival across redirects is a reliable 'the posting still exists' signal."""
    path = urlparse(url).path
    toks = re.findall(r"[0-9a-fA-F]{8,}|\d{5,}", path)
    return toks[-1].lower() if toks else ""


def _tier(url: str, company: str) -> tuple[int, str]:
    """Lower tier = better source. Unknown sources are NOT trusted (tier 5):
    only the employer's own page, a known ATS, LinkedIn/Naukri, or a real board
    count as verifiable. Google-search/share links and free-host spam are junk."""
    h = host_of(url)
    if not h:
        return (9, "invalid")
    low = url.lower()
    # Google search / share links are not job pages — the #1 junk pattern.
    if h in ("google.com", "www.google.com") or "google.com/search" in low or "/search?" in low:
        return (4, "google-search")
    if any(h == j or h.endswith("." + j) or j in h for j in JUNK_HOSTS):
        return (4, "junk")
    if any(h == e or h.endswith("." + e) for e in EMPLOYER_HOSTS):
        return (1, "employer-ats")
    # company's own domain: a company-name token appears in the host
    for tok in re.split(r"[^a-z0-9]+", (company or "").lower()):
        if len(tok) >= 4 and tok in h and not any(p in h for p in PLATFORM_HOSTS + BOARD_HOSTS):
            return (1, "employer-site")
    if any(p in h for p in PLATFORM_HOSTS):
        return (2, "linkedin" if "linkedin" in h else "naukri")
    if any(b in h for b in BOARD_HOSTS):
        return (3, "board")
    return (5, "unknown")  # unknown domain → unverified by default (don't trust)


@dataclass
class Resolved:
    url: str
    source: str          # employer-ats | employer-site | linkedin | naukri | board | other | junk | unverified
    verified: bool
    status: str          # ok | trusted-blocked | dead | junk | unreachable | none
    final_url: str = ""


def verify_link(url: str, company: str = "", title: str = "") -> Resolved:
    """HTTP-check one URL. Trusted platforms that block bots count as real;
    dead/parked/junk pages do not."""
    tier, label = _tier(url, company)
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"},
                         timeout=TIMEOUT, allow_redirects=True, stream=True)
        code = r.status_code
        final = r.url
        r.close()
        final_tier, final_label = _tier(final, company)

        # Verification relies on DETERMINISTic structural signals, not page text
        # (a chunked body scan is flaky: "apply"/"responsibilities" can fall
        #  outside the read window, and "404" appears in many valid pages' JS).
        #
        # Soft-404: ATS platforms answer invalid/expired jobs with HTTP 200 but
        # redirect to the board (dropping the job id) and/or append ?error=true.
        if re.search(r"[?&]error=(?:true|1)\b", final, re.I):
            return Resolved(url, "dead", False, "dead", final)
        tok = _distinctive_token(url)
        if tok and tok not in final.lower():
            return Resolved(url, "dead", False, "dead", final)  # redirected off the posting
        if code in _DEAD:
            return Resolved(url, "dead", False, "dead", final)
        if final_tier == 4:  # junk host or google-search/share link
            return Resolved(url, final_label, False, "junk", final)
        if code in _ANTIBOT:
            # trusted platform/employer that blocks bots -> the posting is real
            if final_tier <= 3:
                return Resolved(final, final_label, True, "trusted-blocked", final)
            return Resolved(url, final_label, False, "unreachable", final)
        if 200 <= code < 400:
            if final_tier >= 5:  # unknown domain: reachable, but we can't trust it's a real JD
                return Resolved(url, "unknown-source", False, "unverified", final)
            return Resolved(final, final_label, True, "ok", final)
        return Resolved(url, final_label, False, "unreachable", final)
    except requests.RequestException:
        return Resolved(url, label, False, "unreachable", "")


def resolve_best(apply_options: list[dict], company: str = "", title: str = "",
                 verify: bool = True) -> Resolved:
    """Pick the best apply link, preferring the employer's own page, and verify it.

    `apply_options`: list of {"title": source_name, "link": url} from Google Jobs.
    Walks candidates best-source-first; returns the first that verifies (preferring
    employer-tier so we surface the company's real page). If none verify, returns
    the best-tier candidate flagged unverified (caller decides to drop/flag)."""
    cands = []
    seen = set()
    for opt in apply_options or []:
        url = (opt or {}).get("link") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        tier, label = _tier(url, company)
        cands.append((tier, url, label))
    if not cands:
        return Resolved("", "unverified", False, "none")
    cands.sort(key=lambda c: c[0])

    if not verify:
        t, url, label = cands[0]
        return Resolved(url, label, False, "none")

    first_seen = None
    for tier, url, label in cands:
        if tier >= 4:  # junk + unknown domains: never trusted, skip the verify pass
            continue
        res = verify_link(url, company, title)
        if first_seen is None:
            first_seen = res
        if res.verified:
            return res
    # nothing trusted verified — flag unverified (caller drops it from the shortlist)
    if first_seen:
        return first_seen
    best = cands[0]
    return Resolved(best[1], best[2] if best[0] >= 4 else "unverified", False, "unverified")
