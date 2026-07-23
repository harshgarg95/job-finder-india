"""Offline tests for the prompt-pack agent tools (no network, no model).

Covers the two deterministic tools the in-CLI flow leans on: `prescreen` (the
volume cap) and `tracker` (upsert by job_id). `discover`/`enrich` hit the network
and are validated live, not here.

Run:  python -m pytest tests/test_agent_tools.py -q  (or: python tests/test_agent_tools.py)
"""

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import agent_tools as AT
from jobfinder import score as SC
from jobfinder.schema import JobPosting


def _isolate():
    """Point both result dirs at a throwaway dir so tests never touch real data/."""
    d = tempfile.mkdtemp(prefix="jf-at-")
    AT.RESULTS = d
    SC.DATA = d
    return d


def _run(fn, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


def test_prescreen_tool_caps_and_emits_rule():
    d = _isolate()
    jobs = [JobPosting(title=f"AI Program Manager {i}", company="C", source="ats:greenhouse",
                       location="Hyderabad, India", url=f"https://x/{i}") for i in range(50)]
    with open(os.path.join(d, "candidates.jsonl"), "w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j.to_dict()) + "\n")
    rc, out = _run(AT.cmd_prescreen, [])
    data = json.loads(out)
    assert rc == 0
    assert data["kept"] <= data["cap"] and data["kept"] <= 40        # the hard cap holds
    assert data["input"] == 50 and data["truncated_from"] == 50
    assert "ONLY" in data["RULE"] and "score_these" in data          # FIX B: full-score cutoff
    assert data["full_score_top_n"] == 15 and len(data["score_these"]) <= 15
    assert os.path.exists(os.path.join(d, "prescreened.jsonl"))


def test_prescreen_tool_errors_without_candidates():
    d = _isolate()
    rc, out = _run(AT.cmd_prescreen, [])
    assert rc == 1 and "candidates.jsonl missing" in json.loads(out)["error"]


def test_tracker_tool_upserts_by_job_id():
    d = _isolate()
    v1 = {"job_id": "abc", "company": "C", "title": "AI PM", "url": "https://x",
          "fit_score": 3.5, "verdict": "STRETCH", "headline": "ok"}
    p1 = os.path.join(d, "v1.json"); json.dump(v1, open(p1, "w"))
    rc, _ = _run(AT.cmd_tracker, ["--add", p1])
    assert rc == 0
    rows = [json.loads(l) for l in open(os.path.join(d, "scored.jsonl"))]
    assert len(rows) == 1 and rows[0]["fit_score"] == 3.5

    # same job_id, new verdict → replaced, not duplicated
    v2 = dict(v1, fit_score=1.5, verdict="DON'T APPLY")
    p2 = os.path.join(d, "v2.json"); json.dump(v2, open(p2, "w"))
    _run(AT.cmd_tracker, ["--add", p2])
    rows = [json.loads(l) for l in open(os.path.join(d, "scored.jsonl"))]
    assert len(rows) == 1 and rows[0]["fit_score"] == 1.5
    assert os.path.exists(os.path.join(d, "top.md"))


def test_tracker_rejects_no_id_but_surfaces_malformed():
    d = _isolate()
    # no id at all → still a hard reject (can't track it)
    p = os.path.join(d, "bad.json"); json.dump({"title": "no id, no score"}, open(p, "w"))
    rc, out = _run(AT.cmd_tracker, ["--add", p])
    assert rc == 1 and "job_id" in json.loads(out)["error"]
    # has id but no score/verdict/headline → NOT rejected: surfaced as malformed (never silently dropped)
    p2 = os.path.join(d, "bad2.json"); json.dump({"job_id": "z", "title": "x", "url": "https://x/1"}, open(p2, "w"))
    rc2, out2 = _run(AT.cmd_tracker, ["--add", p2])
    resp = json.loads(out2.strip().splitlines()[-1])
    assert rc2 == 0 and resp["malformed"] is True and "malformed" in resp["reason"]
    top = open(os.path.join(d, "top.md"), encoding="utf-8").read()
    assert "Couldn't verify" in top and "malformed" in top          # surfaced loudly, NOT "Filtered out"
    print("✓ tracker: no-id rejected; a malformed record is surfaced (Couldn't-verify), never dropped")


def test_tracker_normalizes_lowercase_verdict_and_string_score():
    d = _isolate()
    v = {"job_id": "lc1", "company": "Google", "title": "TPM AI", "url": "https://x/jobs/9",
         "verdict": "apply", "fit_score": "4.0", "headline": "APPLY — strong TPM-AI fit"}
    p = os.path.join(d, "v.json"); json.dump(v, open(p, "w"))
    rc, _ = _run(AT.cmd_tracker, ["--add", p])
    assert rc == 0
    row = [json.loads(l) for l in open(os.path.join(d, "scored.jsonl"))][0]
    assert row["verdict"] == "APPLY" and row["fit_score"] == 4.0 and not row.get("unverifiable")
    top = open(os.path.join(d, "top.md"), encoding="utf-8").read()
    assert "1 APPLY" in top and "TPM AI" in top                     # bucketed as APPLY (was "0 APPLY" before fix)
    print("✓ tracker: lowercase verdict + string fit_score → canonical APPLY, bucketed correctly (not Filtered)")


def test_tracker_tool_accepts_unverifiable_record():
    d = _isolate()
    rec = {"job_id": "u1", "title": "AI PM", "company": "Acme", "url": "https://acme.com/careers",
           "unverifiable": True, "reason": "careers landing page — no specific posting"}
    p = os.path.join(d, "u.json"); json.dump(rec, open(p, "w"))
    rc, out = _run(AT.cmd_tracker, ["--add", p])
    assert rc == 0
    # the JSON response is the last stdout line (write_outputs prints progress first)
    resp = json.loads(out.strip().splitlines()[-1])
    assert resp["unverifiable"] is True
    top = open(os.path.join(d, "top.md"), encoding="utf-8").read()
    assert "Couldn't verify" in top and "AI PM" in top


def test_live_tool_maps_status_to_liveness():
    d = _isolate()
    j = JobPosting(title="AI PM", company="C", source="ats:greenhouse",
                   url="https://x/jobs/123", location="India")
    with open(os.path.join(d, "prescreened.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(j.to_dict()) + "\n")
    import jobfinder.discovery.link_resolver as LR
    from jobfinder.discovery.link_resolver import Resolved

    LR.verify_link = lambda url, company="", title="": Resolved(url, "employer-ats", True, "ok", url)
    rc, out = _run(AT.cmd_live, [j.id])
    assert rc == 0 and json.loads(out)["liveness"] == "active"

    LR.verify_link = lambda url, company="", title="": Resolved(url, "dead", False, "dead", url)
    _, out = _run(AT.cmd_live, [j.id])
    assert json.loads(out)["liveness"] == "expired"

    LR.verify_link = lambda url, company="", title="": Resolved(url, "x", False, "unreachable", url)
    _, out = _run(AT.cmd_live, ["https://direct.example/jobs/9"])   # URL-direct mode
    assert json.loads(out)["liveness"] == "unknown"


def test_prescreen_couldnt_verify_excluded_from_score_these():
    d = _isolate()
    good = [JobPosting(title=f"AI Delivery Manager {i}", company="C", source="ats:greenhouse",
                       location="Hyderabad, India", url=f"https://boards.greenhouse.io/c/jobs/{1000 + i}")
            for i in range(5)]
    bad = [JobPosting(title="AI Program Manager", company="BareCo", source="ats:greenhouse",
                      location="Hyderabad, India", url="https://bareco.example"),          # bare domain
           JobPosting(title="AI Product Manager", company="LandCo", source="ats:greenhouse",
                      location="Hyderabad, India", url="https://landco.example/careers")]  # careers landing
    with open(os.path.join(d, "candidates.jsonl"), "w", encoding="utf-8") as f:
        for j in good + bad:
            f.write(json.dumps(j.to_dict()) + "\n")
    rc, out = _run(AT.cmd_prescreen, [])
    data = json.loads(out)
    st_ids = {r["job_id"] for r in data["score_these"]}
    cv_ids = {r["job_id"] for r in data["couldnt_verify"]}
    bad_ids = {j.id for j in bad}
    assert rc == 0
    assert bad_ids == cv_ids                              # both URL non-job-links → couldnt_verify
    assert not (st_ids & bad_ids)                         # ...and NONE consume a scoring slot
    assert all(r.get("reason") for r in data["couldnt_verify"])   # surfaced with a reason, not silent
    assert len(data["score_these"]) == 5                 # the 5 verifiable fill the slots
    print("✓ FIX 2: URL non-job-links → couldnt_verify (with reason), never in score_these")


def test_evaluate_surfaces_review_before_next_actions():
    md = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "modes", "evaluate.md"), encoding="utf-8").read()
    low = md.lower()
    review_pos = low.find("review & learn")
    next_pos = low.find("offer next actions")
    assert 0 < review_pos < next_pos                     # FIX 3: review fires BEFORE the Done-able menu
    assert "immediately after top.md" in low             # explicitly positioned right after Present
    assert "python -m jobfinder dashboard" in md         # the alternative review surface pointer
    print("✓ FIX 3: evaluate.md surfaces the feedback review after top.md, before next-actions; dashboard pointer present")


def test_tracker_status_reports_remaining():
    d = _isolate()
    json.dump({"ids": ["a", "b", "c"], "target": 3}, open(os.path.join(d, "score_these.json"), "w"))
    _, out = _run(AT.cmd_tracker, ["--status", "--json"])
    st = json.loads(out.strip().splitlines()[-1])
    assert st == {"target": 3, "scored": 0, "remaining": 3, "remaining_ids": ["a", "b", "c"], "complete": False}
    v = {"job_id": "a", "title": "A", "company": "C", "url": "https://x/1",
         "verdict": "APPLY", "fit_score": 4.0, "headline": "APPLY — a"}
    p = os.path.join(d, "va.json"); json.dump(v, open(p, "w"))
    _run(AT.cmd_tracker, ["--add", p])
    st2 = json.loads(_run(AT.cmd_tracker, ["--status", "--json"])[1].strip().splitlines()[-1])
    assert st2["scored"] == 1 and st2["remaining"] == 2 and st2["remaining_ids"] == ["b", "c"] and st2["complete"] is False
    print("✓ tracker --status: target/scored/remaining/remaining_ids from score_these vs scored.jsonl")


def test_tracker_partial_run_stamps_incomplete_banner():
    d = _isolate()
    json.dump({"ids": ["a", "b", "c"], "target": 3}, open(os.path.join(d, "score_these.json"), "w"))
    v = {"job_id": "a", "title": "A", "company": "C", "url": "https://x/1",
         "verdict": "APPLY", "fit_score": 4.0, "headline": "APPLY — a"}
    p = os.path.join(d, "va.json"); json.dump(v, open(p, "w"))
    _run(AT.cmd_tracker, ["--add", p])
    top = open(os.path.join(d, "top.md"), encoding="utf-8").read()
    assert "Scored 1 of 3" in top and "incomplete" in top          # partial → LOUD banner
    for jid in ("b", "c"):                                          # complete the set → banner gone
        pp = os.path.join(d, f"v{jid}.json"); json.dump(dict(v, job_id=jid, url=f"https://x/{jid}"), open(pp, "w"))
        _run(AT.cmd_tracker, ["--add", pp])
    assert "incomplete" not in open(os.path.join(d, "top.md"), encoding="utf-8").read()
    print("✓ top.md carries 'Scored N of M — incomplete' on a partial run; gone at N==M")


def test_tracker_add_accepts_multi_verdict_jsonl():
    d = _isolate()
    jl = os.path.join(d, "batch.jsonl")
    with open(jl, "w", encoding="utf-8") as f:
        for jid, verd, sc in (("a", "APPLY", 4.2), ("b", "STRETCH", 3.4), ("c", "DON'T APPLY", 1.5)):
            f.write(json.dumps({"job_id": jid, "title": jid, "company": "C", "url": f"https://x/{jid}",
                                "verdict": verd, "fit_score": sc, "headline": f"{verd} — {jid}"}) + "\n")
    rc, out = _run(AT.cmd_tracker, ["--add", jl])
    resp = json.loads(out.strip().splitlines()[-1])
    assert rc == 0 and resp["count"] == 3 and set(resp["added"]) == {"a", "b", "c"}
    rows = [json.loads(l) for l in open(os.path.join(d, "scored.jsonl"))]
    assert {r["job_id"] for r in rows} == {"a", "b", "c"}          # all upserted in ONE call
    print("✓ tracker --add accepts a multi-verdict JSONL (batch) — all upserted in one call")


def test_tracker_cap_enforced_lands_in_filtered_with_note():
    d = _isolate()
    v = {"job_id": "gl", "title": "Senior Program Manager", "company": "GitLab", "url": "https://x/jobs/1",
         "verdict": "STRETCH", "fit_score": 3.5, "headline": "STRETCH — remote-Bangalore PgM",
         "caps_applied": ["seniority_ceiling_under->2.0", "missing_named_methodology->2.5"]}
    p = os.path.join(d, "v.json"); json.dump(v, open(p, "w"))
    _run(AT.cmd_tracker, ["--add", p])
    row = [json.loads(l) for l in open(os.path.join(d, "scored.jsonl"))][0]
    assert row["fit_score"] == 2.0 and row["verdict"] == "DON'T APPLY"      # capped + re-derived on write
    top = open(os.path.join(d, "top.md"), encoding="utf-8").read()
    assert "Cap enforced: 3.5 → 2.0" in top                                 # surfaced in top.md (via headline)
    assert top.find("Senior Program Manager") > top.find("Filtered out")    # bucketed as DON'T APPLY
    print("✓ cap-enforced job lands in Filtered with the '3.5 → 2.0' note in top.md (score.py untouched)")


def test_discover_refuses_mid_scoring_allows_force():
    d = _isolate()
    from jobfinder import state
    state.STATE_DIR = os.path.join(d, ".state")
    json.dump({"ids": ["a", "b", "c"], "target": 3}, open(os.path.join(d, "score_these.json"), "w"))
    open(os.path.join(d, "scored.jsonl"), "w").write(
        json.dumps({"job_id": "a", "verdict": "APPLY", "fit_score": 4.0, "headline": "x"}) + "\n")   # 1 of 3
    rc, out = _run(AT.cmd_discover, [])                                     # remaining 2 → refuse (no network)
    assert rc == 1 and "scoring in progress" in json.loads(out.strip().splitlines()[-1])["error"]

    from jobfinder.discovery import registry

    class Empty:
        id = "ats"
        gap_fill_after = None
        last_errors: list = []

        def enabled(self, cfg):
            return True

        def fetch(self, q, cfg):
            return []

    saved = registry.build_providers
    registry.build_providers = lambda cfg: [Empty()]
    try:
        rc2, out2 = _run(AT.cmd_discover, ["--force"])                      # --force bypasses the guard
    finally:
        registry.build_providers = saved
    assert rc2 == 0 and "scoring in progress" not in out2                   # proceeded past the guard
    print("✓ discover refuses mid-scoring (remaining>0); --force bypasses the guard")


def test_scoring_status_unreadable_fails_toward_cant_verify():
    d = _isolate()
    open(os.path.join(d, "score_these.json"), "w").write("{corrupt")
    st = AT.scoring_status()
    assert st["unreadable"] is True and st["complete"] is False
    assert st["target"] is None and st["remaining"] is None                 # never {target:0, remaining:0}
    assert "cannot be verified" in st["warning"]
    # tracker --status carries the state + warning
    rc, out = _run(AT.cmd_tracker, ["--status"])
    rep = json.loads(out)
    assert rc == 0 and rep["unreadable"] is True and "cannot be verified" in rep["warning"]
    # top.md gets the loud unreadable banner (not the N-of-M one, not silence)
    open(os.path.join(d, "top.md"), "w").write("# Top matches\n\nbody\n")
    AT._stamp_incomplete_banner(st)
    top = open(os.path.join(d, "top.md")).read()
    assert "unreadable" in top and "cannot be verified" in top
    # regression: a MISSING file is still the honest "nothing in progress" state
    os.remove(os.path.join(d, "score_these.json"))
    st2 = AT.scoring_status()
    assert st2["target"] == 0 and "unreadable" not in st2
    print("✓ corrupt score_these.json → unreadable state, loud banner; missing file unchanged")


def test_discover_refuses_on_unreadable_progress_file():
    d = _isolate()
    from jobfinder import state
    state.STATE_DIR = os.path.join(d, ".state")
    open(os.path.join(d, "score_these.json"), "w").write("NOT JSON")
    rc, out = _run(AT.cmd_discover, [])                 # guard fires before any network
    err = json.loads(out.strip().splitlines()[-1])["error"]
    assert rc == 1 and "unreadable" in err and "--force" in err
    print("✓ discover refuses on an unreadable progress file (fails toward can't-verify)")


def test_discover_prefilter_note_when_keywords_zero_the_funnel():
    d = _isolate()
    from jobfinder import state
    state.STATE_DIR = os.path.join(d, ".state")
    from jobfinder.discovery import registry

    class Acct:                                          # obvious non-matches for ANY keyword set
        id = "ats"
        gap_fill_after = None
        last_errors: list = []

        def enabled(self, cfg):
            return True

        def fetch(self, q, cfg):
            return [JobPosting(title=f"Chartered Accountant {i}", company="C", source="ats:greenhouse",
                               location="Chennai, India", url=f"https://x/{i}",
                               description="Taxation, audit and statutory compliance.")
                    for i in range(3)]

    profile = {"target_roles": {"primary": []}, "function": {"in_scope": []},
               "location": {"willing_to_relocate": False, "base_city": "Chennai"}}
    saved_load, saved_bp = AT._load, registry.build_providers
    AT._load = lambda: (profile, {}, {}, {"profile": profile, "run": {}, "sources": {}, "tenants": []})
    registry.build_providers = lambda cfg: [Acct()]
    try:
        rc, out = _run(AT.cmd_discover, [])
    finally:
        AT._load, registry.build_providers = saved_load, saved_bp
    rep = json.loads(out)
    assert rc == 0 and rep["raw"] == 3 and rep["candidates"] == 0
    assert "all 3 raw jobs failed the keyword prefilter" in rep["prefilter_note"]
    assert "target_roles" in rep["prefilter_note"]       # points at the likely cause
    print("✓ keyword prefilter zeroing the funnel surfaces prefilter_note — not an honest-looking 0")


def test_enrich_reports_jd_provenance_deterministically():
    d = _isolate()
    j = JobPosting(title="AI Program Manager", company="C", source="ats:greenhouse",
                   location="Hyderabad, India", url="https://x/jobs/1",
                   description="A short snippet. " * 20)             # ~340 chars — over the 200 floor
    open(os.path.join(d, "prescreened.jsonl"), "w").write(json.dumps(j.to_dict()) + "\n")
    from jobfinder.discovery import job_fetcher
    saved = job_fetcher.enrich
    job_fetcher.enrich = lambda job, min_len=job_fetcher.FULL_JD_MIN: False   # deep-fetch FAILED
    try:
        rc, out = _run(AT.cmd_enrich, [j.id])
    finally:
        job_fetcher.enrich = saved
    rep = json.loads(out)
    assert rc == 0 and rep["enriched"] is False and rep["jd_source"] == "snippet"
    assert rep["jd_chars"] == len(j.description)
    assert "snippet" in rep["RULE"]                      # the deterministic instruction rides along
    # an already-full JD reports "full" via the real enrich() (no fetch, no network)
    j2 = JobPosting(title="AI PM 2", company="C", source="ats:greenhouse",
                    location="Hyderabad, India", url="https://x/jobs/2", description="x" * 5000)
    open(os.path.join(d, "prescreened.jsonl"), "w").write(json.dumps(j2.to_dict()) + "\n")
    rc2, out2 = _run(AT.cmd_enrich, [j2.id])
    rep2 = json.loads(out2)
    assert rc2 == 0 and rep2["jd_source"] == "full" and rep2["enriched"] is False
    print("✓ enrich reports enriched/jd_chars/jd_source — snippet-scored verdicts are flaggable")


def test_topmd_dashboard_pointer_stamped_once():
    d = _isolate()
    v = {"job_id": "dp1", "company": "C", "title": "AI PM", "url": "https://x",
         "fit_score": 4.1, "verdict": "APPLY", "headline": "ok"}
    p = os.path.join(d, "v.json"); json.dump(v, open(p, "w"))
    _run(AT.cmd_tracker, ["--add", p])
    top = open(os.path.join(d, "top.md")).read()
    assert top.count("jobfinder dashboard") == 1          # footer pointer stamped
    v2 = dict(v, job_id="dp2")
    p2 = os.path.join(d, "v2.json"); json.dump(v2, open(p2, "w"))
    _run(AT.cmd_tracker, ["--add", p2])                   # top.md regenerated + re-stamped
    top2 = open(os.path.join(d, "top.md")).read()
    assert top2.count("jobfinder dashboard") == 1         # exactly once — idempotent
    print("✓ top.md footer carries the dashboard pointer exactly once per render")


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
