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
