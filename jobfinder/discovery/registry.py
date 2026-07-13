"""Discovery registry — run all enabled channels and report honestly.

Returns the combined raw postings plus a per-channel report (counts + errors).
A channel that errors is recorded in the report; it does NOT get silently turned
into "0 jobs found". The caller can then tell the difference between "discovery
genuinely returned nothing" and "a channel broke".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import JobPosting
from .ats import AtsProvider
from .google_jobs import GoogleJobsProvider
from .apify import ApifyProvider
from .base import Query


@dataclass
class ChannelReport:
    id: str
    enabled: bool
    count: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_reason: str = ""


def build_providers(cfg: dict) -> list:
    tenants = cfg.get("ats_tenants", [])
    return [
        AtsProvider(tenants),
        GoogleJobsProvider(),
        ApifyProvider(),
    ]


def discover(query: Query, cfg: dict) -> tuple[list[JobPosting], list[ChannelReport]]:
    providers = build_providers(cfg)
    all_jobs: list[JobPosting] = []
    reports: list[ChannelReport] = []

    for p in providers:
        try:
            on = p.enabled(cfg)
        except Exception as e:
            reports.append(ChannelReport(p.id, False, errors=[f"enabled() failed: {e}"]))
            continue
        if not on:
            reasons = {
                "google_jobs": "set SERPAPI_KEY in .env + enable in config/sources.yml",
                "apify": "set APIFY_TOKEN in .env + enable in config/sources.yml (Naukri + LinkedIn + Indeed)",
                "ats": "no tenants configured",
            }
            # A provider may explain its own skip (e.g. apify auto-paused) via ._skip.
            skip = getattr(p, "_skip", None) or reasons.get(p.id, "disabled")
            reports.append(ChannelReport(p.id, False, skipped_reason=skip))
            continue
        try:
            jobs = p.fetch(query, cfg)
            all_jobs.extend(jobs)
            rep = ChannelReport(p.id, True, count=len(jobs))
            # AtsProvider records per-tenant errors on itself
            rep.errors = list(getattr(p, "last_errors", []) or [])
            reports.append(rep)
        except Exception as e:
            reports.append(ChannelReport(p.id, True, errors=[f"fetch() failed: {e}"]))

    return all_jobs, reports
