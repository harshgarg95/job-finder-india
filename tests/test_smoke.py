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
from jobfinder import feedback as FB
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
    assert L._tier("https://www.google.com/search?q=jobs", "X")[0] == 4        # google-search = junk
    assert L._tier("https://hirevista.x.infinityfree.me/job/1", "X")[0] == 4   # free-host spam
    assert L._tier("https://some-random-aggregator.xyz/job/1", "X")[0] == 5    # unknown = untrusted


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


def test_prescreen_tier0_gate_no_io():
    from jobfinder.prescreen import prescreen
    prof = {"seniority": {"years_total": 8}, "compensation": {"floor_ctc_lpa": 20}}
    # over-senior requirement (15+ vs 8) -> reject
    over = JobPosting(title="Director", company="C", source="apify:naukri", experience_min=15)
    ok, why = prescreen(over, prof); assert not ok and "15" in why
    # comp below floor (8 LPA < 20) -> reject
    low = JobPosting(title="PM", company="C", source="apify:naukri", salary_max=800000, salary_currency="INR")
    ok, why = prescreen(low, prof); assert not ok and "floor" in why.lower()
    # borderline experience (9 vs 8, within +3 buffer) -> pass to LLM
    bord = JobPosting(title="PM", company="C", source="apify:naukri", experience_min=9)
    assert prescreen(bord, prof)[0] is True
    # unknown fields -> pass (don't reject on missing data)
    assert prescreen(JobPosting(title="PM", company="C", source="s"), prof)[0] is True


def test_cli_failover_on_quota_error():
    # gemini "quota exhausted" -> fail over to next CLI, no network (runner injected)
    import os
    from jobfinder import cli_adapter as CA
    os.environ["JOBFINDER_CLI_FALLBACK"] = "claude"
    def runner(argv, stdin_text):
        if argv[0] == "gemini":
            raise RuntimeError("TerminalQuotaError: you have exhausted your capacity")
        return '{"fit_score": 3.0, "verdict": "STRETCH"}'
    switched = {}
    out = CA.score("p", cli="gemini", runner=runner,
                   on_failover=lambda f, t, w: switched.update({"f": f, "t": t}))
    assert out["fit_score"] == 3.0 and out["_scored_by"] == "claude"
    assert switched == {"f": "gemini", "t": "claude"}
    os.environ.pop("JOBFINDER_CLI_FALLBACK", None)


def test_cli_large_prompt_uses_stdin():
    from jobfinder import cli_adapter as CA
    seen = {}
    def runner(argv, stdin_text):
        seen["argv_len"] = len(argv); seen["stdin_len"] = len(stdin_text)
        return '{"ok": 1}'
    big = "x" * (CA.SAFE_ARG + 50)
    CA.score(big, cli="gemini", runner=runner)  # gemini is arg-delivery
    assert seen["stdin_len"] > CA.SAFE_ARG and seen["argv_len"] == 2  # prompt went to stdin, not argv


def test_apify_url_builders_and_mappers_no_io():
    from jobfinder.discovery import apify as AP
    nk = AP._naukri_url("AI Program Manager", "Hyderabad")
    assert nk.startswith("https://www.naukri.com/ai-program-manager-jobs-in-hyderabad")
    assert "k=AI%20Program%20Manager" in nk   # keyword search param (relevance fix)
    assert "keywords=AI%20Program%20Manager" in AP._linkedin_url("AI Program Manager", "Hyderabad")
    assert "in.indeed.com/jobs" in AP._indeed_url("AI PM", "Hyderabad")
    # naukri: relative jdURL -> absolute; hidden salary -> "Not disclosed"; exp parsed
    n = AP._map_naukri({"title": "PM", "companyName": "Acme", "jdURL": "/job-listings-x-123",
                        "minimumExperience": "5", "maximumExperience": "10",
                        "salaryDetail": {"minimumSalary": 0, "maximumSalary": 0, "hideSalary": True},
                        "placeholders": [{"type": "location", "label": "Hyderabad"}], "tagsAndSkills": "AI,PM"})
    assert n.url == "https://www.naukri.com/job-listings-x-123" and n.experience_min == 5.0
    assert n.location == "Hyderabad" and n.salary_text == "Not disclosed" and n.link_verified is True
    # indeed: expired -> dropped
    assert AP._map_indeed({"positionName": "X", "isExpired": True}) is None
    assert AP._map_linkedin({"title": "TPM", "link": "https://in.linkedin.com/jobs/view/1"}).source == "apify:linkedin"


def test_feedback_suppress_and_lessons_no_io():
    # pure functions on synthetic entries — no file writes
    entries = [
        {"job_id": "a1", "company": "Acme", "title": "PM", "action": "wouldnt_apply", "note": "too junior"},
        {"job_id": "b2", "company": "Beta", "title": "TPM", "action": "wrong_location", "note": "Bengaluru"},
        {"job_id": "c3", "company": "Gamma", "title": "Lead", "action": "good_match", "note": ""},
    ]
    sup = FB.suppressed_ids(entries)
    assert "a1" in sup and "b2" in sup     # rejections suppress
    assert "c3" not in sup                  # good_match does not suppress
    digest = FB.lessons_digest(entries)
    assert "PRIOR USER CORRECTIONS" in digest and "Bengaluru" in digest
    assert FB.stats(entries)["wouldnt_apply"] == 1


def test_feedback_rejects_unknown_action():
    # validation happens before any file write, so this is safe + does no I/O
    try:
        FB.record("id", "Co", "Title", "url", "bogus_action")
        assert False, "should have raised on unknown action"
    except ValueError:
        pass


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
