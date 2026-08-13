#!/usr/bin/env python3
"""Discovery smoke — daily CI canary against the real free-channel APIs.

Run by .github/workflows/discovery-smoke.yml (daily cron + manual dispatch).
Purpose: catch API drift (the JSearch v1→v5 / renamed-endpoint class of
breakage) within a day via GitHub's failure email — BEFORE a user's real run
silently degrades to fewer channels.

What it does, per channel — the minimum real traffic that proves the shape:
  • ats     — for EACH ATS family in config/companies_india.yml (greenhouse,
              lever, ashby, smartrecruiters, workday) fetch ONE tenant board
              through the production AtsProvider path (2nd tenant only as
              fallback). A family fails only if every tried tenant fails.
  • adzuna  — ONE search request (max_requests_per_run forced to 1).
  • jsearch — ONE search request (same). Keyed channels are exercised whenever
              their key is present, regardless of config/sources.yml opt-ins —
              this tests API health, not the user's channel preferences.

"Changed response shape" is asserted at the contract level: the response must
still parse into >= 1 well-formed JobPosting (non-empty title + company + url;
for the keyed channels also >= 1 posting with a non-empty location, since
location feeds the India gate). An API that renames fields or moves the jobs
list yields zero well-formed postings from a 200 — and fails the smoke.

Statuses:
  OK    — channel reachable, response parses               (pass)
  SKIP  — API key not configured (repo secret missing)     (warning, pass)
  QUOTA — provider free tier exhausted / rate-limited      (warning, pass —
          real-tier exhaustion is not API drift)
  WARN  — transient upstream WEATHER on ONE keyed channel  (warning, pass) —
          a 5xx, a timeout / connection error, or a 200 that parsed but gave
          empty/degraded data. Not our code, not drift. See classify_keyed().
  FAIL  — real breakage: exit 1 → GitHub's failure email.

WARN vs FAIL policy (why the canary stopped crying wolf): the daily smoke kept
hard-failing on transient paid-API hiccups (jsearch empty-location 27 Jul, jsearch
empty-results 08 Aug, adzuna 503 13 Aug, jsearch empty-location again 13 Aug) while
`ats` — the keyless floor — passed every time. Those are third-party weather, not
drift. So a SINGLE keyed channel hitting a transient condition (5xx / empty data)
while ats is healthy now WARNs and the run PASSES. The signals we cannot lose still
hard-FAIL (see decide()): ats down, ALL keyed channels down at once, any 4xx/parse
error (auth/404/drift). Persistence escalation (a WARN that recurs across N daily
runs → FAIL) is the intended backstop but needs cross-run state — see the note in
decide(); it is a follow-up that touches the workflow file, out of THIS change.

Free-tier cost of the daily run: ~30 Adzuna + ~30 JSearch requests/month
(of ~250 and ~200 free) + a handful of keyless ATS calls. No Apify, no SerpAPI.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from jobfinder.discovery.adzuna import AdzunaProvider  # noqa: E402
from jobfinder.discovery.ats import AtsProvider  # noqa: E402
from jobfinder.discovery.base import Query  # noqa: E402
from jobfinder.discovery.jsearch import JSearchProvider  # noqa: E402
from jobfinder.run import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))  # local runs; in CI, secrets are already in env

QUERY = Query(titles=["software engineer"], location="India", limit_per_channel=5)
# Force exactly ONE request per keyed channel (the whole point of a smoke).
CFG = {"run": {"discovery": {"adzuna": {"max_requests_per_run": 1},
                             "jsearch": {"max_requests_per_run": 1}}}}
TENANTS_PER_FAMILY = 2          # 2nd tenant is a fallback, tried only if the 1st fails
WORKDAY_SMOKE_LIMIT = 20        # don't pull a 150-job board for a shape check

results: list[dict] = []        # {channel, status, detail}


def well_formed(jobs: list) -> list:
    return [j for j in jobs if (j.title or "").strip() and (j.url or "").strip()
            and (j.company or "").strip()]


def record(channel: str, status: str, detail: str) -> None:
    results.append({"channel": channel, "status": status, "detail": detail})
    icon = {"OK": "✅", "SKIP": "⏭️", "QUOTA": "🟡", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"{icon} {channel:<10} {status:<6} {detail}")
    if status == "FAIL":
        print(f"::error title=discovery-smoke {channel}::{detail}")
    elif status in ("SKIP", "QUOTA", "WARN"):
        print(f"::warning title=discovery-smoke {channel}::{detail}")


# ── ats: one tenant per family through the production provider path ──────────
def smoke_ats() -> None:
    path = os.path.join(ROOT, "config", "companies_india.yml")
    tenants = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("companies") or []
    families: dict[str, list[dict]] = {}
    for t in tenants:
        families.setdefault(t.get("ats", "?"), []).append(t)
    if not families:
        record("ats", "FAIL", f"no tenants parsed from {path} — file moved or shape changed")
        return

    broken: list[str] = []
    detail: list[str] = []
    for fam in sorted(families):
        fam_ok = False
        errs: list[str] = []
        for t in families[fam][:TENANTS_PER_FAMILY]:
            t = {**t, "limit": min(int(t.get("limit", WORKDAY_SMOKE_LIMIT)), WORKDAY_SMOKE_LIMIT)}
            p = AtsProvider([t])
            jobs = well_formed(p.fetch(QUERY, {}))
            if jobs and not p.last_errors:
                detail.append(f"{fam}:{t['slug']} {len(jobs)} jobs")
                fam_ok = True
                break                      # family proven — don't spend the fallback call
            errs.append(f"{t['slug']}: " + ("; ".join(p.last_errors) if p.last_errors
                        else "0 well-formed postings (shape drift?)"))
        if not fam_ok:
            broken.append(f"{fam} [{' | '.join(errs)}]")
    if broken:
        record("ats", "FAIL", "family broken: " + " · ".join(broken))
    else:
        record("ats", "OK", " · ".join(detail))


# ── keyed channels: classify one channel's result, WARN weather vs FAIL breakage ─
KEYED_CHANNELS = ("adzuna", "jsearch")
_HTTP_CODE_RE = re.compile(r"HTTP\s+(\d{3})")
# Transport-level failures with NO HTTP response — timeouts and connection errors
# (DNS / refused / reset / 'Max retries exceeded'). Same weather class as a 5xx.
_TRANSIENT_NET_RE = re.compile(
    r"timed?\s*out|timeout|connection|max retries|failed to establish|getaddrinfo|"
    r"name or service not known|temporary failure in name resolution|network is unreachable",
    re.I)


def classify_keyed(name: str, jobs: list, errors: list) -> tuple[str, str]:
    """Map one keyed channel's (jobs, last_errors) to a status. THE FAIL/WARN line:

    Transient upstream WEATHER → WARN (passes as an isolated single-channel blip):
      • HTTP 5xx — server-side, not our code, not drift.
      • a transport error with NO HTTP response — a timeout or connection error
        (DNS / refused / reset). Same weather class as a 5xx.
      • a 200 that PARSED but yielded no usable data: 0 well-formed postings, OR
        postings whose locations are all empty. Degraded upstream *data*, not a
        changed *shape*.

    Real BREAKAGE → FAIL (signals we cannot lose):
      • a 4xx (auth / 404 / bad request → secrets or an endpoint rename, e.g. the
        v1→v5 break which 404s).
      • a JSON *parse* error (a 200 with an unparseable / HTML body → shape drift),
        or any other unrecognized error.

    Decision #1 — distinguishing 'changed shape (FAIL)' from 'valid-but-empty
    (WARN)': the reliable structural signal is whether the body PARSED. An
    unparseable 200 raises inside the provider and lands in `errors` → FAIL here.
    A body that is valid JSON but whose jobs *container* was renamed parses
    cleanly and yields 0 postings — indistinguishable from genuinely-empty results
    from the mapped output alone (the raw payload isn't available without touching
    the provider modules, which are out of scope). So that one case WARNs in a
    single run; a *persistent* renamed container is meant to be escalated by the
    persistence backstop (decide()'s note). Note the realistic drift — a renamed
    ENDPOINT — 404s and is FAILed here immediately.

    When an HTTP response arrived, the STATUS CODE decides (not the body text — a
    4xx error page could itself contain the word 'timeout'); only when there is NO
    HTTP status do the transport-error markers apply.
    """
    errors = errors or []
    if any("quota" in e.lower() or "rate limit" in e.lower() for e in errors):
        return "QUOTA", "free tier exhausted / rate-limited — not API drift; " + "; ".join(errors)
    if errors:
        joined = "; ".join(errors)
        codes = [int(m.group(1)) for e in errors for m in [_HTTP_CODE_RE.search(e)] if m]
        if codes:                                  # an HTTP response arrived → the status decides
            if all(500 <= c <= 599 for c in codes):
                return "WARN", "transient upstream error (HTTP 5xx) — weather, passes; " + joined
            return "FAIL", joined                  # any 4xx → auth / 404 / real drift
        if _TRANSIENT_NET_RE.search(joined):       # no HTTP status → transport error
            return "WARN", "transient network error (timeout / connection) — weather, passes; " + joined
        return "FAIL", joined                      # JSON parse error / unknown → real breakage
    ok = well_formed(jobs)
    with_loc = [j for j in ok if (j.location or "").strip()]
    if not ok:
        return "WARN", (f"200 OK and parsed, but 0 well-formed postings (raw jobs: {len(jobs)}) — "
                        "empty/degraded upstream data, not a shape error; passes as weather")
    if not with_loc:
        return "WARN", (f"{len(ok)} postings but ALL locations empty — degraded upstream data "
                        "(the India gate needs location); passes as weather")
    return "OK", f"{len(ok)} well-formed postings ({len(with_loc)} with location)"


def smoke_keyed(name: str, provider, key_envs: list[str]) -> None:
    missing = [k for k in key_envs if not os.environ.get(k)]
    if missing:
        record(name, "SKIP", f"no {'/'.join(missing)} in env — add the repo secret(s) "
                             "to smoke this channel")
        return
    jobs = provider.fetch(QUERY, CFG)
    status, detail = classify_keyed(name, jobs, getattr(provider, "last_errors", []))
    record(name, status, detail)


def decide(status_by_channel: dict) -> tuple[bool, list[str]]:
    """Cross-channel verdict. A WARN passes ONLY as isolated single-channel weather;
    the run still hard-FAILs when a signal we cannot lose fires:
      • ats (the keyless floor) failed — if it breaks, page loudly.
      • any keyed channel hard-FAILed (4xx / parse / timeout — secrets or drift).
      • ALL attempted keyed channels degraded at once (both WARN/FAIL) — that is an
        outage, not a single-channel blip.

    decide() is the SINGLE-RUN verdict. The PERSISTENCE ESCALATION (a WARN that
    recurs across N consecutive scheduled runs → FAIL, so a persistently dead
    channel can't hide as daily weather) is layered ON TOP in main() via
    load_counters/update_counters/escalations — it only ADDS FAILs to what decide()
    already returns, never softens a guardrail.
    """
    reasons: list[str] = []
    if status_by_channel.get("ats") == "FAIL":
        reasons.append("ats (the keyless discovery floor) hard-failed — paging loudly")
    for ch in KEYED_CHANNELS:
        if status_by_channel.get(ch) == "FAIL":
            reasons.append(f"{ch} hard-failed (4xx / parse error — secrets or real drift)")
    attempted = [status_by_channel.get(ch) for ch in KEYED_CHANNELS
                 if status_by_channel.get(ch) not in (None, "SKIP")]
    if len(attempted) >= 2 and all(s in ("WARN", "FAIL") for s in attempted):
        reasons.append("all keyed channels degraded at once — upstream outage, not a single-channel blip")
    return bool(reasons), reasons


# ── persistence: escalate a WARN that recurs across N consecutive scheduled runs ─
# A single transient WARN is weather (passes). But a channel that WARNs every day
# is a channel that is persistently dead/degraded, masquerading as weather — the
# gap decide() alone can't close. Cross-run state is carried in a tiny per-channel
# counter file (the workflow keeps it in the GitHub Actions cache). Enabled ONLY
# when SMOKE_STATE_FILE is set (scheduled CI runs); local runs and manual dispatch
# leave it unset → persistence off, single-run behavior unchanged.
PERSIST_THRESHOLD = 3             # a channel WARNing this many scheduled runs running → FAIL
_RESET_STATES = ("OK", "QUOTA")   # a healthy / expected state clears the channel's WARN streak


def load_counters(path: str | None) -> tuple[dict, str]:
    """Read per-channel consecutive-WARN counters → (counters, note). A missing
    file (cold cache / first run) or a corrupt/unreadable one BOTH yield zeroed
    counters: persistence bookkeeping must NEVER hard-fail the canary itself."""
    zero = {ch: 0 for ch in KEYED_CHANNELS}
    if not path or not os.path.exists(path):
        return zero, "cold"
    try:
        raw = json.load(open(path, encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state file is not a JSON object")
        out = {}
        for ch in KEYED_CHANNELS:
            try:
                out[ch] = max(0, int(raw.get(ch, 0)))
            except (TypeError, ValueError):
                out[ch] = 0            # a corrupt individual value → 0, don't fail
        return out, "ok"
    except Exception as e:             # noqa: BLE001 — never fail on bookkeeping
        return zero, f"corrupt: {e}"


def update_counters(counters: dict, status_by_channel: dict) -> dict:
    """Per-CHANNEL (not per-condition) streak update: ANY WARN flavor increments;
    a healthy/expected state (OK / QUOTA) resets to 0; SKIP / FAIL leave it
    unchanged (no clean WARN signal). Per-channel by design — a channel that flaps
    between degraded flavors (5xx → empty → timeout) has still delivered no usable
    data, so it must keep accumulating rather than reset when the flavor changes."""
    out = dict(counters)
    for ch in KEYED_CHANNELS:
        st = status_by_channel.get(ch)
        if st == "WARN":
            out[ch] = int(out.get(ch, 0)) + 1
        elif st in _RESET_STATES:
            out[ch] = 0
    return out


def escalations(counters: dict, threshold: int = PERSIST_THRESHOLD) -> list[str]:
    """FAIL reasons for channels whose consecutive-WARN streak has reached N."""
    reasons = []
    for ch in KEYED_CHANNELS:
        n = int(counters.get(ch, 0))
        if n >= threshold:
            reasons.append(f"{ch} has WARNed for {n} consecutive scheduled runs (>= {threshold}) — "
                           "escalating to FAIL: a persistently degraded/dead channel, not weather")
    return reasons


def save_counters(path: str | None, counters: dict) -> None:
    """Best-effort persist. A write failure is annotated, never fatal."""
    if not path:
        return
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({ch: int(counters.get(ch, 0)) for ch in KEYED_CHANNELS}, f)
    except Exception as e:             # noqa: BLE001 — bookkeeping must not fail the run
        print(f"::warning title=discovery-smoke::could not save persistence counters: {e}")


def main() -> int:
    print(f"discovery smoke — {len(QUERY.titles)} query title, 1 request per keyed channel\n")
    smoke_ats()
    smoke_keyed("adzuna", AdzunaProvider(), ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"])
    smoke_keyed("jsearch", JSearchProvider(), ["JSEARCH_API_KEY"])

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## Discovery smoke\n\n| channel | status | detail |\n|---|---|---|\n")
            for r in results:
                f.write(f"| {r['channel']} | {r['status']} | {r['detail'][:300]} |\n")

    status_by = {r["channel"]: r["status"] for r in results}
    fail, reasons = decide(status_by)

    # Persistence escalation — only on scheduled CI runs (SMOKE_STATE_FILE set by
    # the workflow; unset for local runs + manual dispatch, so those never perturb
    # the streak). Only ADDS FAILs; never softens a decide() guardrail.
    persist_path = os.environ.get("SMOKE_STATE_FILE")
    if persist_path:
        counters, note = load_counters(persist_path)
        if note.startswith("corrupt"):
            print(f"::warning title=discovery-smoke::persistence counters unreadable ({note}) — treated as 0")
        counters = update_counters(counters, status_by)
        esc = escalations(counters)
        reasons += esc
        if esc:
            fail = True
        save_counters(persist_path, counters)
        print("persistence streaks (consecutive WARNs): "
              + ", ".join(f"{ch}={counters.get(ch, 0)}" for ch in KEYED_CHANNELS))

    for reason in reasons:
        print(f"::error title=discovery-smoke::{reason}")

    tally = {s: sum(r["status"] == s for r in results) for s in ("OK", "WARN", "SKIP", "QUOTA", "FAIL")}
    verdict = "FAIL" if fail else ("PASS (with WARN)" if tally["WARN"] else "PASS")
    print(f"\n{verdict}: {tally['OK']} ok · {tally['WARN']} warn · {tally['SKIP']} skipped · "
          f"{tally['QUOTA']} quota · {tally['FAIL']} failed")
    if tally["WARN"] and not fail:
        print("  (WARN = transient upstream weather on a single keyed channel; ats floor healthy → not paging)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
