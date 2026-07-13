"""job-finder entrypoint: cold-start check -> discover -> dedup -> filter ->
PRESCREEN (bounded) -> score -> rank.

Run:  python -m jobfinder --resume path/to/resume.pdf
      python -m jobfinder --discover-only          # discovery + prescreen, no scoring
      python -m jobfinder onboard                  # first-run setup (see __main__)
      python -m jobfinder doctor --json            # setup check (see __main__)

Volume safety: the prescreen (prescreen_set) bounds the candidate set to
run.yml's `max_llm_jobs` BEFORE any LLM call, and the funnel is logged at every
stage (raw -> candidates -> prescreened -> scored). An all-day / credits-gone
run is impossible by construction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

from . import doctor
from .dedup import dedupe
from .discovery import apify
from .discovery.base import Query
from .discovery.registry import discover
from .filters import keyword_prefilter, location_ok
from .prescreen import prescreen_set

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


def _load_user_yaml(name: str) -> dict:
    """Load config/<name>.yml, falling back to the shipped <name>.example.yml."""
    real = os.path.join(ROOT, "config", f"{name}.yml")
    example = os.path.join(ROOT, "config", f"{name}.example.yml")
    path = real if os.path.exists(real) else example
    data = load_yaml(path) if os.path.exists(path) else {}
    data["_path"] = path
    return data


def load_profile() -> dict:
    return _load_user_yaml("profile")


def build_query(profile: dict, args, limit: int) -> Query:
    titles = args.titles or (profile.get("target_roles", {}) or {}).get("primary", []) or ["jobs"]
    # Discovery breadth: query at country level; the prescreen + scorer handle city.
    location = args.location or "India"
    return Query(titles=titles, location=location, limit_per_channel=limit)


def print_report(reports) -> int:
    print("\n── Discovery channel report ─────────────────────────────")
    total = 0
    for r in reports:
        if not r.enabled:
            print(f"  • {r.id:14s} OFF   ({r.skipped_reason})")
            continue
        total += r.count
        print(f"  • {r.id:14s} ON    {r.count} jobs")
        for e in r.errors[:6]:
            print(f"       ⚠ {e}")
        if len(r.errors) > 6:
            print(f"       ⚠ (+{len(r.errors) - 6} more tenant errors)")
    print(f"  └ raw total: {total}")
    return total


def _cold_start_gate(args) -> int | None:
    """Mirror career-ops's first-run check. Returns an exit code to STOP, or None
    to proceed. Discovery/scoring do not run until the basics exist."""
    rep = doctor.check()
    resume_ok = bool(rep["files"].get("resume")) or bool(
        args.resume and os.path.exists(os.path.expanduser(args.resume)))
    missing = [m for m in rep["missing_required"] if not (m == "resume" and resume_ok)]

    if not rep["has_cli"]:
        print("✗ No AI CLI found (claude / gemini / codex / qwen / opencode) and no Ollama model.")
        print("  Scoring runs through a CLI you already have — install one, then re-run.")
        return 1
    if missing:
        print(f"✗ Setup incomplete — missing: {', '.join(missing)}.")
        print("  Run onboarding first:  python -m jobfinder onboard")
        print("  (Discovery and scoring stay off until the basics exist — by design.)")
        return 1
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder", description="Honest job-fit finder")
    ap.add_argument("--resume", help="Path to your resume (.txt/.md/.docx/.pdf)")
    ap.add_argument("--titles", nargs="*", help="Override target role titles for discovery")
    ap.add_argument("--location", help="Discovery location (default: India)")
    ap.add_argument("--limit", type=int, default=None, help="Max results per channel (default: run.yml)")
    ap.add_argument("--cli", default=None, help="AI CLI to score with (claude/gemini/codex/qwen/...)")
    ap.add_argument("--discover-only", action="store_true",
                    help="Discover + prescreen + save, no scoring")
    ap.add_argument("--skip-doctor", action="store_true", help="(advanced) bypass the cold-start setup check")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "results"))
    args = ap.parse_args(argv)

    load_dotenv(os.path.join(ROOT, ".env"))

    if not args.skip_doctor:
        stop = _cold_start_gate(args)
        if stop is not None:
            return stop

    profile = load_profile()
    run_cfg = _load_user_yaml("run")
    sources = _load_user_yaml("sources")
    tenants = (load_yaml(os.path.join(ROOT, "config", "ats_tenants.india.yml")) or {}).get("tenants", [])
    cfg = {"ats_tenants": tenants, "sources": sources, "run": run_cfg,
           "discovery": profile.get("discovery", {})}

    limit = args.limit if args.limit is not None else \
        int((run_cfg.get("discovery", {}) or {}).get("limit_per_channel", 60))
    query = build_query(profile, args, limit)
    print(f"job-finder: discovering for titles={query.titles} location={query.location!r}")
    print(f"profile: {profile['_path']}  ·  run: {run_cfg['_path']}  ·  sources: {sources['_path']}")

    # Start-of-run, read-only Apify resolution BEFORE discovery (cheap probe, no
    # scrape). Apify stays OPTIONAL — any non-active state just runs ATS-only.
    cfg["apify_resolved"] = apify.resolve(cfg)
    _ar = cfg["apify_resolved"]
    print(f"apify channel: {_ar['state']}" + (f" — {_ar['reason']}" if _ar.get("reason") else ""))

    raw, reports = discover(query, cfg)
    total = print_report(reports)
    if (cfg.get("apify_resolved") or {}).get("state") != "active":
        print(f"ℹ Apify {cfg['apify_resolved']['state']} — optional India-board coverage "
              "(Naukri/LinkedIn/Indeed) is off; running on the free ATS scan only. "
              "(Add APIFY_TOKEN to .env + enable in config/sources.yml to include it.)")

    enabled_channels = [r for r in reports if r.enabled]
    broke = [r for r in enabled_channels if r.errors and r.count == 0]
    if total == 0:
        if broke:
            print("\n✗ Every enabled channel errored — this is a BREAKAGE, not an empty result.")
            return 2
        print("\n• Discovery genuinely returned 0 jobs (no breakage). Try more tenants/keys.")
        return 0

    jobs = dedupe(raw)
    candidates = [j for j in jobs if location_ok(j, profile)]
    candidates = keyword_prefilter(candidates, profile, query.titles)

    # ── The volume gate: bound the set BEFORE any LLM call ──
    kept, prep = prescreen_set(candidates, profile, run_cfg)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "jobs.jsonl"), "w", encoding="utf-8") as f:
        for j in candidates:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(args.out, "prescreened.jsonl"), "w", encoding="utf-8") as f:
        for j in kept:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(args.out, "prescreen_report.json"), "w", encoding="utf-8") as f:
        json.dump(prep, f, ensure_ascii=False, indent=2)

    cap_note = f", capped from {prep['truncated_from']}" if prep["truncated_from"] else ""
    print("\n── Funnel (volume safety) ───────────────────────────────")
    print(f"  raw discovered ................ {total}")
    print(f"  after dedup + India + keyword . {len(candidates)}")
    print(f"  after prescreen (bounded) ..... {len(kept)}  (cap {prep['cap']}{cap_note})")
    if prep["by_reason"]:
        print("  top drop reasons:")
        for reason, n in list(prep["by_reason"].items())[:6]:
            print(f"     {n:4d}  {reason}")
    print(f"  saved -> {os.path.join(args.out, 'prescreened.jsonl')} (+ prescreen_report.json)")

    funnel = {"raw": total, "candidates": len(candidates), "prescreened": len(kept),
              "truncated_from": prep["truncated_from"]}

    if args.discover_only:
        print("\n(--discover-only) Stopping before scoring.")
        return 0

    if not kept:
        print("\n• Nothing survived the prescreen — no LLM calls made. "
              "Broaden target_roles in config/profile.yml or check discovery.")
        return 0

    from .score import score_and_rank
    if not args.resume:
        print("\n⚠ No --resume given; cannot score. Re-run with --resume <path>.")
        return 1
    # CLI precedence: --cli flag > run.yml scoring.cli > $JOBFINDER_CLI/auto-detect.
    chosen_cli = args.cli or (run_cfg.get("scoring", {}) or {}).get("cli")
    return score_and_rank(os.path.expanduser(args.resume), kept, profile, args.out,
                          cli=chosen_cli, run_cfg=run_cfg, funnel=funnel)


if __name__ == "__main__":
    sys.exit(main())
