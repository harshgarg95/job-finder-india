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

import requests

from .link_resolver import UA, host_of

TIMEOUT = 15
# Hosts that block bots / need login → can't deep-fetch; keep the snippet.
UNFETCHABLE = ("linkedin.com", "naukri.com", "glassdoor.")


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


def enrich(job, min_len: int = 4000) -> bool:
    """If a job's description looks like a snippet (shorter than a full JD) and
    its link is fetchable, replace it with the full JD. Returns True if enriched.
    Threshold is generous (4000) because Google Jobs snippets routinely run
    1.5–4k chars yet omit the requirements section."""
    if len((job.description or "")) >= min_len:
        return False
    full = fetch_full_jd(job.url)
    if full and len(full) > len(job.description or "") * 1.1:
        job.description = full
        return True
    return False
