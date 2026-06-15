"""Scoring orchestration — build the prompt, drive the user's AI CLI, rank.

This is the product path: it concatenates the rubric + the candidate's resume and
profile + one job, hands it to whichever AI CLI the user has (headless, via
cli_adapter), parses the JSON verdict, and ranks. No scoring key lives here.

Honesty plumbing: per-job failures are recorded and the run continues, but if
*every* job fails to score, that is reported as a breakage — never silently
turned into an empty/garbage ranking.
"""

from __future__ import annotations

import json
import os

import yaml

from . import cli_adapter
from .discovery import job_fetcher
from .resume import load_resume
from .schema import JobPosting

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(resume_text: str, profile: dict, job: JobPosting, lessons: str = "") -> str:
    """Assemble the full scoring prompt for one job. `lessons` is the feedback
    digest (prior user corrections) the scorer must honor — the retune loop."""
    rubric = _read(os.path.join(PROMPTS, "_rubric.md"))
    procedure = _read(os.path.join(PROMPTS, "score-job.md"))
    prof_yaml = yaml.safe_dump({k: v for k, v in profile.items() if not k.startswith("_")},
                               sort_keys=False, allow_unicode=True)
    lessons_block = f"\n---\n{lessons}\n" if lessons else ""
    return f"""{rubric}

---
{procedure}

---
## CANDIDATE RESUME
{resume_text}

---
## CANDIDATE PROFILE (config/profile.yml)
```yaml
{prof_yaml}
```
{lessons_block}
---
## JOB TO SCORE
{job.scoring_view()}

---
Now emit exactly one JSON object scoring THIS job per the schema. Output only the
JSON object.
"""


def _fit_of(v: dict) -> float:
    try:
        return float(v.get("fit_score", 0))
    except (TypeError, ValueError):
        return 0.0


def score_and_rank(resume_path: str, jobs: list[JobPosting], profile: dict, out_dir: str,
                   cli: str | None = None, top_n: int = 10, samples: int = 3) -> int:
    from . import feedback
    resume_text = load_resume(resume_path)
    os.makedirs(out_dir, exist_ok=True)
    scored, failures = [], []

    # Feedback loop: drop jobs the user already rejected, and replay corrections.
    fb = feedback.load()
    suppress = feedback.suppressed_ids(fb)
    lessons = feedback.lessons_digest(fb)
    if suppress:
        before = len(jobs)
        jobs = [j for j in jobs if j.id not in suppress]
        print(f"  feedback: suppressed {before - len(jobs)} job(s) you previously rejected")
    if lessons:
        print(f"  feedback: replaying {len(fb)} prior correction(s) into scoring")

    print(f"\n── Scoring {len(jobs)} jobs via your AI CLI "
          f"({cli or os.environ.get('JOBFINDER_CLI') or 'auto-detect'}) ──")
    enriched = 0
    for i, job in enumerate(jobs, 1):
        # Deep-fetch the full JD if we only have a thin snippet (so the scorer
        # sees buried gating requirements, not a summary).
        if job_fetcher.enrich(job):
            enriched += 1
        prompt = build_prompt(resume_text, profile, job, lessons)
        # Self-consistency: score N times, keep the MOST CONSERVATIVE (lowest)
        # result. Single-pass LLM scores vary; honest scoring errs low (better to
        # skip than to waste an application on a false APPLY).
        outs, last_err = [], None
        def _note_failover(frm, to, why, _seen=set()):
            if (frm, to) not in _seen:
                _seen.add((frm, to))
                print(f"   ⚠ CLI '{frm}' unavailable ({why[:60]}) → failing over to '{to}'")
        for _ in range(max(1, samples)):
            try:
                outs.append(cli_adapter.score(prompt, cli=cli, on_failover=_note_failover))
            except Exception as e:
                last_err = e
        if not outs:
            failures.append({"title": job.title, "company": job.company, "error": str(last_err)})
        else:
            verdict = min(outs, key=_fit_of)            # conservative pick
            fits = [_fit_of(v) for v in outs]
            verdict["score_samples"] = len(outs)
            verdict["score_range"] = [min(fits), max(fits)]
            verdict.setdefault("company", job.company)
            verdict.setdefault("title", job.title)
            verdict["url"] = job.url
            verdict["job_id"] = job.id
            verdict["location"] = job.location
            verdict["link_source"] = job.link_source
            verdict["link_verified"] = job.link_verified
            verdict["source"] = job.source
            scored.append(verdict)
        if i % 10 == 0:
            print(f"   scored {i}/{len(jobs)} (failures so far: {len(failures)})")

    if enriched:
        print(f"   (deep-fetched the full JD for {enriched} thin-snippet listings)")
    if not scored:
        print(f"\n✗ Scoring produced 0 results from {len(jobs)} jobs — BREAKAGE, not an honest empty.")
        for f in failures[:3]:
            print(f"   ⚠ {f['title']}: {f['error']}")
        return 2

    scored.sort(key=lambda v: (-float(v.get("fit_score", 0)), len(v.get("caps_applied", []))))
    _write_outputs(scored, failures, out_dir, top_n)
    return 0


def _write_outputs(scored: list[dict], failures: list[dict], out_dir: str, top_n: int) -> None:
    with open(os.path.join(out_dir, "scored.jsonl"), "w", encoding="utf-8") as f:
        for v in scored:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    dist = {"APPLY": 0, "STRETCH": 0, "DON'T APPLY": 0}
    for v in scored:
        dist[v.get("verdict", "DON'T APPLY")] = dist.get(v.get("verdict", "DON'T APPLY"), 0) + 1
    n_apply, n_stretch, n_no = dist["APPLY"], dist["STRETCH"], dist["DON'T APPLY"]

    lines = ["# Honest top results", ""]
    fail_note = f" · {len(failures)} failed to score" if failures else ""
    lines.append(f"Scored {len(scored)} jobs — "
                 f"{n_apply} APPLY · {n_stretch} STRETCH · {n_no} DON'T APPLY{fail_note}")
    lines.append("")
    lines.append("| # | Score | Verdict | Title | Company | Honest reason |")
    lines.append("|---|------:|---------|-------|---------|---------------|")
    for i, v in enumerate(scored[:top_n], 1):
        reason = (v.get("headline", "") or "").replace("|", "/")
        lines.append(f"| {i} | {float(v.get('fit_score',0)):.1f} | {v.get('verdict','')} "
                     f"| {v.get('title','')[:48]} | {v.get('company','')[:20]} | {reason[:160]} |")
    applies = n_apply + n_stretch
    if applies < top_n:
        lines.append("")
        lines.append(f"> Only {applies} of these clear the bar (APPLY/STRETCH). "
                     "The rest are shown ranked but are honest DON'T APPLYs — not padding.")
    with open(os.path.join(out_dir, "top.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n  distribution: {n_apply} APPLY · {n_stretch} STRETCH · {n_no} DON'T APPLY")
    print(f"  wrote {out_dir}/scored.jsonl and {out_dir}/top.md")
