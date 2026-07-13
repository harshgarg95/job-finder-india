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
    assert "Score ONLY" in data["RULE"]
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


def test_tracker_tool_rejects_bad_verdict():
    d = _isolate()
    p = os.path.join(d, "bad.json"); json.dump({"title": "no id, no score"}, open(p, "w"))
    rc, out = _run(AT.cmd_tracker, ["--add", p])
    assert rc == 1 and "fit_score" in json.loads(out)["error"]


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
