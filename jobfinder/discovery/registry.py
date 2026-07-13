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
from .adzuna import AdzunaProvider
from .jsearch import JSearchProvider
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
    """Channel priority (all feed the same dedup + India/keyword filter + cap-40
    prescreen funnel). ATS is the always-on free floor; Adzuna is the co-primary
    India-native channel; JSearch is a gap-fill SUPPLEMENT (runs only when Adzuna
    is thin); Google Jobs is an optional SerpAPI alt; Apify is demoted to an
    opt-in deep mode (off by default)."""
    tenants = cfg.get("ats_tenants", [])
    return [
        AtsProvider(tenants),        # 0 — always-on free floor
        AdzunaProvider(),            # 1 — co-primary India-native (free, keyed)
        JSearchProvider(),           # 2 — supplement, gap-fill only (scarcer free tier)
        GoogleJobsProvider(),        # 3 — optional SerpAPI alt (off by default)
        ApifyProvider(),             # 4 — demoted deep mode (off by default)
    ]


def _trigger_below(cfg: dict, channel: str, default: int = 40) -> int:
    return int((((cfg.get("run", {}) or {}).get("discovery", {}) or {})
                .get(channel, {}) or {}).get("trigger_below", default))


def discover(query: Query, cfg: dict) -> tuple[list[JobPosting], list[ChannelReport]]:
    providers = build_providers(cfg)
    all_jobs: list[JobPosting] = []
    reports: list[ChannelReport] = []
    counts: dict[str, int] = {}          # id -> jobs returned (only for channels that ran)

    for p in providers:
        # ── Gap-fill gate: a channel with `gap_fill_after = "<id>"` runs ONLY when
        #    that upstream channel came back thin (below its trigger). If the
        #    upstream didn't run at all (disabled / quota-exhausted / errored),
        #    counts has no entry → the gap-filler runs (it's the fallback). ──
        after = getattr(p, "gap_fill_after", None)
        if after:
            src_count = counts.get(after)
            trig = _trigger_below(cfg, p.id)
            if src_count is not None and src_count >= trig:
                reports.append(ChannelReport(
                    p.id, False,
                    skipped_reason=f"{after} sufficient ({src_count} ≥ {trig}) — quota saved"))
                continue

        try:
            on = p.enabled(cfg)
        except Exception as e:
            reports.append(ChannelReport(p.id, False, errors=[f"enabled() failed: {e}"]))
            continue
        if not on:
            reasons = {
                "adzuna": "set ADZUNA_APP_ID + ADZUNA_APP_KEY in .env + enable in config/sources.yml",
                "jsearch": "set JSEARCH_API_KEY in .env + enable in config/sources.yml",
                "google_jobs": "set SERPAPI_KEY in .env + enable in config/sources.yml",
                "apify": "opt-in deep mode — set APIFY_TOKEN in .env + enabled: true in config/sources.yml",
                "ats": "no tenants configured",
            }
            # A provider may explain its own skip (e.g. quota reached) via ._skip.
            skip = getattr(p, "_skip", None) or reasons.get(p.id, "disabled")
            reports.append(ChannelReport(p.id, False, skipped_reason=skip))
            continue
        try:
            jobs = p.fetch(query, cfg)
            all_jobs.extend(jobs)
            counts[p.id] = len(jobs)
            rep = ChannelReport(p.id, True, count=len(jobs))
            # Providers record their own per-request/per-tenant errors on `last_errors`.
            rep.errors = list(getattr(p, "last_errors", []) or [])
            reports.append(rep)
        except Exception as e:
            reports.append(ChannelReport(p.id, True, errors=[f"fetch() failed: {e}"]))

    return all_jobs, reports
