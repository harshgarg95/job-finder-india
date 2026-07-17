"""Deterministic cap enforcement — the rubric's law `final = min(holistic, caps)`, in code.

The model sometimes records caps_applied but doesn't apply them, promoting a DON'T
APPLY into STRETCH. normalize_record catches that slip: it corrects fit_score to the
smallest cap, re-derives the verdict band, and annotates it visibly. It NEVER modifies
prompts/_rubric.md — it enforces the law the rubric already states.

Run:  python -m pytest tests/test_cap_enforcement.py -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder.schema import normalize_record


def test_cap_violation_corrected_and_verdict_rederived():
    r = normalize_record({"job_id": "gl", "verdict": "STRETCH", "fit_score": 3.5,
                          "headline": "STRETCH — remote-Bangalore PgM",
                          "caps_applied": ["seniority_ceiling_under->2.0", "missing_named_methodology->2.5"]})
    assert r["fit_score"] == 2.0 and r["verdict"] == "DON'T APPLY"       # min cap; band re-derived
    assert r["cap_enforced"] == {"from": 3.5, "to": 2.0, "by": "seniority_ceiling_under"}
    assert r["headline"].startswith("⚖️ Cap enforced: 3.5 → 2.0 (seniority_ceiling_under).")
    print("✓ cap violation → fit corrected to min cap, verdict re-derived, annotated (not silent)")


def test_compliant_verdicts_untouched():
    a = normalize_record({"job_id": "a", "verdict": "DON'T APPLY", "fit_score": 2.0, "headline": "DONT — x",
                          "caps_applied": ["seniority_ceiling_under->2.0"]})     # fit already at the cap
    assert a["fit_score"] == 2.0 and a["verdict"] == "DON'T APPLY" and "cap_enforced" not in a
    b = normalize_record({"job_id": "b", "verdict": "APPLY", "fit_score": 4.2, "headline": "APPLY — y"})
    assert b["fit_score"] == 4.2 and b["verdict"] == "APPLY" and "cap_enforced" not in b   # no caps
    assert b["headline"] == "APPLY — y"                                 # unchanged
    print("✓ compliant verdicts (fit ≤ cap, or no caps) are untouched")


def test_malformed_cap_string_flagged_not_applied():
    m = normalize_record({"job_id": "m", "verdict": "STRETCH", "fit_score": 3.5, "headline": "STRETCH — z",
                          "caps_applied": ["wrong_function"]})           # no '-><number>'
    assert m["fit_score"] == 3.5 and "cap_enforced" not in m            # never guess — score left alone
    assert m["cap_parse_warning"] == ["wrong_function"]                 # flagged
    print("✓ malformed cap string → flagged (cap_parse_warning), score left alone")


def test_cap_enforcement_is_idempotent():
    r = normalize_record({"job_id": "i", "verdict": "STRETCH", "fit_score": 3.5, "headline": "STRETCH — x",
                          "caps_applied": ["a->2.0"]})
    r2 = normalize_record(r)                                            # re-normalize the corrected record
    assert r2["fit_score"] == 2.0 and r2["headline"] == r["headline"]   # no double-correct / double-prepend
    print("✓ cap enforcement is idempotent")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} cap-enforcement tests passed.")
