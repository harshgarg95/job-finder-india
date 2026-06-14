"""Mechanical smoke tests — contracts, not scoring quality.

Scoring QUALITY is verified by a human reading JDs against the resume (the MVP
gate), never by these tests. These only prove the plumbing holds.

Run:  python -m pytest tests/ -q     (or: python tests/test_smoke.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder.schema import JobPosting
from jobfinder.dedup import dedupe
from jobfinder.filters import location_ok, keyword_prefilter
from jobfinder.cli_adapter import _extract_json, detect_clis
from jobfinder import score
from jobfinder.discovery import link_resolver as L


PROFILE = {
    "location": {"remote_ok": True},
    "target_roles": {"primary": ["AI Delivery Manager"], "archetypes": [{"name": "AI Program Manager"}]},
    "function": {"in_scope": ["AI implementation manager"]},
}


def test_jobposting_id_and_roundtrip():
    j = JobPosting(title="AI Delivery Manager", company="Acme", source="ats:greenhouse", url="https://x/y")
    assert len(j.id) == 16
    j2 = JobPosting.from_dict(j.to_dict())
    assert j2.id == j.id and j2.title == j.title


def test_scoring_view_marks_unknowns():
    j = JobPosting(title="X", company="Y", source="s")
    v = j.scoring_view()
    assert "not stated" in v  # missing experience/comp shown honestly, not faked


def test_dedupe_collapses_same_company_title():
    a = JobPosting(title="Implementation Consultant", company="HighRadius", source="ats:greenhouse",
                   url="https://a", description="short")
    b = JobPosting(title="Implementation Consultant", company="HighRadius", source="google_jobs",
                   url="https://b", description="a much longer richer description "*5)
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0].description.startswith("a much longer")  # keeps the richer one


def test_location_filter_india_vs_foreign():
    keep = JobPosting(title="t", company="c", source="s", location="Bengaluru, India")
    drop = JobPosting(title="t", company="c", source="s", location="Remote - France")
    drop2 = JobPosting(title="t", company="c", source="s", location="SF, SEA, NYC, US - Remote")
    blank = JobPosting(title="t", company="c", source="s", location="")
    assert location_ok(keep, PROFILE) is True
    assert location_ok(drop, PROFILE) is False
    assert location_ok(drop2, PROFILE) is False
    assert location_ok(blank, PROFILE) is True  # unknown -> let scorer judge


def test_keyword_prefilter_keeps_relevant_drops_noise():
    good = JobPosting(title="AI Program Manager", company="c", source="s", description="lead AI delivery")
    noise = JobPosting(title="Dental Receptionist", company="c", source="s", description="answer phones")
    out = keyword_prefilter([good, noise], PROFILE, ["AI Delivery Manager"])
    assert good in out and noise not in out


def test_extract_json_from_noisy_stdout():
    stdout = 'Here is the result:\n```json\n{"fit_score": 1.5, "verdict": "DON\'T APPLY"}\n```\nDone.'
    parsed = _extract_json(stdout)
    assert parsed and parsed["fit_score"] == 1.5


def test_link_tier_classification():
    # lower tier = better source (deterministic, no network)
    assert L._tier("https://job-boards.greenhouse.io/x/jobs/1", "X")[0] == 1   # employer ATS
    assert L._tier("https://careers.acmecorp.com/job/1", "AcmeCorp")[0] == 1   # employer site
    assert L._tier("https://www.linkedin.com/jobs/view/1", "X")[0] == 2        # platform
    assert L._tier("https://www.naukri.com/job-1", "X")[0] == 2
    assert L._tier("https://in.indeed.com/viewjob?jk=1", "X")[0] == 3          # board
    assert L._tier("https://www.talent.com/view?id=1", "X")[0] == 4            # junk
    assert L._tier("https://jooble.org/jdp/1", "X")[0] == 4


def test_distinctive_token_survival_logic():
    # job-id token extracted from the path (used to detect soft-404 redirects)
    assert L._distinctive_token("https://job-boards.greenhouse.io/x/jobs/7719673003") == "7719673003"
    assert L._distinctive_token("https://jobs.lever.co/x/3fa1c0de-aaaa-bbbb") != ""
    assert L._distinctive_token("https://acme.com/careers") == ""  # no id -> check skipped


def test_resolve_best_prefers_employer_skips_junk_no_network():
    opts = [
        {"title": "Talent", "link": "https://www.talent.com/view?id=junk"},
        {"title": "LinkedIn", "link": "https://www.linkedin.com/jobs/view/1"},
        {"title": "Acme", "link": "https://job-boards.greenhouse.io/acme/jobs/999"},
    ]
    res = L.resolve_best(opts, "Acme", "PM", verify=False)  # ranking only, no HTTP
    assert "greenhouse.io" in res.url  # employer tier wins over linkedin/junk


def test_build_prompt_contains_rubric_and_inputs():
    j = JobPosting(title="ML Research Engineer", company="DeepCo", source="s", description="train models")
    p = score.build_prompt("RESUME TEXT HERE", PROFILE, j)
    assert "Honest Fit Rubric" in p          # rubric injected
    assert "RESUME TEXT HERE" in p           # resume injected
    assert "ML Research Engineer" in p       # job injected
    assert "emit exactly one JSON object" in p.lower() or "one JSON object" in p


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
