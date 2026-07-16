"""Local results dashboard tests — no network, no model, no browser.

Proves: _load_run() splits a run into APPLY/STRETCH · Couldn't-verify · Prescreen-
filtered (rank + reason) + funnel; a marked action persists via feedback.record and
appears in preferences (the store prescreen replays); the stdlib server answers
/api/data (JSON) and / (HTML) on 127.0.0.1.

Run:  python -m pytest tests/test_dashboard.py -q   (or: python tests/test_dashboard.py)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import dashboard as D
from jobfinder import feedback as FB
from jobfinder import preferences as PF
from jobfinder.schema import JobPosting


def test_load_run_splits_sections():
    d = tempfile.mkdtemp(prefix="jf-dash-")
    D.RESULTS_DIR = d
    jobs = [JobPosting(title=t, company="C", source="ats:greenhouse", location="Hyderabad, India",
                       url=f"https://x/jobs/{i}") for i, t in enumerate(["A PM", "B PM", "C PM", "D PM"])]
    idA, idB, idC, idD = [j.id for j in jobs]
    scored = [
        {"job_id": idA, "title": "A PM", "company": "C", "url": jobs[0].url, "fit_score": 4.3,
         "verdict": "APPLY", "headline": "APPLY — good"},
        {"job_id": idB, "title": "B PM", "company": "C", "url": jobs[1].url, "fit_score": 1.5,
         "verdict": "DON'T APPLY", "headline": "DON'T APPLY — no"},
        {"job_id": idC, "title": "C PM", "company": "C", "url": jobs[2].url,
         "unverifiable": True, "reason": "JD too thin"},
    ]
    with open(os.path.join(d, "scored.jsonl"), "w", encoding="utf-8") as f:
        for r in scored:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(d, "prescreened.jsonl"), "w", encoding="utf-8") as f:
        for j in jobs:                                          # fit-ranked order A,B,C,D
            f.write(json.dumps(j.to_dict()) + "\n")
    json.dump({"input": 50, "kept": 4, "truncated_from": None},
              open(os.path.join(d, "prescreen_report.json"), "w", encoding="utf-8"))

    run = D._load_run()
    assert [v["job_id"] for v in run["jobs"]] == [idA, idB]     # verdicts only, sorted desc by fit
    assert run["jobs"][0]["fit_score"] == 4.3
    assert len(run["couldnt_verify"]) == 1 and run["couldnt_verify"][0]["reason"] == "JD too thin"
    # prescreen_filtered = prescreened NOT in scored (A,B,C are scored) → only D, at its rank
    assert len(run["prescreen_filtered"]) == 1
    pf = run["prescreen_filtered"][0]
    assert pf["rank"] == 4 and "not scored" in pf["reason"]
    assert run["funnel"] == {"candidates": 50, "prescreened": 4, "scored": 2, "truncated_from": None}
    print("✓ _load_run splits APPLY/STRETCH · couldnt-verify · prescreen-filtered + funnel")


def test_dashboard_feedback_persists_and_appears_in_preferences():
    d = tempfile.mkdtemp(prefix="jf-dash-fb-")
    FB.DATA = d
    FB.FB_JSONL = os.path.join(d, "feedback.jsonl")
    FB.FB_MD = os.path.join(d, "feedback.md")
    PF.CONFIG = d
    PF.DATA = d
    PF.PREFS_PATH = os.path.join(d, "preferences.yml")
    PF.TRACKER_JSONL = os.path.join(d, "tracker.jsonl")
    # exactly what the dashboard's POST /api/feedback calls:
    FB.record("applied-1", "Acme", "AI Delivery Manager", "https://x/jobs/1", "applied")
    FB.record("ns-1", "Beta", "Data Scientist", "https://x/jobs/2", "wrong_function")
    ids = {e["job_id"] for e in FB.load()}
    assert {"applied-1", "ns-1"} <= ids                        # persisted through feedback.record
    prefs = PF.refresh()                                       # derive the layer prescreen loads
    assert "applied-1" in PF.seen_ids(prefs)                   # applied → seen → not re-surfaced next run
    print("✓ dashboard feedback.record() persists + appears in preferences (prescreen replay path)")


def test_dashboard_serves_http():
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    D.RESULTS_DIR = tempfile.mkdtemp(prefix="jf-dash-http-")   # empty run → valid empty JSON
    srv = ThreadingHTTPServer(("127.0.0.1", 0), D.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/data", timeout=5).read())
        assert {"jobs", "couldnt_verify", "prescreen_filtered", "funnel", "quota"} <= set(data)
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode("utf-8")
        assert "Job Finder India" in html and "find me jobs" in html   # renders + no-results guidance
    finally:
        srv.shutdown()
        srv.server_close()
    print("✓ dashboard serves /api/data (JSON) + / (HTML) on 127.0.0.1, then shuts down")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} dashboard tests passed.")
