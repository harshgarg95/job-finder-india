"""Deterministic pre-screen — the VOLUME-SAFETY gate before any LLM call.

This is the fix for the failure mode where ~907 candidates were sent to the
scorer (× self-consistency samples ≈ thousands of LLM calls). A free, fast,
title/seniority/function/hard-constraint gate (the career-ops `title_filter`
pattern: positive + negative matching) cuts the set to a bounded ~30–50 BEFORE
the expensive holistic scorer runs. A hard `max_llm_jobs` cap guarantees an
all-day / credits-gone run is impossible.

Design rules (unchanged from the project's ethos):
  • This is a COST filter, not the fit verdict. It removes the clearly-wrong
    (wrong role family, over-senior title, foreign / non-commutable onsite) and
    ranks the rest; the honest holistic rubric still makes the real call.
  • Conservative on ambiguity: anything that *might* fit passes through.
  • No silent truncation: if the kept set exceeds the cap, the caller is told
    exactly how many were dropped to the cap (`report["truncated_from"]`).
"""

from __future__ import annotations

import re
from collections import Counter

from .schema import JobPosting

# ── Role-family POSITIVES (career-ops title_filter "positive") ───────────────
# Explicit role-family phrases for a delivery / program / product / solutions
# profile. We also mine the user's own profile (primary titles, archetypes,
# in_scope), so this adapts per user. A title with NO role-family signal is
# almost always an IC / other-function role → the dominant volume cut.
_DEFAULT_POSITIVE = [
    "program manager", "technical program manager", "tpm", "program lead",
    "project manager", "delivery manager", "delivery lead", "delivery head",
    "implementation manager", "implementation lead", "implementation consultant",
    "implementation specialist", "onboarding manager", "engagement manager",
    "product manager", "product owner", "product lead", "group product manager",
    "technical product manager", "solutions consultant", "solution consultant",
    "solutions architect", "solution architect", "solutions engineer",
    "solutions manager", "customer success", "professional services",
    "transformation manager", "ai delivery", "ai implementation",
    "ai engineer",  # applied AI engineering = the candidate's "adjacent" stretch
]

# A generic leadership head + an AI/ML qualifier together is also a positive
# (catches "GenAI Product Lead", "AI Solutions Specialist", "Generative AI
# Consultant") without admitting IC engineering roles that merely mention AI.
_COMBO_HEADS = ["manager", "lead", "owner", "consultant", "architect", "specialist"]

# ── Clearly-wrong FUNCTIONS (career-ops title_filter "negative") ─────────────
_DEFAULT_NEGATIVE = [
    "data scientist", "research scientist", "applied scientist", "research engineer",
    "machine learning engineer", "ml engineer", "deep learning", "nlp engineer",
    "computer vision", "software engineer", "software developer", "backend engineer",
    "back end engineer", "frontend engineer", "front end engineer", "full stack",
    "fullstack", "android engineer", "ios engineer", "mobile engineer",
    "platform engineer", "systems engineer", "devops", "site reliability", "sre",
    "data engineer", "security engineer", "qa engineer", "test engineer",
    "quality engineer", "automation engineer", "account executive", "sales development",
    "business development", "recruiter", "talent acquisition", "graphic designer",
    "ux designer", "ui designer", "content writer", "accountant", "controller",
    "people partner", "intern",
]

# ── Seniority ABOVE the candidate's honest ceiling (manager / mid-IC) → drop ──
_SENIOR_OVER = [
    "director", "vice president", "vp", "svp", "evp", "head of", "chief",
    "cto", "ceo", "coo", "cpo", "cfo", "principal", "staff", "distinguished",
]

# AI qualifiers (whole-word) — gate combo + ranking.
_AI_TERMS = ["ai", "ml", "genai", "gen ai", "llm", "machine learning",
             "artificial intelligence", "generative"]

# ── Location tokens for the hard-constraint gate ─────────────────────────────
_INDIA_CITIES = [
    "hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai", "pune", "delhi",
    "new delhi", "gurgaon", "gurugram", "noida", "chennai", "kolkata", "ahmedabad",
    "jaipur", "indore", "kochi", "coimbatore", "chandigarh", "trivandrum",
    "thiruvananthapuram", "ncr",
]
_INDIA_TOKENS = _INDIA_CITIES + ["india", "bharat", "telangana", "karnataka",
                                 "maharashtra", "tamil nadu", "kerala"]
_FOREIGN_TOKENS = [
    "united states", "usa", "us", "u.s", "united kingdom", "uk", "canada", "france",
    "germany", "netherlands", "spain", "mexico", "singapore", "dubai", "uae",
    "australia", "ireland", "europe", "emea", "americas", "brazil", "poland",
    "japan", "china", "london", "new york", "san francisco", "seattle", "toronto",
    "california",
]
_REMOTE_TOKENS = ["remote", "anywhere", "work from home", "wfh"]


def _compile(phrases) -> list[re.Pattern]:
    rx = []
    for p in phrases:
        p = (p or "").strip().lower()
        if len(p) >= 2:
            rx.append(re.compile(r"\b" + re.escape(p) + r"\b", re.I))
    return rx


def _match_any(regexes: list[re.Pattern], text: str):
    """Return the actual matched substring (for a clean drop reason) or None."""
    if not text:
        return None
    for r in regexes:
        m = r.search(text)
        if m:
            return m.group(0)
    return None


# Profile-independent patterns, compiled once.
_NEGATIVE_RX = _compile(_DEFAULT_NEGATIVE)
_SENIOR_RX = _compile(_SENIOR_OVER)
_AI_RX = _compile(_AI_TERMS)
_COMBO_RX = _compile(_COMBO_HEADS)
_INDIA_RX = _compile(_INDIA_TOKENS)
_FOREIGN_RX = _compile(_FOREIGN_TOKENS)


def _profile_positives(profile: dict) -> list[str]:
    out = set(_DEFAULT_POSITIVE)
    tr = profile.get("target_roles", {}) or {}
    for t in tr.get("primary", []) or []:
        out.add((t or "").lower().strip())
    for a in tr.get("archetypes", []) or []:
        nm = (a.get("name") or "").lower().strip()
        if nm:
            out.add(nm)
    for f in (profile.get("function", {}) or {}).get("in_scope", []) or []:
        out.add((f or "").lower().strip())
    return sorted(p for p in out if len(p) >= 3)


def _is_positive(title: str, role_rx: list[re.Pattern]) -> bool:
    """Title is in the target role family: an explicit role-family phrase, OR a
    generic leadership head paired with an AI/ML qualifier."""
    if _match_any(role_rx, title):
        return True
    if _match_any(_AI_RX, title) and _match_any(_COMBO_RX, title):
        return True
    return False


def _structured_gate(job: JobPosting, profile: dict, run_cfg: dict) -> tuple[bool, str]:
    """Original Tier-0 gate: drop on clearly-over-senior stated experience or
    disclosed comp below the floor. Fires only when the structured field exists."""
    sen = profile.get("seniority", {}) or {}
    comp = profile.get("compensation", {}) or {}
    years_total = sen.get("years_total")
    buf = (run_cfg.get("prescreen", {}) or {}).get("seniority_buffer_years", 3)

    if job.experience_min is not None and years_total:
        if job.experience_min >= years_total + buf:
            return False, f"JD requires {job.experience_min:g}+ yrs; you have ~{years_total:g} total"

    floor = comp.get("floor_ctc_lpa")
    if floor and job.salary_max and (job.salary_currency in (None, "INR", "inr", "Rs")):
        lpa = job.salary_max / 100000.0
        if 0 < lpa < floor:
            return False, f"stated max comp ~{lpa:.0f} LPA below your floor of {floor:g} LPA"
    return True, ""


def _location_gate(job: JobPosting, profile: dict) -> tuple[bool, str]:
    """Hard constraints: drop foreign roles (even if remote — not India-eligible)
    and onsite roles in a non-allowed city. Remote-India / unknown pass through."""
    loc = (job.location or "").lower().strip()
    if not loc:
        return True, ""

    foreign = _match_any(_FOREIGN_RX, loc)
    india = _match_any(_INDIA_RX, loc)
    if foreign and not india:
        return False, f"foreign location ('{foreign}' — not India-eligible)"

    locp = profile.get("location", {}) or {}
    if locp.get("willing_to_relocate"):
        return True, ""
    if job.remote or any(t in loc for t in _REMOTE_TOKENS):
        return True, ""  # remote handled (India-eligibility checked above)
    onsite = [c.lower() for c in (locp.get("onsite_cities") or [])]
    named = [c for c in _INDIA_CITIES if c in loc]
    if named and onsite and not any(o in loc for o in onsite):
        return False, f"onsite in {named[0].title()} (you're onsite-{onsite[0].title()} only)"
    return True, ""


def _gate(job: JobPosting, profile: dict, run_cfg: dict,
          role_rx: list[re.Pattern]) -> tuple[bool, str]:
    """Run all deterministic gates on one job. (passes, drop_reason)."""
    title = (job.title or "").strip()
    if not title:
        return False, "no title"

    over = _match_any(_SENIOR_RX, title)
    if over:
        return False, f"over-senior title ('{over}' — above your manager/mid ceiling)"

    if not _is_positive(title, role_rx):
        neg = _match_any(_NEGATIVE_RX, title)
        return False, (f"wrong-function title ('{neg}')" if neg else "title not in target role family")

    ok, why = _structured_gate(job, profile, run_cfg)
    if not ok:
        return False, why
    ok, why = _location_gate(job, profile)
    if not ok:
        return False, why
    return True, ""


# Seniority bands for proximity scoring (title level vs the candidate's honest ceiling).
_CEILING_RANK = {"intern": 0, "junior": 1, "associate": 1, "mid": 2, "senior": 3,
                 "lead": 4, "manager": 5, "director": 6}
_TITLE_BAND = [("intern", 0), ("junior", 1), ("associate", 1), ("senior", 3), ("lead", 4),
               ("principal", 5), ("staff", 5), ("manager", 5), ("head", 6), ("director", 6),
               ("vice president", 6), ("chief", 6)]


_BARE_REMOTE_OK = {"", "anywhere", "global", "worldwide", "remote"}


def _location_fit(job: JobPosting, profile: dict) -> float:
    """Deterministic location fit for an India-based candidate: own city named >
    India-remote / bare remote > India other-city > remote anchored abroad > else.

    'remote +2.0' means remote the candidate can actually take — India-remote or a
    location-agnostic 'Remote' posting. A remote role anchored to a foreign geo
    ('Remote - Colombia', 'Remote, North America', a remote Munich role) is weak for
    an India-based candidate and must not outrank a same-city in-function role — the
    gate (untouched) still lets it through, but ranking demotes it."""
    loc = (job.location or "").lower().strip()
    lp = profile.get("location", {}) or {}
    onsite = [c.lower() for c in (lp.get("onsite_cities") or []) if c]
    is_remote = bool(job.remote) or any(t in loc for t in _REMOTE_TOKENS)
    if onsite and any(c in loc for c in onsite):
        return 2.5                                       # the user's own city — best
    if _match_any(_INDIA_RX, loc):
        return 2.0 if (is_remote and lp.get("remote_ok", True)) else 1.0
    if is_remote and lp.get("remote_ok", True):
        rest = loc
        for t in _REMOTE_TOKENS:
            rest = rest.replace(t, " ")
        rest = re.sub(r"[^a-z]+", " ", rest).strip()     # what geo, if any, the remote is anchored to
        return 2.0 if rest in _BARE_REMOTE_OK else 0.5   # bare remote OK; anchored-abroad remote weak
    return 0.0                                           # onsite elsewhere / unknown


def _seniority_fit(title: str, profile: dict) -> float:
    """Proximity of the title's level to the candidate's honest ceiling. Unknown
    level is neutral-positive (don't punish a title that states no level)."""
    cr = _CEILING_RANK.get(str((profile.get("seniority", {}) or {}).get("honest_ceiling", "mid")).lower(), 2)
    t = (title or "").lower()
    bands = [b for kw, b in _TITLE_BAND if kw in t]
    if not bands:
        # A title that states NO level ("Implementation Consultant", "Business Analyst",
        # "Solutions Consultant") is typically a mid–senior IC, not junior — so don't
        # bury it 1.0 below a "Senior/Manager X"; give a decent, not-penalised credit.
        return 1.0
    gap = cr - max(bands)                                # how far the title sits below the ceiling
    if gap in (0, 1):
        return 1.5                                       # at / just below the ceiling — the sweet spot
    if gap == 2:
        return 0.75
    return 0.0                                           # far below, or above the ceiling


def _fit_proxy(job: JobPosting, profile: dict, role_rx: list[re.Pattern]) -> float:
    """Deterministic FIT-correlated relevance for ranking the kept set before the
    cap — so the top `full_score_top_n` are the most likely fits, not arbitrary
    order. Function match + location + seniority proximity dominate; an AI/domain
    term in the title is only a tie-breaker (was the trump that buried same-city
    in-function roles under any 'AI X' title)."""
    title = job.title or ""
    s = 0.0
    if _match_any(role_rx, title):                       # title in the target role family
        s += 3.0
    s += _location_fit(job, profile)                     # 0 – 2.5
    s += _seniority_fit(title, profile)                  # 0 – 1.5
    if _match_any(_AI_RX, title):                        # AI/domain term in title — tie-breaker only
        s += 0.75
    if _match_any(_COMBO_RX, title):
        s += 0.5
    if _match_any(_AI_RX, (job.description or "")[:2000]):
        s += 0.25
    if job.link_verified:
        s += 0.25
    return s


def prescreen_set(jobs: list[JobPosting], profile: dict,
                  run_cfg: dict | None = None,
                  preferences: dict | None = None) -> tuple[list[JobPosting], dict]:
    """Cut + rank the candidate set to a bounded, scoreable list.

    Returns (kept, report). `kept` is at most `prescreen.max_llm_jobs` jobs,
    ranked best-first. `report` carries the funnel counts and drop-reason
    breakdown for honest logging — including `truncated_from` (set when the cap
    removed jobs, so truncation is never silent).
    """
    run_cfg = run_cfg or {}
    cap = int((run_cfg.get("prescreen", {}) or {}).get("max_llm_jobs", 40))
    role_rx = _compile(_profile_positives(profile))

    kept: list[JobPosting] = []
    dropped: list[tuple[JobPosting, str]] = []
    for j in jobs:
        ok, why = _gate(j, profile, run_cfg, role_rx)
        if ok:
            kept.append(j)
        else:
            dropped.append((j, why))

    # ── Preference layer (revealed feedback): drop already-decided jobs, and
    #    DOWN-RANK established rejected patterns. Soft + logged; never a hidden
    #    hard filter, never overrides the rubric or the cap. ──
    dropped_seen, demoted = [], []
    if preferences:
        from . import preferences as PF
        seen = PF.seen_ids(preferences)
        if seen:
            keep2 = []
            for j in kept:
                if j.id in seen:
                    dropped_seen.append({"title": j.title, "company": j.company, "job_id": j.id})
                else:
                    keep2.append(j)
            kept = keep2
    rel = {}
    for j in kept:
        pen = 0.0
        if preferences:
            hits = PF.negative_hits(j, preferences)
            if hits:
                pen = 1.5 * len(hits)                    # small demotion, not a cliff
                demoted.append({"title": j.title, "company": j.company,
                                "reasons": [f"{c}:{v}" for c, v in hits], "penalty": round(pen, 1)})
        rel[j.id] = _fit_proxy(j, profile, role_rx) - pen
    kept.sort(key=lambda j: (rel.get(j.id, 0.0), j.posted_at or ""), reverse=True)

    truncated_from = None
    if len(kept) > cap:
        truncated_from = len(kept)
        kept = kept[:cap]

    report = {
        "input": len(jobs),
        "kept": len(kept),
        "dropped": len(dropped),
        "cap": cap,
        "truncated_from": truncated_from,
        "by_reason": dict(Counter(why for _, why in dropped).most_common()),
        "dropped_samples": [{"title": j.title, "company": j.company, "reason": why}
                            for j, why in dropped[:200]],
        "dropped_seen": dropped_seen,     # already-decided jobs removed (soft, logged)
        "demoted": demoted,               # look-alikes of rejected patterns, down-ranked
    }
    from .progress import emit as _emit
    _emit(f"prescreen: {len(jobs)}→{len(kept)} (cap {cap})")
    return kept, report


def prescreen(job: JobPosting, profile: dict, run_cfg: dict | None = None) -> tuple[bool, str]:
    """Single-job deterministic verdict (passes, reason) — kept for tests and as
    a safety check. The set-level `prescreen_set` is what bounds a real run."""
    role_rx = _compile(_profile_positives(profile))
    return _gate(job, profile, run_cfg or {}, role_rx)
