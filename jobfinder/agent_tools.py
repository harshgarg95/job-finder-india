"""Agent-callable tools for the prompt-pack (in-CLI) mode.

These are thin JSON wrappers around the EXISTING deterministic pipeline so the
user's own AI CLI (Claude / Gemini / Codex / OpenCode) can drive job-finder by
shelling out, then score the bounded set IN-SESSION with its own model — no
headless `claude -p`, no setup-token.

  python -m jobfinder discover --json     # discover + dedup + India/keyword filter → candidates.jsonl
  python -m jobfinder prescreen --json    # candidates → prescreened.jsonl (hard cap) + funnel
  python -m jobfinder enrich <job_id>     # deep-fetch ONE full JD for in-session scoring
  python -m jobfinder tracker --add -     # register one scored verdict (stdin/file) → tracker.md + top.md

The headless run.py / cli_adapter path is intentionally KEPT (the CI/batch
fallback, decision D1) — these tools do not touch it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import run as R
from .dedup import dedupe
from .discovery import apify
from .discovery.base import Query
from .discovery.registry import discover
from .filters import keyword_prefilter, location_ok
from .prescreen import prescreen_set
from .schema import JobPosting

RESULTS = os.path.join(R.ROOT, "data", "results")


def _load():
    """Load env + profile/run/sources + the merged tenant list (same as run.py)."""
    R.load_dotenv(os.path.join(R.ROOT, ".env"))
    profile = R.load_profile()
    run_cfg = R._load_user_yaml("run")
    sources = R._load_user_yaml("sources")
    tenants = (R.load_yaml(os.path.join(R.ROOT, "config", "ats_tenants.india.yml")) or {}).get("tenants", [])
    companies = (R.load_yaml(os.path.join(R.ROOT, "config", "companies_india.yml")) or {}).get("companies", [])
    seen, merged = set(), []
    for t in tenants + companies:
        key = (t.get("ats"), t.get("slug"), t.get("host"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)
    cfg = {"ats_tenants": merged, "sources": sources, "run": run_cfg,
           "discovery": profile.get("discovery", {})}
    os.makedirs(RESULTS, exist_ok=True)
    return profile, run_cfg, sources, cfg


def cmd_discover(argv: list[str]) -> int:
    profile, run_cfg, sources, cfg = _load()
    cfg["apify_resolved"] = apify.resolve(cfg)          # start-of-run, read-only
    limit = int((run_cfg.get("discovery", {}) or {}).get("limit_per_channel", 60))
    titles = (profile.get("target_roles", {}) or {}).get("primary", []) or ["jobs"]
    raw, reports = discover(Query(titles=titles, location="India", limit_per_channel=limit), cfg)
    jobs = dedupe(raw)
    cand = keyword_prefilter([j for j in jobs if location_ok(j, profile)], profile, titles)
    path = os.path.join(RESULTS, "candidates.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for j in cand:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
    print(json.dumps({
        "raw": sum(r.count for r in reports if r.enabled),
        "candidates": len(cand),
        "channels": [{"id": r.id, "enabled": r.enabled, "count": r.count,
                      "skipped": r.skipped_reason} for r in reports],
        "apify": cfg["apify_resolved"]["state"],
        "candidates_path": path,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_prescreen(argv: list[str]) -> int:
    profile, run_cfg, _, _ = _load()
    cpath = os.path.join(RESULTS, "candidates.jsonl")
    if not os.path.exists(cpath):
        print(json.dumps({"error": "candidates.jsonl missing — run `discover` first"}))
        return 1
    cand = [JobPosting.from_dict(json.loads(l)) for l in open(cpath, encoding="utf-8") if l.strip()]
    kept, rep = prescreen_set(cand, profile, run_cfg)
    ppath = os.path.join(RESULTS, "prescreened.jsonl")
    with open(ppath, "w", encoding="utf-8") as f:
        for j in kept:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(RESULTS, "prescreen_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    # Compact list the agent can iterate over without re-reading the big file.
    jobs = [{"job_id": j.id, "title": j.title, "company": j.company, "location": j.location}
            for j in kept]
    print(json.dumps({
        "input": rep["input"], "kept": rep["kept"], "cap": rep["cap"],
        "truncated_from": rep["truncated_from"], "by_reason": rep["by_reason"],
        "prescreened_path": ppath, "jobs": jobs,
        "RULE": f"Score ONLY these {len(jobs)} jobs in-session. Never discover or score beyond this set.",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_enrich(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder enrich")
    ap.add_argument("job_id", help="job_id from prescreened.jsonl")
    a = ap.parse_args(argv)
    from .discovery import job_fetcher
    ppath = os.path.join(RESULTS, "prescreened.jsonl")
    jobs = [JobPosting.from_dict(json.loads(l)) for l in open(ppath, encoding="utf-8") if l.strip()]
    job = next((j for j in jobs if j.id == a.job_id), None)
    if job is None:
        print(json.dumps({"error": f"job_id {a.job_id} not in prescreened.jsonl"}))
        return 1
    job_fetcher.enrich(job)                              # deep-fetch full JD (no-op if already full)
    print(json.dumps({
        "job_id": job.id, "title": job.title, "company": job.company,
        "url": job.url, "location": job.location, "source": job.source,
        "scoring_view": job.scoring_view(),             # the exact JD block to score against
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_tracker(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder tracker")
    ap.add_argument("--add", required=True, help="verdict JSON file, or '-' for stdin")
    a = ap.parse_args(argv)
    from . import score
    _, run_cfg, _, _ = _load()
    verdict = json.load(sys.stdin if a.add == "-" else open(a.add, encoding="utf-8"))
    if not isinstance(verdict.get("fit_score"), (int, float)) or not verdict.get("job_id"):
        print(json.dumps({"error": "verdict needs numeric fit_score and job_id"}))
        return 1
    spath = os.path.join(RESULTS, "scored.jsonl")
    rows = [json.loads(l) for l in open(spath, encoding="utf-8") if l.strip()] if os.path.exists(spath) else []
    rows = [r for r in rows if r.get("job_id") != verdict["job_id"]] + [verdict]   # upsert by job_id
    rows.sort(key=lambda v: (-float(v.get("fit_score", 0)), len(v.get("caps_applied", []) or [])))
    with open(spath, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    funnel = None
    rep_path = os.path.join(RESULTS, "prescreen_report.json")
    if os.path.exists(rep_path):
        rep = json.load(open(rep_path, encoding="utf-8"))
        funnel = {"raw": "?", "candidates": rep.get("input"), "prescreened": rep.get("kept"),
                  "truncated_from": rep.get("truncated_from")}
    score._update_tracker(rows)
    score._write_outputs(rows, [], RESULTS, int((run_cfg.get("scoring", {}) or {}).get("top_n", 10)),
                         funnel=funnel)
    print(json.dumps({"tracked": len(rows), "added": verdict["job_id"],
                      "verdict": verdict.get("verdict"), "fit_score": verdict.get("fit_score")},
                     ensure_ascii=False))
    return 0


HANDLERS = {"discover": cmd_discover, "prescreen": cmd_prescreen,
            "enrich": cmd_enrich, "tracker": cmd_tracker}
