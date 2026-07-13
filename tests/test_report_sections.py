"""top.md section tests (FIX A + FIX B) — no network, no model.

Proves the report rendering: a non-job-link verdict is FORCED out of APPLY/STRETCH
into "Couldn't verify"; unverifiable records render there too; prescreen-filtered
jobs are listed with rank + reason (not an LLM verdict); the risk guard fires only
when the weakest full-scored job still clears the STRETCH line; and the wall-clock
footer is written.

Run:  python -m pytest tests/test_report_sections.py -q
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import score


def _tmp():
    return tempfile.mkdtemp(prefix="jf-report-")


def _verdict(job_id, fit, verdict, url):
    return {"job_id": job_id, "title": f"T{job_id}", "company": "Co", "url": url,
            "fit_score": fit, "verdict": verdict, "headline": "why"}


def _pj(job_id, url):
    return {"id": job_id, "title": f"T{job_id}", "company": "Co", "location": "India",
            "url": url, "source": "adzuna", "link_source": "adzuna"}


def _read(d):
    return open(os.path.join(d, "top.md"), encoding="utf-8").read()


def test_couldnt_verify_section_and_apply_exclusion():
    d = _tmp()
    scored = [
        _verdict("a", 4.5, "APPLY", "https://acme.com/jobs/111"),       # real posting → APPLY
        {"job_id": "b", "title": "Tb", "company": "Co", "url": "https://acme.com/careers",
         "unverifiable": True, "reason": "careers landing page"},       # explicit unverifiable
        _verdict("c", 4.6, "APPLY", "https://acme.com"),                # APPLY but bare domain → moved
    ]
    score._write_outputs(scored, [], d, top_n=10)
    top = _read(d)
    apply_part = top.split("Couldn't verify")[0]
    assert "Ta" in apply_part                       # a real APPLY stays in APPLY/STRETCH
    assert "Tc" not in apply_part                   # non-job-link APPLY forced OUT of APPLY
    assert "Couldn't verify" in top
    assert "Tb" in top and "Tc" in top              # both appear in the couldn't-verify section
    assert "4.6 withheld" in top                    # the provisional score is shown as withheld
    print("✓ couldn't-verify section + non-job-link excluded from APPLY (score withheld)")


def test_prescreen_filtered_and_risk_guard():
    d = _tmp()
    scored = [_verdict(x, 3.5, "STRETCH", f"https://acme.com/jobs/{x}0") for x in ("j1", "j2", "j3")]
    prescreened = [_pj(x, f"https://acme.com/jobs/{x}0") for x in ("j1", "j2", "j3", "j4", "j5")]
    score._write_outputs(scored, [], d, top_n=10, prescreened=prescreened, full_score_top_n=3)
    top = _read(d)
    assert "Prescreen-filtered — not individually scored (2)" in top
    assert "Tj4" in top and "Tj5" in top and "rank #4" in top
    assert "not individually scored" in top.lower()
    # weakest full-scored (3.5) still ≥ STRETCH line → the raise-cutoff note fires
    assert "Risk note" in top and "full_score_top_n" in top
    print("✓ prescreen-filtered listing + risk-guard note")


def test_no_risk_note_when_weakest_below_stretch():
    d = _tmp()
    scored = [_verdict("j1", 2.0, "DON'T APPLY", "https://acme.com/jobs/j10")]
    prescreened = [_pj(x, f"https://acme.com/jobs/{x}0") for x in ("j1", "j2")]
    score._write_outputs(scored, [], d, top_n=10, prescreened=prescreened, full_score_top_n=1)
    top = _read(d)
    assert "Prescreen-filtered" in top          # still listed
    assert "Risk note" not in top               # weakest 2.0 < STRETCH line → no note
    print("✓ no risk note when the weakest full-scored job is below the STRETCH line")


def test_wallclock_footer():
    d = _tmp()
    from datetime import datetime, timezone, timedelta
    started = (datetime.now(timezone.utc) - timedelta(seconds=125)).isoformat()
    score._write_outputs([_verdict("a", 4.0, "APPLY", "https://acme.com/jobs/1")], [], d,
                         top_n=10, started_at=started)
    top = _read(d)
    assert "2m 5s" in top                       # 125s → 2m 5s
    print("✓ wall-clock footer")


def test_backcompat_no_new_args():
    # Old call shape (no prescreened / full_score_top_n / started_at) must still work.
    d = _tmp()
    score._write_outputs([_verdict("a", 4.0, "APPLY", "https://acme.com/jobs/1")], [], d, top_n=10)
    top = _read(d)
    assert "APPLY / STRETCH" in top and "Prescreen-filtered" not in top
    print("✓ back-compatible when the new args are omitted")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} report-section tests passed.")
