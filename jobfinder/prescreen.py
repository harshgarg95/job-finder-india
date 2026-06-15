"""Tier-0 pre-screen — a free, deterministic gate before any LLM call.

The owner's idea: don't full-evaluate obvious no's. The safest, cheapest version
uses the STRUCTURED fields we already have (experience bands + salary, strongest
from Naukri/Apify) against the profile's [GATE] values. It rejects only CLEAR,
citable mismatches; anything uncertain passes through to the full-JD LLM scoring.

Crucially this is a COST FILTER, not the fit verdict — it never *advances* a job
on thin signal (that would risk the buried-requirement trap the owner found in
round 2); it only removes the unambiguous misfits (over-senior, below-floor)
that an LLM pass would also reject, saving the call.
"""

from __future__ import annotations

from .schema import JobPosting


def prescreen(job: JobPosting, profile: dict) -> tuple[bool, str]:
    """Return (passes, reason). passes=False → skip the LLM, deterministic
    DON'T APPLY with `reason`. Conservative: only rejects clear structured misfits."""
    sen = profile.get("seniority", {}) or {}
    comp = profile.get("compensation", {}) or {}
    years_total = sen.get("years_total")

    # 1) Experience requirement clearly beyond reach (e.g. a 12+/15+/20-yr role
    #    for an ~8-yr candidate). Buffer of +3 so borderline cases still get the
    #    full LLM read.
    if job.experience_min is not None and years_total:
        if job.experience_min >= years_total + 3:
            return False, (f"JD requires {job.experience_min:g}+ years; you have ~{years_total:g} "
                           f"total — clearly above your level.")

    # 2) Disclosed comp clearly below the walk-away floor (INR/LPA). Only fires
    #    when salary is actually stated (most Naukri posts hide it → pass through).
    floor = comp.get("floor_ctc_lpa")
    if floor and job.salary_max and (job.salary_currency in (None, "INR", "inr", "Rs", "INR ")):
        lpa = job.salary_max / 100000.0          # rupees → lakhs/annum
        if 0 < lpa < floor:
            return False, (f"Stated max comp ~{lpa:.0f} LPA is below your floor of "
                           f"{floor:g} LPA.")

    return True, ""
