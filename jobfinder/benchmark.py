"""Scoring benchmark harness — prove "honest scoring" beats a keyword scanner.

Freezes a sample of prescreened jobs, records (a) the tool's in-session rubric
verdict/score and (b) a NAIVE keyword-match baseline (the "% of JD keywords the
résumé contains" model that Jobscan-style scanners use — the thing we claim to
beat), and — once the user hand-labels each job would-apply / wouldn't-apply —
scores BOTH approaches against those labels: agreement, false-APPLY (wasted
applications), false-DON'T (missed opportunities), precision / recall / F1.

Deterministic + offline. The rubric verdicts come from the host model in-session
(no headless call); this module only does the plumbing + the metrics.

CLI:  python -m jobfinder benchmark --score [data/benchmark/labeling.csv]
"""

from __future__ import annotations

import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "benchmark")
SAMPLE = os.path.join(DIR, "sample.jsonl")
LABELING = os.path.join(DIR, "labeling.csv")

APPLY_VERDICTS = {"APPLY", "STRETCH"}          # what the tool counts as "worth applying"
POSITIVE_LABELS = {"would-apply", "would_apply", "apply", "yes", "y", "1", "true"}

_STOP = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this", "that",
    "from", "your", "who", "all", "can", "not", "but", "has", "was", "were", "their",
    "them", "they", "its", "his", "her", "she", "him", "out", "any", "how", "why",
    "into", "over", "such", "than", "then", "when", "where", "what", "which", "while",
    "work", "role", "team", "job", "years", "year", "experience", "including", "using",
    "across", "within", "help", "build", "ability", "strong", "well", "new", "one",
    "make", "more", "most", "other", "also", "per", "via", "etc", "join", "us",
    "company", "opportunity", "candidate", "requirements", "responsibilities", "skills",
    "preferred", "qualifications", "about", "position", "based", "must", "should",
}


def _tokens(text: str) -> set[str]:
    """Significant lowercase word tokens (drop stopwords, short words, bare numbers)."""
    out = set()
    for w in re.findall(r"[a-zA-Z][a-zA-Z+#.]{2,}", (text or "").lower()):
        w = w.strip(".")
        if len(w) >= 3 and w not in _STOP:
            out.add(w)
    return out


def keyword_score(resume_text: str, jd_text: str, title: str = "") -> float:
    """Naive keyword-match baseline (0..1): the fraction of the JD's significant
    tokens that also appear in the résumé — the "% keyword match" a scanner reports.
    Deliberately dumb: no seniority/function/location reasoning, no caps."""
    jd = _tokens((jd_text or "") + " " + (title or ""))
    if not jd:
        return 0.0
    res = _tokens(resume_text)
    return round(len(jd & res) / len(jd), 4)


# ── metrics ──────────────────────────────────────────────────────────────────
def _confusion(preds: list[bool], labels: list[bool]) -> dict:
    tp = sum(p and l for p, l in zip(preds, labels))
    fp = sum(p and not l for p, l in zip(preds, labels))
    tn = sum((not p) and (not l) for p, l in zip(preds, labels))
    fn = sum((not p) and l for p, l in zip(preds, labels))
    n = len(labels) or 1
    return {
        "n": len(labels), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "agreement": round((tp + tn) / n, 3),
        "false_apply": fp,                       # tool said apply, user wouldn't → wasted time
        "false_dont": fn,                        # tool rejected, user would → missed opportunity
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else None,
        "f1": round(2 * tp / (2 * tp + fp + fn), 3) if (2 * tp + fp + fn) else None,
    }


def _label_is_positive(v: str) -> bool | None:
    v = (v or "").strip().lower()
    if not v:
        return None
    if v in POSITIVE_LABELS:
        return True
    return False   # anything else (wouldn't-apply / no / 0 / …) is negative


def score_labeling(path: str = LABELING) -> dict:
    """Read the hand-labeled CSV and compute rubric-vs-keyword metrics. The keyword
    baseline is scored two ways: budget-matched (same #applies as the rubric — a
    fair head-to-head) and best-F1 (the steelman threshold for the baseline)."""
    if not os.path.exists(path):
        return {"error": f"{path} not found — build the benchmark sample first"}
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lab = _label_is_positive(r.get("MY_LABEL", ""))
            if lab is None:
                continue                          # unlabeled → excluded
            rows.append({
                "verdict": (r.get("tool_verdict") or "").strip().upper(),
                "kw": float(r.get("keyword_score") or 0),
                "label": lab,
            })
    if not rows:
        return {"error": "no labeled rows — fill MY_LABEL (would-apply / wouldn't-apply) first"}

    labels = [r["label"] for r in rows]
    n_pos = sum(labels)
    # Rubric: apply = APPLY/STRETCH; COULDN'T VERIFY / DON'T APPLY = not-apply.
    rubric_pred = [r["verdict"] in APPLY_VERDICTS for r in rows]
    n_apply = sum(rubric_pred)

    kws = sorted((r["kw"] for r in rows), reverse=True)
    # Budget-matched keyword: top-`n_apply` by keyword score → apply (same #applies).
    kw_cut = kws[n_apply - 1] if 0 < n_apply <= len(kws) else (max(kws) + 1)
    kw_budget_pred = _top_k_pred([r["kw"] for r in rows], n_apply)
    # Best-F1 keyword: sweep every threshold, keep the max-F1 (steelman for keyword).
    best = None
    for thr in sorted(set(kws)) + [min(kws) - 1e-9]:
        pred = [r["kw"] >= thr for r in rows]
        m = _confusion(pred, labels)
        if best is None or (m["f1"] or -1) > (best[1]["f1"] or -1):
            best = (thr, m)

    return {
        "n_labeled": len(rows), "n_would_apply": n_pos, "n_wouldnt_apply": len(rows) - n_pos,
        "rubric": {"decision": "verdict in {APPLY, STRETCH}", "n_apply": n_apply,
                   **_confusion(rubric_pred, labels)},
        "keyword_budget_matched": {"decision": f"top-{n_apply} by keyword score (same apply-budget)",
                                   "threshold": round(kw_cut, 4), **_confusion(kw_budget_pred, labels)},
        "keyword_best_f1": {"decision": f"keyword_score >= {round(best[0], 4)} (best-F1 steelman)",
                            "threshold": round(best[0], 4), **best[1]},
    }


def _top_k_pred(scores: list[float], k: int) -> list[bool]:
    if k <= 0:
        return [False] * len(scores)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    keep = set(order[:k])
    return [i in keep for i in range(len(scores))]


# ── labeling.csv writer ──────────────────────────────────────────────────────
FIELDS = ["job_id", "job", "company", "source", "link",
          "tool_verdict", "tool_score", "keyword_score", "MY_LABEL"]


def write_labeling(rows: list[dict], path: str = LABELING) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def format_report(m: dict) -> str:
    """Human-readable side-by-side of the three decision rules."""
    if m.get("error"):
        return m["error"]
    L = [f"Benchmark — {m['n_labeled']} labeled ({m['n_would_apply']} would-apply · "
         f"{m['n_wouldnt_apply']} wouldn't)", ""]
    L.append(f"{'approach':32} {'agree':>6} {'false-APPLY':>12} {'false-DONT':>11} "
             f"{'prec':>6} {'recall':>7} {'f1':>6}")
    L.append("-" * 84)
    for key, name in (("rubric", "Rubric (honest tool)"),
                      ("keyword_budget_matched", "Keyword (same apply-budget)"),
                      ("keyword_best_f1", "Keyword (best-F1 steelman)")):
        b = m[key]
        L.append(f"{name:32} {b['agreement']*100:5.0f}% {b['false_apply']:>12} "
                 f"{b['false_dont']:>11} {str(b['precision']):>6} {str(b['recall']):>7} "
                 f"{str(b['f1']):>6}")
    L += ["", f"  rubric decision:  {m['rubric']['decision']}",
          f"  false-APPLY = tool said apply, you wouldn't (wasted application)",
          f"  false-DONT  = tool rejected, you would (missed opportunity)"]
    return "\n".join(L)
