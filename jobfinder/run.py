"""job-finder entrypoint: discover -> dedup -> filter -> (Phase 2: score) -> rank.

Run:  python -m jobfinder --resume path/to/resume.pdf
      python -m jobfinder --discover-only          # Phase 1 only, no scoring
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

from .dedup import dedupe
from .discovery.base import Query
from .discovery.registry import discover
from .filters import keyword_prefilter, location_ok

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_dotenv(path: str) -> None:
    """Minimal .env loader (no dependency). Only sets keys not already in env."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def load_profile() -> dict:
    real = os.path.join(ROOT, "config", "profile.yml")
    example = os.path.join(ROOT, "config", "profile.example.yml")
    path = real if os.path.exists(real) else example
    prof = load_yaml(path)
    prof["_path"] = path
    return prof


def build_query(profile: dict, args) -> Query:
    titles = args.titles or (profile.get("target_roles", {}) or {}).get("primary", []) or ["jobs"]
    # Discovery breadth: query Google Jobs at country level; the scorer handles city.
    location = args.location or "India"
    return Query(titles=titles, location=location, limit_per_channel=args.limit)


def print_report(reports) -> int:
    print("\n── Discovery channel report ─────────────────────────────")
    total = 0
    for r in reports:
        if not r.enabled:
            print(f"  • {r.id:14s} OFF   ({r.skipped_reason})")
            continue
        total += r.count
        line = f"  • {r.id:14s} ON    {r.count} jobs"
        print(line)
        for e in r.errors[:6]:
            print(f"       ⚠ {e}")
        if len(r.errors) > 6:
            print(f"       ⚠ (+{len(r.errors) - 6} more tenant errors)")
    print(f"  └ raw total: {total}")
    return total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder", description="Honest job-fit finder")
    ap.add_argument("--resume", help="Path to your resume (.txt/.md/.docx/.pdf)")
    ap.add_argument("--titles", nargs="*", help="Override target role titles for discovery")
    ap.add_argument("--location", help="Discovery location (default: India)")
    ap.add_argument("--limit", type=int, default=60, help="Max results per channel")
    ap.add_argument("--discover-only", action="store_true", help="Phase 1 only: discover + save, no scoring")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "results"))
    args = ap.parse_args(argv)

    load_dotenv(os.path.join(ROOT, ".env"))
    profile = load_profile()
    tenants = (load_yaml(os.path.join(ROOT, "config", "ats_tenants.india.yml")) or {}).get("tenants", [])
    cfg = {"ats_tenants": tenants, "discovery": profile.get("discovery", {})}

    query = build_query(profile, args)
    print(f"job-finder: discovering for titles={query.titles} location={query.location!r}")
    print(f"profile: {profile['_path']}")

    raw, reports = discover(query, cfg)
    total = print_report(reports)

    enabled_channels = [r for r in reports if r.enabled]
    broke = [r for r in enabled_channels if r.errors and r.count == 0]
    if total == 0:
        if broke:
            print("\n✗ Every enabled channel errored — this is a BREAKAGE, not an empty result.")
            return 2
        print("\n• Discovery genuinely returned 0 jobs (no breakage). Try more tenants/keys.")
        return 0

    jobs = dedupe(raw)
    jobs = [j for j in jobs if location_ok(j, profile)]
    jobs = keyword_prefilter(jobs, profile, query.titles)

    os.makedirs(args.out, exist_ok=True)
    jobs_path = os.path.join(args.out, "jobs.jsonl")
    with open(jobs_path, "w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")

    print(f"\n── After dedup + India-filter + keyword pre-filter ──────")
    print(f"  candidate jobs for scoring: {len(jobs)}")
    print(f"  saved -> {jobs_path}")

    if args.discover_only:
        print("\n(--discover-only) Stopping before scoring.")
        return 0

    # Phase 2 scoring is wired in score.py.
    try:
        from .score import score_and_rank
    except ImportError:
        print("\n(scoring module not present yet — run with --discover-only)")
        return 0
    if not args.resume:
        print("\n⚠ No --resume given; cannot score. Re-run with --resume <path>.")
        return 1
    return score_and_rank(args.resume, jobs, profile, args.out)


if __name__ == "__main__":
    sys.exit(main())
