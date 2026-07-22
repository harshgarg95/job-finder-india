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
  FAIL  — channel errored, or shape stopped parsing        (exit 1 → email)

Free-tier cost of the daily run: ~30 Adzuna + ~30 JSearch requests/month
(of ~250 and ~200 free) + a handful of keyless ATS calls. No Apify, no SerpAPI.
"""
from __future__ import annotations

import os
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
    icon = {"OK": "✅", "SKIP": "⏭️", "QUOTA": "🟡", "FAIL": "❌"}[status]
    print(f"{icon} {channel:<10} {status:<6} {detail}")
    if status == "FAIL":
        print(f"::error title=discovery-smoke {channel}::{detail}")
    elif status in ("SKIP", "QUOTA"):
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


# ── keyed channels: one real request, then the shape contract ────────────────
def smoke_keyed(name: str, provider, key_envs: list[str]) -> None:
    missing = [k for k in key_envs if not os.environ.get(k)]
    if missing:
        record(name, "SKIP", f"no {'/'.join(missing)} in env — add the repo secret(s) "
                             "to smoke this channel")
        return
    jobs = provider.fetch(QUERY, CFG)
    errors = getattr(provider, "last_errors", [])
    if any("quota" in e.lower() or "rate limit" in e.lower() for e in errors):
        record(name, "QUOTA", "free tier exhausted / rate-limited — not API drift; "
                              f"({'; '.join(errors)})")
        return
    if errors:
        record(name, "FAIL", "; ".join(errors))
        return
    ok = well_formed(jobs)
    with_loc = [j for j in ok if (j.location or "").strip()]
    if not ok:
        record(name, "FAIL", f"request succeeded but 0 well-formed postings parsed "
                             f"(raw jobs: {len(jobs)}) — response shape changed?")
    elif not with_loc:
        record(name, "FAIL", f"{len(ok)} postings but ALL have an empty location — "
                             "location field renamed? (the India gate depends on it)")
    else:
        record(name, "OK", f"{len(ok)} well-formed postings ({len(with_loc)} with location)")


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

    fails = [r for r in results if r["status"] == "FAIL"]
    print(f"\n{'FAIL' if fails else 'PASS'}: "
          f"{sum(r['status'] == 'OK' for r in results)} ok · "
          f"{sum(r['status'] == 'SKIP' for r in results)} skipped · "
          f"{sum(r['status'] == 'QUOTA' for r in results)} quota · {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
