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

# India/foreign/remote classification lives in ONE place — jobfinder/location.py
# (`classify`). The stale per-module token lists that used to live here are gone:
# they were what let a foreign role with the channel's `remote` flag set (Munich,
# "Remote - Colombia") slip through discovery.


def location_ok(job: JobPosting, profile: dict) -> bool:
    """Keep India-based and India-eligible-remote jobs; drop clearly-foreign ones.

    Permissive on ambiguity (blank -> keep, let the scorer judge), but a job
    whose location names a foreign place — including a foreign-tied 'remote'
    (e.g. 'US - Remote', 'Remote - France') — is dropped. The scorer still
    double-checks location and can cite a mismatch on anything that slips
    through."""
    from .location import classify        # ONE source of truth (same call the gate uses)
    if (profile.get("location", {}) or {}).get("willing_to_relocate"):
        return True                       # relocation-open -> no foreign filtering at discovery
    # Drop ONLY a clearly-foreign location. "unknown" and "remote_india_eligible" MUST
    # pass: an unknown location has to reach the gate's location_unverified →
    # couldn't-verify path (surfaced, not hidden at discovery).
    return classify(job.location) != "foreign"


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
