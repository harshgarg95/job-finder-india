"""Preference layer — accumulated revealed preferences, DERIVED from feedback.

This is how job-finder learns WITHOUT touching the scoring law (`prompts/_rubric.md`
never changes). From the raw corrections in `data/feedback.jsonl` (joined with the
tracker for reliable location), we maintain `config/preferences.yml`:

  • negative patterns (repeatedly-rejected functions / companies / locations /
    seniority) → prescreen DOWN-RANKS look-alikes (soft, logged, cap-respecting);
  • positive patterns (applied / interested) and the negatives together →
    a short "user preference context" block the scoring mode injects as a
    TIE-BREAKER for borderline calls only.

It is machine-maintained (`refresh`), inspectable (`--show`), and reversible
(`--clear`) — a bad correction never poisons future runs permanently. User Layer
(gitignored). It never hard-filters a pattern and never overrides a hard gate.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date

import yaml

from . import feedback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
DATA = os.path.join(ROOT, "data")
PREFS_PATH = os.path.join(CONFIG, "preferences.yml")
TRACKER_JSONL = os.path.join(DATA, "tracker.jsonl")

DEFAULT_THRESHOLD = 2       # a negative value must recur ≥ this many times to demote look-alikes

# Words that don't distinguish a role's function (seniority, generic role suffixes,
# domain buzzwords, fillers) — dropped so the function signature is the meaningful part.
_STOP = {
    "senior", "sr", "junior", "jr", "lead", "staff", "principal", "associate", "chief",
    "manager", "mgr", "engineer", "specialist", "analyst", "consultant", "officer",
    "director", "head", "owner", "vp", "svp",
    "ai", "ml", "genai", "llm", "gen", "the", "and", "for", "with", "of", "to", "in",
    "at", "on", "remote", "hybrid", "onsite", "india", "global", "new", "iii",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 3 and t not in _STOP]


def _phrase(text: str, n: int = 2) -> str:
    ts = _tokens(text)
    return " ".join(ts[:n]) if ts else (text or "").strip().lower()


def _load_tracker() -> dict:
    by = {}
    if os.path.exists(TRACKER_JSONL):
        for ln in open(TRACKER_JSONL, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    e = json.loads(ln)
                    by[e.get("job_id")] = e
                except json.JSONDecodeError:
                    continue
    return by


def derive(entries: list[dict], tracker: dict, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Aggregate the latest-per-job corrections into the preference structure."""
    latest = feedback._latest(entries)
    neg_fn: dict[str, dict] = defaultdict(lambda: {"count": 0, "tokens": set()})
    neg_co: dict[str, int] = defaultdict(int)
    neg_loc: dict[str, int] = defaultdict(int)
    neg_sen: dict[str, int] = defaultdict(int)
    pos_fn: dict[str, int] = defaultdict(int)
    pos_co: dict[str, int] = defaultdict(int)
    comp_hits = 0
    seen_applied, seen_rejected = [], []

    for e in latest:
        act = e.get("action")
        jid = e.get("job_id")
        title = e.get("title", "") or ""
        company = (e.get("company") or "").strip().lower()
        loc = ((tracker.get(jid) or {}).get("location")) or ""

        if act == "applied":
            seen_applied.append(jid)
        elif act in feedback.REASONS or act == "wouldnt_apply":
            seen_rejected.append(jid)

        if act in feedback.POSITIVE:
            p = _phrase(title)
            if p:
                pos_fn[p] += 1
            if company:
                pos_co[company] += 1
        elif act in ("wrong_function", "wouldnt_apply"):
            p = _phrase(title)
            if p:
                neg_fn[p]["count"] += 1
                neg_fn[p]["tokens"] |= set(_tokens(title))
        elif act == "wrong_company":
            if company:
                neg_co[company] += 1
        elif act == "wrong_location":
            for t in _tokens(loc):
                neg_loc[t] += 1
        elif act == "wrong_level":
            for t in re.findall(r"director|vice president|vp|svp|principal|staff|head|chief|senior|lead",
                                title.lower()):
                neg_sen[t] += 1
        elif act == "wrong_comp":
            comp_hits += 1

    def _nfn(d):
        return [{"value": v, "count": i["count"], "tokens": sorted(i["tokens"])}
                for v, i in sorted(d.items(), key=lambda kv: -kv[1]["count"])]

    def _nc(d):
        return [{"value": v, "count": c} for v, c in sorted(d.items(), key=lambda kv: -kv[1])]

    return {
        "updated": date.today().isoformat(),
        "established_threshold": threshold,
        "negative": {
            "functions": _nfn(neg_fn),
            "companies": _nc(neg_co),
            "locations": _nc(neg_loc),
            "seniority": _nc(neg_sen),
            "comp_floor_hits": comp_hits,
        },
        "positive": {
            "functions": _nc(pos_fn),
            "companies": _nc(pos_co),
        },
        "seen": {
            "applied": sorted(set(x for x in seen_applied if x)),
            "rejected": sorted(set(x for x in seen_rejected if x)),
        },
    }


def refresh(threshold: int = DEFAULT_THRESHOLD) -> dict:
    prefs = derive(feedback.load(), _load_tracker(), threshold)
    os.makedirs(CONFIG, exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(prefs, f, sort_keys=False, allow_unicode=True)
    return prefs


def load() -> dict:
    if not os.path.exists(PREFS_PATH):
        return {}
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        return {}


def clear() -> None:
    try:
        os.remove(PREFS_PATH)
    except FileNotFoundError:
        pass


def seen_ids(prefs: dict) -> set[str]:
    s = (prefs or {}).get("seen", {}) or {}
    return set(s.get("applied", []) or []) | set(s.get("rejected", []) or [])


def negative_hits(job, prefs: dict) -> list[tuple[str, str]]:
    """Established-negative patterns this job matches → [(category, value)]. Only
    values that recur ≥ established_threshold count; function match needs ≥2 shared
    significant tokens (conservative — a single generic word never demotes)."""
    if not prefs:
        return []
    th = int(prefs.get("established_threshold", DEFAULT_THRESHOLD))
    neg = prefs.get("negative", {}) or {}
    title = job.title or ""
    company = (job.company or "").lower()
    loc = (job.location or "").lower()
    ctoks = set(_tokens(title))
    hits: list[tuple[str, str]] = []

    for it in neg.get("functions", []) or []:
        if it.get("count", 0) >= th:
            ntoks = set(it.get("tokens") or _tokens(it.get("value", "")))
            if len(ctoks & ntoks) >= 2:
                hits.append(("function", it["value"]))
    for it in neg.get("companies", []) or []:
        if it.get("count", 0) >= th and it.get("value") and it["value"] in company:
            hits.append(("company", it["value"]))
    for it in neg.get("locations", []) or []:
        if it.get("count", 0) >= th and it.get("value") and re.search(
                r"\b" + re.escape(it["value"]) + r"\b", loc):
            hits.append(("location", it["value"]))
    for it in neg.get("seniority", []) or []:
        if it.get("count", 0) >= th and it.get("value") and re.search(
                r"\b" + re.escape(it["value"]) + r"\b", title.lower()):
            hits.append(("seniority", it["value"]))
    return hits


def context(prefs: dict | None = None) -> str:
    """Short block the scoring mode injects — a TIE-BREAKER for borderline calls,
    never an override. Empty string if there's nothing established yet."""
    prefs = load() if prefs is None else prefs
    if not prefs:
        return ""
    neg = prefs.get("negative", {}) or {}
    pos = prefs.get("positive", {}) or {}

    def _fmt(items):
        return ", ".join(f"{i['value']} ×{i['count']}" for i in (items or []) if i.get("count", 0) >= 1)

    nf, nc, nl = _fmt(neg.get("functions")), _fmt(neg.get("companies")), _fmt(neg.get("locations"))
    pf, pc = _fmt(pos.get("functions")), _fmt(pos.get("companies"))
    if not any([nf, nc, nl, pf, pc]):
        return ""
    lines = ["## USER PREFERENCE CONTEXT (revealed — a TIE-BREAKER for borderline calls only; "
             "it does NOT override the rubric, a strong fit, or any hard gate)"]
    passed = "; ".join(x for x in [f"functions [{nf}]" if nf else "",
                                   f"companies [{nc}]" if nc else "",
                                   f"locations [{nl}]" if nl else ""] if x)
    liked = "; ".join(x for x in [f"functions [{pf}]" if pf else "",
                                  f"companies [{pc}]" if pc else ""] if x)
    if passed:
        lines.append(f"- The user has repeatedly PASSED on: {passed}.")
    if liked:
        lines.append(f"- The user APPLIED to / liked: {liked}.")
    lines.append("- For a BORDERLINE score (≈3.5–4.2) you may lean ~0.1–0.2 toward the revealed "
                 "preference; never flip a clear APPLY/DON'T APPLY and never bypass a hard gate.")
    return "\n".join(lines)
