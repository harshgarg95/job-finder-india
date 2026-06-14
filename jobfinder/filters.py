"""Cheap pre-scoring filters — COST optimizations, not the judgment.

Per the build plan (docs/research/05 §1.3): a cheap keyword pre-filter cuts the
candidate set before the expensive holistic LLM pass. It must be PERMISSIVE —
better to over-include and let the honest scorer reject a job with a cited
reason than to silently drop a good one here. The real fit decision is the
rubric's, never this filter's.
"""

from __future__ import annotations

import re

from .schema import JobPosting

# Indian places (and "india"); "remote"/"hybrid"/"anywhere" handled separately.
_INDIA_TOKENS = [
    "india", "bharat",
    "bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "delhi", "new delhi",
    "gurgaon", "gurugram", "noida", "chennai", "kolkata", "ahmedabad", "jaipur",
    "indore", "kochi", "coimbatore", "chandigarh", "trivandrum", "thiruvananthapuram",
    "ncr", "telangana", "karnataka", "maharashtra", "tamil nadu",
]

# Foreign regions: a "remote" tied to one of these is NOT India-eligible.
_FOREIGN_TOKENS = [
    "united states", "u.s.", "usa", " us ", "us-", "-us", "us,", " us)", "(us",
    "united kingdom", " uk", "uk ", "canada", "france", "germany", "netherlands",
    "spain", "mexico", "singapore", "dubai", "uae", "australia", "ireland",
    "poland", "brazil", "denmark", "sweden", "emea", "americas", "apac", "europe",
    " eu ", "| eu", "eu |", "china", "japan", "tokyo", "italy", "cyprus", "argentina",
    "buenos aires", "san francisco", "new york", "seattle", "london", "toronto",
    "chicago", "atlanta", "foster city", "california", " ca", "virginia", "ohio",
    "georgia", "arizona", "texas", "boston", "austin", "denver",
    # US state abbreviations commonly seen in ATS location strings
    " ny", " sf", " sea", " va", " wa", " tx", " il",
]
_REMOTE_TOKENS = ["remote", "anywhere", "work from home", "wfh"]


def location_ok(job: JobPosting, profile: dict) -> bool:
    """Keep India-based and India-eligible-remote jobs; drop clearly-foreign ones.

    Permissive on ambiguity (blank -> keep, let the scorer judge), but a job
    whose location names a foreign place — including a foreign-tied 'remote'
    (e.g. 'US - Remote', 'Remote - France') — is dropped. The scorer still
    double-checks location and can cite a mismatch on anything that slips
    through."""
    loc = (job.location or "").lower().strip()
    if not loc:
        return True  # unknown -> let the scorer judge
    remote_ok = (profile.get("location", {}) or {}).get("remote_ok", True)

    has_india = any(tok in loc for tok in _INDIA_TOKENS)
    has_foreign = any(tok in loc for tok in _FOREIGN_TOKENS)
    is_remote = any(tok in loc for tok in _REMOTE_TOKENS) or bool(job.remote)

    if has_india:
        return True                       # India named -> keep (even if multi-region)
    if has_foreign:
        return False                      # foreign named, India not -> drop
    if is_remote:
        return remote_ok                  # unscoped remote -> keep if user allows remote
    return False                          # names some non-India place, not remote


def _keywords_from_profile(profile: dict, query_titles: list[str]) -> list[str]:
    kws: set[str] = set()
    for t in query_titles:
        for tok in re.split(r"[^a-z0-9]+", t.lower()):
            if len(tok) >= 3:
                kws.add(tok)
    tr = profile.get("target_roles", {}) or {}
    for t in tr.get("primary", []) or []:
        for tok in re.split(r"[^a-z0-9]+", t.lower()):
            if len(tok) >= 3:
                kws.add(tok)
    for a in tr.get("archetypes", []) or []:
        for tok in re.split(r"[^a-z0-9]+", (a.get("name", "")).lower()):
            if len(tok) >= 3:
                kws.add(tok)
    fn = profile.get("function", {}) or {}
    for t in fn.get("in_scope", []) or []:
        for tok in re.split(r"[^a-z0-9]+", t.lower()):
            if len(tok) >= 4:
                kws.add(tok)
    # generic role-family terms so we don't miss adjacent titles
    kws.update(["ai", "ml", "genai", "llm", "data", "product", "program",
                "project", "delivery", "implementation", "manager", "engineer",
                "consultant", "architect", "analyst", "lead", "automation"])
    # stop-words that shouldn't count as signal
    for noise in ("the", "and", "for", "with", "ai/ml"):
        kws.discard(noise)
    return sorted(kws)


def keyword_prefilter(jobs: list[JobPosting], profile: dict, query_titles: list[str]) -> list[JobPosting]:
    """Keep jobs whose title or description contains any profile keyword.
    Permissive: this only removes obvious non-matches (sales, accounting, etc.)."""
    kws = _keywords_from_profile(profile, query_titles)
    kept = []
    for j in jobs:
        hay = f"{j.title}\n{j.description}".lower()
        if any(k in hay for k in kws):
            kept.append(j)
    return kept
