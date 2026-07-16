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

import yaml

from . import progress
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


def _quota_summary(run_cfg: dict) -> dict:
    """Remaining monthly free-tier quota per metered channel (no network call —
    reads the persisted counter). Shown in the run summary so the user always
    knows how much of each free tier is left this month."""
    from .discovery import quota
    disc = (run_cfg.get("discovery", {}) or {})
    out = {}
    for ch, default_cap in (("adzuna", 250), ("jsearch", 200)):
        cap = int((disc.get(ch, {}) or {}).get("monthly_cap", default_cap))
        used = quota.used_this_month(ch)
        out[ch] = {"used_this_month": used, "remaining": max(0, cap - used), "monthly_cap": cap}
    return out


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
    # Per-channel source counts among the surviving candidates (label each channel's
    # contribution, so the user sees which source produced what).
    by_source: dict[str, int] = {}
    for j in cand:
        by_source[j.source] = by_source.get(j.source, 0) + 1
    progress.emit(f"discovery: {sum(r.count for r in reports if r.enabled)} raw → "
                  f"{len(cand)} candidates")
    print(json.dumps({
        "raw": sum(r.count for r in reports if r.enabled),
        "candidates": len(cand),
        "candidates_by_source": by_source,
        "channels": [{"id": r.id, "enabled": r.enabled, "count": r.count,
                      "skipped": r.skipped_reason} for r in reports],
        "apify": cfg["apify_resolved"]["state"],
        "quota_remaining": _quota_summary(run_cfg),
        "candidates_path": path,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_prescreen(argv: list[str]) -> int:
    profile, run_cfg, _, _ = _load()
    # Stamp the run start so top.md can report wall-clock time (prescreen is the
    # first step of an evaluate run; scoring the top-N follows).
    from . import state
    from datetime import datetime, timezone
    state.write("run_timing", {"started_at": datetime.now(timezone.utc).isoformat()})
    cpath = os.path.join(RESULTS, "candidates.jsonl")
    if not os.path.exists(cpath):
        print(json.dumps({"error": "candidates.jsonl missing — run `discover` first"}))
        return 1
    cand = [JobPosting.from_dict(json.loads(l)) for l in open(cpath, encoding="utf-8") if l.strip()]
    from . import preferences as PF
    prefs = PF.load()                        # revealed-preference layer (empty until feedback)
    kept, rep = prescreen_set(cand, profile, run_cfg, preferences=prefs)
    ppath = os.path.join(RESULTS, "prescreened.jsonl")
    with open(ppath, "w", encoding="utf-8") as f:
        for j in kept:
            f.write(json.dumps(j.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(RESULTS, "prescreen_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    # Compact list the agent can iterate over without re-reading the big file.
    jobs = [{"job_id": j.id, "title": j.title, "company": j.company, "location": j.location}
            for j in kept]
    fs_n = int((run_cfg.get("scoring", {}) or {}).get("full_score_top_n", 15))
    # FIX 2 — fill score_these with VERIFIABLE jobs only. A URL-level non-job-link
    # (bare domain / careers-landing) can't be scored honestly, so it goes to its own
    # bucket instead of eating a scoring slot — 15 real verdicts, not 10 + 5 wasted.
    # (URL-only check, no network; the JD-presence check still runs later at `enrich`.)
    from . import verify
    verifiable, couldnt_verify = [], []
    for j, rec in zip(kept, jobs):
        vstatus, vreason = verify.classify(j.url, None)
        (verifiable if vstatus == "ok"
         else couldnt_verify).append(rec if vstatus == "ok" else {**rec, "status": vstatus, "reason": vreason})
    score_these = verifiable[:fs_n]
    backfill_pool = verifiable[fs_n:]
    print(json.dumps({
        "input": rep["input"], "kept": rep["kept"], "cap": rep["cap"],
        "truncated_from": rep["truncated_from"], "by_reason": rep["by_reason"],
        "preferences_applied": bool(prefs),
        "dropped_seen": len(rep.get("dropped_seen", [])),
        "demoted": rep.get("demoted", []),
        "full_score_top_n": fs_n,
        "prescreened_path": ppath,
        "jobs": jobs,                       # full ranked set (rank = list order, best first)
        "score_these": score_these,         # FIX 2 — top-N VERIFIABLE by prescreen rank
        "couldnt_verify": couldnt_verify,   # URL non-job-links → bucket (no enrich, no slot)
        "backfill_pool": backfill_pool,     # next verifiable jobs — pull one on a runtime no_jd
        "RULE": (f"Full-score in-session ONLY the {len(score_these)} jobs in `score_these` (top verifiable "
                 f"by prescreen rank). Log every job in `couldnt_verify` DIRECTLY as an unverifiable entry "
                 "(reason given) — do NOT enrich or score them, they don't consume a slot. For each job you "
                 "DO score, run `enrich` first; if its verifiability/location gate is not 'ok' at enrich time "
                 "(e.g. no_jd), record it unverifiable AND pull the next job from `backfill_pool` so you still "
                 "reach the target count. Everything else is auto-listed 'Prescreen-filtered'. Never score "
                 "beyond the prescreened set."),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_preferences(argv: list[str]) -> int:
    """Inspect / rebuild / clear the revealed-preference layer (config/preferences.yml)."""
    ap = argparse.ArgumentParser(prog="jobfinder preferences")
    ap.add_argument("--refresh", action="store_true", help="rebuild from data/feedback.jsonl")
    ap.add_argument("--show", action="store_true", help="print current preferences (default)")
    ap.add_argument("--context", action="store_true", help="print the scoring preference-context block")
    ap.add_argument("--clear", action="store_true", help="wipe the derived layer (feedback kept)")
    ap.add_argument("--clear-feedback", action="store_true",
                    help="also wipe raw data/feedback.* (a hard reset)")
    a = ap.parse_args(argv)
    from . import preferences as PF, feedback as FB

    if a.clear or a.clear_feedback:
        PF.clear()
        out = {"cleared": "config/preferences.yml"}
        if a.clear_feedback:
            for p in (FB.FB_JSONL, FB.FB_MD):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
            out["cleared_feedback"] = True
        print(json.dumps(out))
        return 0
    if a.refresh:
        prefs = PF.refresh()
        print(json.dumps({"refreshed": True, "updated": prefs.get("updated"),
                          "seen": {k: len(v) for k, v in (prefs.get("seen") or {}).items()},
                          "negative": {k: (len(v) if isinstance(v, list) else v)
                                       for k, v in (prefs.get("negative") or {}).items()}}))
        return 0
    if a.context:
        print(PF.context() or "(no established preferences yet)")
        return 0
    prefs = PF.load()
    if not prefs:
        print("(no preferences yet — mark some results, then run `preferences --refresh`)")
        return 0
    print(yaml.safe_dump(prefs, sort_keys=False, allow_unicode=True))
    return 0


def cmd_enrich(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder enrich")
    ap.add_argument("job_id", help="job_id from prescreened.jsonl")
    a = ap.parse_args(argv)
    from .discovery import job_fetcher
    profile, _, _, _ = _load()                          # needed for the location re-gate
    ppath = os.path.join(RESULTS, "prescreened.jsonl")
    jobs = [JobPosting.from_dict(json.loads(l)) for l in open(ppath, encoding="utf-8") if l.strip()]
    job = next((j for j in jobs if j.id == a.job_id), None)
    if job is None:
        print(json.dumps({"error": f"job_id {a.job_id} not in prescreened.jsonl"}))
        return 1
    job_fetcher.enrich(job)                              # deep-fetch full JD (no-op if already full)
    from . import verify, location
    vstatus, vreason = verify.classify(job.url, job.description)   # can we actually score this?
    lstatus, lreason, lcity = location.regate(job, profile)       # coarse-location onsite re-gate
    print(json.dumps({
        "job_id": job.id, "title": job.title, "company": job.company,
        "url": job.url, "location": job.location, "source": job.source,
        "verifiability": {"status": vstatus, "reason": vreason},
        "location_gate": {"status": lstatus, "reason": lreason, "derived_city": lcity},
        "scoring_view": job.scoring_view(),             # the exact JD block to score against
        "RULE": ("Score this job ONLY if verifiability.status == 'ok' AND location_gate.status == 'ok'. "
                 "If EITHER is not 'ok' (no_jd / non_job_link / onsite_elsewhere / location_unverified), "
                 "DO NOT score — write an unverifiable record (reason = the failing check's reason) and "
                 "`tracker --add` it (see modes/evaluate.md). NEVER fabricate a verdict."),
    }, ensure_ascii=False, indent=2))
    return 0


def _find_job(job_id: str) -> dict | None:
    """Look up a scored job's discovery record by job_id, so the tracker can
    label it with the origin channel (`source`) + link the verdict schema omits."""
    for fn in ("prescreened.jsonl", "candidates.jsonl"):
        p = os.path.join(RESULTS, fn)
        if not os.path.exists(p):
            continue
        for ln in open(p, encoding="utf-8"):
            if not ln.strip():
                continue
            d = json.loads(ln)
            if d.get("id") == job_id:
                return d
    return None


def cmd_tracker(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder tracker")
    ap.add_argument("--add", required=True, help="verdict JSON file, or '-' for stdin")
    a = ap.parse_args(argv)
    from . import score
    _, run_cfg, _, _ = _load()
    verdict = json.load(sys.stdin if a.add == "-" else open(a.add, encoding="utf-8"))
    if not verdict.get("job_id"):
        print(json.dumps({"error": "record needs a job_id"}))
        return 1
    # Backfill the origin channel + link/location from the discovery record so
    # top.md/tracker.md label each job with its source (the verdict schema in
    # prompts/score-job.md carries url/title/company but not source/location).
    jrec = _find_job(verdict["job_id"])
    if jrec:
        for k in ("source", "link_source", "location", "url", "title", "company"):
            if not verdict.get(k) and jrec.get(k):
                verdict[k] = jrec.get(k)
    # NORMALIZE before persist: coerce fit_score to a number, canonicalize the verdict
    # case (apply→APPLY), validate required fields (verdict, fit_score, headline). A
    # record that still fails is flagged malformed → routed to Couldn't-verify with an
    # explicit reason. So score.py's renderer receives CANONICAL data and never
    # mis-buckets a lowercase/schema-off verdict as "Filtered out". (score.py untouched.)
    from .schema import normalize_record, coerce_fit
    verdict = normalize_record(verdict)
    spath = os.path.join(RESULTS, "scored.jsonl")
    rows = [json.loads(l) for l in open(spath, encoding="utf-8") if l.strip()] if os.path.exists(spath) else []
    rows = [normalize_record(r) for r in rows if r.get("job_id") != verdict["job_id"]] + [verdict]  # upsert
    rows.sort(key=lambda v: (-(coerce_fit(v.get("fit_score")) or 0.0), len(v.get("caps_applied", []) or [])))
    with open(spath, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    funnel = None
    rep_path = os.path.join(RESULTS, "prescreen_report.json")
    if os.path.exists(rep_path):
        rep = json.load(open(rep_path, encoding="utf-8"))
        funnel = {"raw": "?", "candidates": rep.get("input"), "prescreened": rep.get("kept"),
                  "truncated_from": rep.get("truncated_from")}
    # Full ranked prescreened set + cutoff → top.md renders "Prescreen-filtered
    # (not individually scored)"; run_timing → the wall-clock footer.
    pp = os.path.join(RESULTS, "prescreened.jsonl")
    prescreened = [json.loads(l) for l in open(pp, encoding="utf-8") if l.strip()] \
        if os.path.exists(pp) else []
    fs_n = int((run_cfg.get("scoring", {}) or {}).get("full_score_top_n", 15))
    from . import state
    started_at = state.read("run_timing").get("started_at")
    score._update_tracker(rows)
    score._write_outputs(rows, [], RESULTS, int((run_cfg.get("scoring", {}) or {}).get("top_n", 10)),
                         funnel=funnel, prescreened=prescreened, full_score_top_n=fs_n,
                         started_at=started_at)
    out = {"tracked": len([r for r in rows if not r.get("unverifiable")]),
           "added": verdict["job_id"], "unverifiable": bool(verdict.get("unverifiable")),
           "malformed": bool(verdict.get("malformed")),
           "verdict": verdict.get("verdict"), "fit_score": verdict.get("fit_score")}
    if verdict.get("malformed"):
        out["reason"] = verdict.get("reason")           # surfaced, never a silent drop
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_live(argv: list[str]) -> int:
    """Liveness check (adopted from career-ops's check-liveness.mjs, lightweight):
    is a posting still active? Reuses link_resolver.verify_link — ATS soft-404
    detection + dead/anti-bot/junk classification over plain HTTP (no browser).
    A false 'expired' is worse than a slow check, so anything inconclusive maps
    to `unknown` (never dropped), not `expired`."""
    ap = argparse.ArgumentParser(prog="jobfinder live")
    ap.add_argument("ref", help="job_id (from prescreened/scored) or a full URL")
    a = ap.parse_args(argv)
    from .discovery.link_resolver import verify_link

    url, company, title = a.ref, "", ""
    if not a.ref.lower().startswith("http"):
        found = None
        for fn in ("prescreened.jsonl", "scored.jsonl"):
            p = os.path.join(RESULTS, fn)
            if not os.path.exists(p):
                continue
            for ln in open(p, encoding="utf-8"):
                if not ln.strip():
                    continue
                d = json.loads(ln)
                if a.ref in (d.get("job_id"), d.get("id")):
                    found = d
                    break
            if found:
                break
        if not found:
            print(json.dumps({"error": f"job_id {a.ref} not found; pass a URL instead"}))
            return 1
        url, company, title = found.get("url", ""), found.get("company", ""), found.get("title", "")

    res = verify_link(url, company, title)
    mapping = {"ok": "active", "trusted-blocked": "active",
               "dead": "expired", "junk": "expired",
               "unreachable": "unknown", "unverified": "unknown", "none": "unknown"}
    print(json.dumps({
        "url": url, "liveness": mapping.get(res.status, "unknown"),
        "status": res.status, "source": res.source, "verified": res.verified,
        "final_url": res.final_url,
        "note": "inconclusive → unknown (a false 'expired' would make you miss a real job)",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_benchmark(argv: list[str]) -> int:
    """Score the hand-labeled benchmark CSV: rubric vs the keyword baseline
    (agreement · false-APPLY · false-DON'T · precision/recall/F1), side by side."""
    ap = argparse.ArgumentParser(prog="jobfinder benchmark")
    ap.add_argument("--csv", default=None, help="labeling.csv (default data/benchmark/labeling.csv)")
    a = ap.parse_args(argv)
    from . import benchmark as B
    m = B.score_labeling(a.csv or B.LABELING)
    print(B.format_report(m))
    return 1 if m.get("error") else 0


HANDLERS = {"discover": cmd_discover, "prescreen": cmd_prescreen,
            "enrich": cmd_enrich, "tracker": cmd_tracker, "live": cmd_live,
            "preferences": cmd_preferences, "benchmark": cmd_benchmark}
