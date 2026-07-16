"""Discovery registry — run all enabled channels and report honestly.

Returns the combined raw postings plus a per-channel report (counts + errors).
A channel that errors is recorded in the report; it does NOT get silently turned
into "0 jobs found". The caller can then tell the difference between "discovery
genuinely returned nothing" and "a channel broke".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..progress import emit as _emit
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
                _emit(f"discovery: {p.id} skipped ({after} sufficient, {src_count}≥{trig})")
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
            # Providers record their own per-request/per-tenant errors on `last_errors`.
            errs = list(getattr(p, "last_errors", []) or [])
            if len(jobs) == 0 and errs:                    # 0 results WITH errors = errored, not empty
                _emit(f"discovery: {p.id} errored — 0 results, {len(errs)} failure(s) "
                      f"(e.g. {errs[0][:45]})")
            else:
                _emit(f"discovery: {p.id} {len(jobs)}")
            rep = ChannelReport(p.id, True, count=len(jobs))
            rep.errors = errs
            reports.append(rep)
        except Exception as e:
            _emit(f"discovery: {p.id} errored (fetch failed: {str(e)[:45]})")
            reports.append(ChannelReport(p.id, True, errors=[f"fetch() failed: {e}"]))

    return all_jobs, reports


# ── Discovery health — distinguish a broken run from an honest empty one ──────
# A network failure (Codex's sandbox blocks network by default; being offline)
# makes every channel return 0 — indistinguishable from "no jobs matched" unless
# we look at the recorded errors. This turns the per-channel reports into an
# ok/errored/skipped status + a LOUD, honest verdict when discovery actually broke.
_NET_HINTS = (
    "connection", "timeout", "timed out", "getaddrinfo", "name resolution", "name or service",
    "failed to establish", "max retries", "unreachable", "network", "connection refused",
    "no route to host", "nodename nor servname", "temporary failure",
)


def _looks_unreachable(errors: list[str]) -> bool:
    blob = " ".join(errors).lower()
    return (not errors) or any(h in blob for h in _NET_HINTS)


def _channel_status(r: "ChannelReport") -> str:
    if not r.enabled:
        return "skipped"
    if r.count == 0 and r.errors:            # ran, returned nothing, but recorded failures → errored
        return "errored"
    return "ok"                              # got results, or a genuine clean empty


def discovery_health(reports: list["ChannelReport"]) -> dict:
    """Turn per-channel reports into a status list + an honest `failed` verdict.

    `failed` mirrors run.py's proven rule (total==0 AND some enabled channel
    errored) — i.e. no candidates AND a breakage, never a legitimate empty. The
    message names the cause (unreachable/network vs HTTP errors), flags the keyless
    ATS floor when it's the one that broke, and WARNS that top.md is stale."""
    channels = []
    for r in reports:
        st = _channel_status(r)
        reason = (r.skipped_reason if st == "skipped"
                  else (r.errors[0][:200] if st == "errored" else ""))
        channels.append({"id": r.id, "status": st, "count": r.count,
                         "errors": len(r.errors), "reason": reason})
    enabled = [r for r in reports if r.enabled]
    total = sum(r.count for r in enabled)
    errored = [r for r in enabled if _channel_status(r) == "errored"]
    ats = next((r for r in reports if r.id == "ats"), None)
    ats_errored = bool(ats and ats.enabled and _channel_status(ats) == "errored")
    failed = bool(enabled) and total == 0 and bool(errored)

    reason, message = "", ""
    if failed:
        all_errs = [e for r in errored for e in r.errors]
        if _looks_unreachable(all_errs):
            cause = ('no channel could be reached. This usually means no network access '
                     '(e.g. Codex\'s sandbox blocks network by default — see README "Network access") '
                     'or you\'re offline')
        else:
            cause = "every reachable channel returned an error (HTTP / non-200) — see per-channel reasons"
        reason = ("the keyless ATS floor errored (it needs no key and normally always works)"
                  if ats_errored else "all enabled channels errored")
        message = (f'⚠️ Discovery FAILED: {cause}. This is NOT the same as "no jobs matched" — '
                   f"{reason}. data/results/top.md was NOT updated — any file there is from an "
                   "earlier run, not this one.")
    return {"channels": channels, "failed": failed, "reason": reason, "message": message,
            "errored": [r.id for r in errored], "ats_errored": ats_errored}
