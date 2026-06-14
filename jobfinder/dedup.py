"""Deduplication across discovery channels.

A job can surface on an ATS feed and again via Google Jobs. We collapse them by
stable id (URL-based) and by a (company, normalized-title) near-key, keeping the
record with the richest description so the scorer sees the fullest JD.
"""

from __future__ import annotations

import re

from .schema import JobPosting


def _norm_title(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"\(.*?\)", " ", t)              # drop "(Remote)", "(f/m/d)"
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def dedupe(jobs: list[JobPosting]) -> list[JobPosting]:
    """Collapse duplicates. Primary key is (company, normalized-title) so the same
    role surfacing on an ATS feed and again via Google Jobs (different URLs)
    merges into one. When company is missing, fall back to the URL-based id. On a
    collision, keep the record with the richer (longer) description."""
    by_key: dict[str, JobPosting] = {}
    order: list[str] = []
    for j in jobs:
        company = _norm_title(j.company)
        title = _norm_title(j.title)
        key = f"{company}::{title}" if company and title else (j.id if j.url else f"{company}::{title}")
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = j
            order.append(key)
        elif len(j.description or "") > len(existing.description or ""):
            by_key[key] = j
    return [by_key[k] for k in order]
