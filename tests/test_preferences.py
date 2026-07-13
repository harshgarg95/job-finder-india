"""Feedback loop + preference layer tests. No network, no model.

Proves: feedback persists + dedupes (incl. new actions); the preference layer
derives negative/positive/seen correctly; prescreen down-ranks an established
rejected pattern and drops already-decided jobs on the next run; clearing resets.
The scoring law (prompts/_rubric.md) is never touched by any of this.

Run:  python -m pytest tests/test_preferences.py -q  (or: python tests/test_preferences.py)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import feedback as FB
from jobfinder import preferences as PF
from jobfinder.prescreen import prescreen_set
from jobfinder.schema import JobPosting

PROF = {
    "seniority": {"years_total": 8},
    "target_roles": {"primary": ["AI Delivery Manager", "AI Program Manager", "Product Manager"]},
    "function": {"in_scope": ["AI delivery manager"]},
    "location": {"onsite_cities": ["Hyderabad"], "willing_to_relocate": False},
}
RUN = {"prescreen": {"max_llm_jobs": 40}}


def _isolate():
    """Point feedback + preferences at a throwaway dir (never touch real data/)."""
    d = tempfile.mkdtemp(prefix="jf-pref-")
    FB.DATA = d
    FB.FB_JSONL = os.path.join(d, "feedback.jsonl")
    FB.FB_MD = os.path.join(d, "feedback.md")
    PF.CONFIG = d
    PF.DATA = d
    PF.PREFS_PATH = os.path.join(d, "preferences.yml")
    PF.TRACKER_JSONL = os.path.join(d, "tracker.jsonl")
    return d


def test_feedback_new_actions_persist_and_dedupe():
    _isolate()
    FB.record("j1", "GitLab", "Customer Success Manager", "u", "wrong_function")
    FB.record("j1", "GitLab", "Customer Success Manager", "u", "interested")   # changed mind
    FB.record("j2", "HighRadius", "AI Delivery Manager", "u", "applied")
    entries = FB.load()
    assert len(entries) == 3                        # all appended
    latest = FB._latest(entries)
    assert {e["job_id"]: e["action"] for e in latest} == {"j1": "interested", "j2": "applied"}
    assert "interested" in FB.ACTIONS and "wrong_company" in FB.ACTIONS
    assert FB.ACTIONS["interested"][1] is False     # positive, NON-suppressing


def test_preferences_derive_and_refresh():
    _isolate()
    FB.record("a", "GitLab", "Customer Success Manager", "u", "wrong_function")
    FB.record("b", "PostHog", "Customer Success Engineer", "u", "wrong_function")
    FB.record("c", "BadCo", "Data Scientist", "u", "wrong_company")
    FB.record("d", "HighRadius", "AI Delivery Manager", "u", "applied")
    prefs = PF.refresh()
    negfn = {i["value"]: i["count"] for i in prefs["negative"]["functions"]}
    assert negfn.get("customer success") == 2                       # established pattern
    assert any(i["value"] == "badco" for i in prefs["negative"]["companies"])
    assert any(i["value"] == "delivery" for i in prefs["positive"]["functions"])
    assert set(prefs["seen"]["applied"]) == {"d"}
    assert {"a", "b", "c"} <= set(prefs["seen"]["rejected"])


def test_prescreen_demotes_established_rejected_pattern():
    _isolate()
    FB.record("a", "GitLab", "Customer Success Manager", "u", "wrong_function")
    FB.record("b", "PostHog", "Customer Success Manager", "u", "wrong_function")
    prefs = PF.refresh()
    clean = JobPosting(title="AI Delivery Manager", company="Acme", source="ats:greenhouse",
                       location="Hyderabad, India", url="https://c/1")
    match = JobPosting(title="Senior Customer Success Manager", company="Zeta", source="ats:greenhouse",
                       location="Hyderabad, India", url="https://c/2")
    kept, rep = prescreen_set([match, clean], PROF, {"prescreen": {"max_llm_jobs": 1}}, preferences=prefs)
    assert [j.title for j in kept] == ["AI Delivery Manager"]       # clean wins the 1 slot
    assert rep["demoted"] and rep["demoted"][0]["company"] == "Zeta"
    # without preferences, the demotion doesn't happen (control)
    kept2, _ = prescreen_set([match, clean], PROF, {"prescreen": {"max_llm_jobs": 2}})
    assert len(kept2) == 2


def test_seen_job_dropped_then_clear_resets():
    _isolate()
    j = JobPosting(title="AI Delivery Manager", company="X", source="ats:greenhouse",
                   location="Hyderabad, India", url="https://z/seen")
    FB.record(j.id, "X", j.title, j.url, "wrong_function")          # you've decided on this exact job
    prefs = PF.refresh()
    kept, rep = prescreen_set([j], PROF, RUN, preferences=prefs)
    assert kept == [] and rep["dropped_seen"] and rep["dropped_seen"][0]["job_id"] == j.id
    PF.clear()                                                      # reset learning
    kept2, _ = prescreen_set([j], PROF, RUN, preferences=PF.load())
    assert kept2 == [j]                                            # no longer suppressed


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
