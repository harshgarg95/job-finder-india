"""Volume-safety tests for the bounded prescreen. No network, no LLM.

These prove the single most important guarantee: a large candidate set is cut to
a bounded, on-target list BEFORE any LLM call, with a hard cap and honest
(non-silent) truncation.

Run:  python -m pytest tests/test_prescreen.py -q   (or: python tests/test_prescreen.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder.schema import JobPosting
from jobfinder.prescreen import prescreen_set

PROF = {
    "seniority": {"years_total": 8, "honest_ceiling": "manager"},
    "compensation": {"floor_ctc_lpa": 20, "currency": "INR"},
    "location": {"onsite_cities": ["Hyderabad"], "willing_to_relocate": False, "remote_ok": True},
    "target_roles": {
        "primary": ["AI Delivery Manager", "Technical Program Manager - AI", "AI Product Manager"],
        "archetypes": [{"name": "AI Implementation Manager"}],
    },
    "function": {"in_scope": ["AI delivery manager"], "out_of_scope": ["ML research engineer"]},
}
RUN = {"prescreen": {"max_llm_jobs": 40, "seniority_buffer_years": 3}}


def _job(title, location="Hyderabad, India", **kw):
    return JobPosting(title=title, company="C", source="ats:greenhouse", location=location, **kw)


def test_hard_cap_bounds_and_reports_truncation():
    jobs = [_job(f"AI Program Manager {i}") for i in range(60)]
    kept, rep = prescreen_set(jobs, PROF, RUN)
    assert len(kept) == 40                 # never exceeds the cap
    assert rep["cap"] == 40
    assert rep["truncated_from"] == 60     # truncation surfaced, not silent
    assert rep["input"] == 60 and rep["kept"] == 40


def test_huge_set_default_cap_when_no_runcfg():
    jobs = [_job(f"AI Delivery Manager {i}") for i in range(500)]
    kept, rep = prescreen_set(jobs, PROF, None)   # no run_cfg -> default cap 40
    assert len(kept) <= 40


def test_wrong_function_titles_dropped():
    jobs = [
        _job("Data Scientist"), _job("Machine Learning Engineer"), _job("Software Engineer"),
        _job("Account Executive"), _job("Backend Engineer"), _job("ML Research Engineer"),
        _job("AI Delivery Manager"),  # the only keeper
    ]
    kept, rep = prescreen_set(jobs, PROF, RUN)
    titles = {j.title for j in kept}
    assert titles == {"AI Delivery Manager"}
    assert rep["dropped"] == 6


def test_over_senior_titles_dropped():
    for t in ("Director of AI", "VP, Product", "Head of Delivery", "Principal Program Manager",
              "Staff Technical Program Manager", "Chief AI Officer"):
        kept, _ = prescreen_set([_job(t)], PROF, RUN)
        assert kept == [], f"{t!r} should be dropped as over-senior"
    # manager / senior / lead are within ceiling
    assert len(prescreen_set([_job("Senior Product Manager, AI")], PROF, RUN)[0]) == 1


def test_location_hard_constraints():
    keep_hyd = _job("AI Program Manager", location="Hyderabad, Telangana, India")
    keep_remote = _job("AI Program Manager", location="Remote, India")
    drop_blr = _job("AI Program Manager", location="Bengaluru, India")
    drop_foreign = _job("AI Program Manager", location="Remote, US")
    kept, _ = prescreen_set([keep_hyd, keep_remote, drop_blr, drop_foreign], PROF, RUN)
    locs = {j.location for j in kept}
    assert "Hyderabad, Telangana, India" in locs and "Remote, India" in locs
    assert "Bengaluru, India" not in locs        # non-Hyderabad onsite dropped
    assert "Remote, US" not in locs              # foreign-remote dropped


def test_combo_keeps_real_roles_but_not_ic_with_buzzword():
    keep = _job("GenAI Product Lead")                       # head (lead/product) + AI
    drop = _job("Senior Systems Engineer (Python, GenAI)")  # IC engineer, buzzword only
    kept, _ = prescreen_set([keep, drop], PROF, RUN)
    titles = {j.title for j in kept}
    assert "GenAI Product Lead" in titles
    assert "Senior Systems Engineer (Python, GenAI)" not in titles


def test_no_title_dropped_and_reasons_recorded():
    kept, rep = prescreen_set([_job("")], PROF, RUN)
    assert kept == [] and rep["by_reason"]


def test_ranking_prefers_ai_titles():
    plain = _job("Program Manager")
    ai = _job("AI Program Manager")
    kept, _ = prescreen_set([plain, ai], PROF, {"prescreen": {"max_llm_jobs": 1}})
    assert kept and kept[0].title == "AI Program Manager"   # AI-in-title ranks higher


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
