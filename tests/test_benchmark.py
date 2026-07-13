"""Benchmark harness tests — keyword baseline + the rubric-vs-keyword scorer. No network.

Run:  python -m pytest tests/test_benchmark.py -q   (or: python tests/test_benchmark.py)
"""

import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import benchmark as B


def test_keyword_score_overlap():
    resume = "Delivery manager with RAG, LangChain, LLM evaluation and stakeholder governance."
    jd_hit = "We need RAG and LangChain and LLM evaluation experience for delivery."
    jd_miss = "We need a welder for offshore oil rig maintenance and pipeline inspection."
    assert B.keyword_score(resume, jd_hit) > B.keyword_score(resume, jd_miss)
    assert B.keyword_score(resume, "") == 0.0
    assert 0.0 <= B.keyword_score(resume, jd_hit) <= 1.0
    print("✓ keyword_score: overlap ranks a matching JD above a non-matching one")


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=B.FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in B.FIELDS})


def test_score_labeling_confusion_and_false_buckets():
    d = tempfile.mkdtemp(prefix="jf-bench-")
    p = os.path.join(d, "labeling.csv")
    # verdict, keyword_score, MY_LABEL   → rubric pred (apply=APPLY/STRETCH)
    rows = [
        {"tool_verdict": "APPLY",           "keyword_score": 0.9, "MY_LABEL": "would-apply"},    # TP
        {"tool_verdict": "STRETCH",         "keyword_score": 0.2, "MY_LABEL": "wouldn't-apply"}, # FP (false-APPLY)
        {"tool_verdict": "DON'T APPLY",     "keyword_score": 0.8, "MY_LABEL": "would-apply"},    # FN (false-DONT)
        {"tool_verdict": "DON'T APPLY",     "keyword_score": 0.7, "MY_LABEL": "wouldn't-apply"}, # TN
        {"tool_verdict": "COULDN'T VERIFY", "keyword_score": 0.1, "MY_LABEL": "wouldn't-apply"}, # TN
    ]
    _write_csv(p, rows)
    m = B.score_labeling(p)
    r = m["rubric"]
    assert r["tp"] == 1 and r["fp"] == 1 and r["fn"] == 1 and r["tn"] == 2
    assert r["false_apply"] == 1 and r["false_dont"] == 1       # the two costly errors, named
    assert r["agreement"] == 0.6 and r["precision"] == 0.5 and r["recall"] == 0.5
    assert m["n_would_apply"] == 2 and m["n_wouldnt_apply"] == 3
    # keyword baseline is scored two ways, both present
    assert "keyword_budget_matched" in m and "keyword_best_f1" in m
    assert m["keyword_budget_matched"]["n"] == 5
    print("✓ score_labeling: rubric confusion + false-APPLY/false-DONT + keyword variants")


def test_unlabeled_rows_excluded_and_empty_guard():
    d = tempfile.mkdtemp(prefix="jf-bench-")
    p = os.path.join(d, "labeling.csv")
    _write_csv(p, [{"tool_verdict": "APPLY", "keyword_score": 0.5, "MY_LABEL": ""}])
    assert "error" in B.score_labeling(p)                       # nothing labeled → guarded
    _write_csv(p, [{"tool_verdict": "APPLY", "keyword_score": 0.5, "MY_LABEL": "would-apply"},
                   {"tool_verdict": "DON'T APPLY", "keyword_score": 0.1, "MY_LABEL": ""}])
    assert B.score_labeling(p)["n_labeled"] == 1               # the blank row is skipped
    print("✓ unlabeled rows excluded; empty-guard returns an error")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} benchmark tests passed.")
