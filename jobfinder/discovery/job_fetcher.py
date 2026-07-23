"""Deep-fetch the FULL job description from a verified job/company page.

Google Jobs often returns a short *snippet*, not the full JD — so the scorer
misses buried gating requirements ("1 year software development", "3 years
SAFe"). For a shortlist candidate we fetch its verified page and replace the
snippet with the full text, so the rubric scores on the REAL requirements.

Only fetches pages we can actually read: company sites / ATS / real boards.
LinkedIn & Naukri block bots, so we keep their snippet (and the rubric notes the
requirements may be incomplete). Never fabricates text; returns None on failure.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import requests

from .link_resolver import UA, host_of

TIMEOUT = 15
# Hosts that block bots / need login → can't deep-fetch; keep the snippet.
UNFETCHABLE = ("linkedin.com", "naukri.com", "glassdoor.")
# A description at/above this length counts as a full JD; below it is snippet
# territory (generous — Google Jobs snippets run 1.5–4k chars yet omit the
# requirements section). Shared with cmd_enrich's jd_source flag.
FULL_JD_MIN = 4000

# ── ATS-aware JD fetch (Workday CXS detail · SmartRecruiters posting API) ─────
# Their careers pages are JS SPAs, so the generic HTTP fetch gets nothing — but
# both serve the JD as public keyless JSON (SmartRecruiters: a documented public
# API; Workday CXS: the same endpoint its own careers SPA calls). Polite-client
# rules, non-negotiable: an honest identifying User-Agent (never a spoofed
# browser), paced sequential requests, ONE attempt — and a 403/429/anti-bot
# answer is a "no": fall through to honest no_jd, never around a block.
_API_UA = "job-finder-india/1.0 (+https://github.com/harshgarg95/job-finder-india)"
_API_HEADERS = {"User-Agent": _API_UA, "Accept": "application/json"}
_API_MIN_INTERVAL = 1.0                 # seconds between detail fetches — no hammering
_last_api_call = 0.0


class _ApiBlocked(Exception):
    """The host answered 403/429 — treat as a refusal, not an obstacle."""


def _pace() -> None:
    global _last_api_call
    wait = _API_MIN_INTERVAL - (time.monotonic() - _last_api_call)
    if wait > 0:
        time.sleep(wait)
    _last_api_call = time.monotonic()


def _api_get_json(url: str) -> dict | None:
    """One polite GET. 403/429 → _ApiBlocked (a 'no'); other non-200 / bad JSON →
    None (caller falls through to the generic path). Never retries."""
    _pace()
    r = requests.get(url, headers=_API_HEADERS, timeout=TIMEOUT)
    if r.status_code in (403, 429):
        raise _ApiBlocked(f"HTTP {r.status_code}")
    if r.status_code != 200:
        return None
    try:
        data = r.json()
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _fetch_workday_jd(url: str) -> str | None:
    """JD via Workday's CXS job-detail JSON, derived from the public job URL:
    https://{host}/{site}/job/{...}  →  https://{host}/wday/cxs/{tenant}/{site}/job/{...}
    (tenant = host prefix). Verified live 2026-07-23 (Genpact: 4,170-char JD where
    the rendered page yields nothing over HTTP)."""
    p = urlparse(url)
    parts = [s for s in (p.path or "").split("/") if s]
    if len(parts) < 3 or "job" not in parts:
        return None
    tenant, site = p.netloc.split(".")[0], parts[0]
    data = _api_get_json(f"https://{p.netloc}/wday/cxs/{tenant}/{site}/{'/'.join(parts[1:])}")
    if not data:
        return None
    text = _clean((data.get("jobPostingInfo") or {}).get("jobDescription") or "")
    return text if len(text) >= 600 else None       # same floor as fetch_full_jd — no thin passes


def _fetch_smartrecruiters_jd(url: str) -> str | None:
    """JD via SmartRecruiters' documented public Posting API:
    https://api.smartrecruiters.com/v1/companies/{company}/postings/{id}
    (company + id parsed from the public job URL). Verified live 2026-07-23."""
    m = re.search(r"smartrecruiters\.com/([^/?#]+)/(\d{6,})", url)
    if not m:
        return None
    data = _api_get_json(f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}")
    if not data:
        return None
    sections = (data.get("jobAd") or {}).get("sections") or {}
    text = _clean("\n\n".join((v or {}).get("text") or "" for v in sections.values()
                              if isinstance(v, dict)))
    return text if len(text) >= 600 else None


def _clean(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()
        text = soup.get_text("\n")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _fetch_playwright(url: str) -> str | None:
    """Render a JS-heavy career page in headless Chromium and extract its text.
    Used only as a fallback when plain HTTP yields too little. Optional —
    returns None if Playwright/Chromium isn't installed."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)  # let client-side JD render
            html = page.content()
            browser.close()
        return _clean(html)
    except Exception:
        return None


def fetch_full_jd(url: str) -> str | None:
    """Return the full JD text from `url`, or None if not fetchable/too thin.
    Tries plain HTTP first; falls back to a headless browser for JS-rendered
    pages (Workday-style SPAs)."""
    if not url:
        return None
    h = host_of(url)
    if any(u in h for u in UNFETCHABLE):
        return None
    # ATS-aware branch first: these hosts serve the JD as public keyless JSON,
    # while their rendered pages are empty SPAs over plain HTTP.
    try:
        if "myworkdayjobs.com" in h:
            t = _fetch_workday_jd(url)
            if t:
                return t[:12000]
        elif "smartrecruiters.com" in h:
            t = _fetch_smartrecruiters_jd(url)
            if t:
                return t[:12000]
    except _ApiBlocked:
        return None          # the host said no — honest no_jd, never around a block
    except Exception:        # noqa: BLE001 — guarded fallback: today's path unchanged
        pass
    text = None
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"},
                         timeout=TIMEOUT, allow_redirects=True)
        if r.status_code < 400 and r.text:
            text = _clean(r.text)
    except requests.RequestException:
        text = None
    # If HTTP got little (JS-rendered page), try a real browser.
    if not text or len(text) < 800:
        rendered = _fetch_playwright(url)
        if rendered and len(rendered) > len(text or ""):
            text = rendered
    return text[:12000] if text and len(text) >= 600 else None


def enrich(job, min_len: int = FULL_JD_MIN) -> bool:
    """If a job's description looks like a snippet (shorter than a full JD) and
    its link is fetchable, replace it with the full JD. Returns True if enriched.
    Threshold is generous (FULL_JD_MIN) because Google Jobs snippets routinely
    run 1.5–4k chars yet omit the requirements section."""
    if len((job.description or "")) >= min_len:
        return False
    full = fetch_full_jd(job.url)
    if full and len(full) > len(job.description or "") * 1.1:
        job.description = full
        return True
    return False
