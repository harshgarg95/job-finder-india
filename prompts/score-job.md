# Score one job — honest verdict

Apply the rules in [`_rubric.md`](_rubric.md) to score **one** job against the
candidate. Read the rubric first; it is the law. This file defines the procedure
and the exact output shape.

## Procedure
1. Read the candidate **resume** and **profile** (`config/profile.yml` — the
   `[GATE]` fields are ground truth about the candidate; if absent, infer
   honestly from the resume and say so).
2. Read the **job** (the normalized block below / provided as input).
3. Work the six dimensions in `_rubric.md`. For each, find the **exact resume
   line** and the **exact JD requirement** it turns on.
4. Form a holistic 0–5 score, then apply **every** triggered cap (caps only push
   the score down). Final score = min(holistic, all caps).
5. Emit **exactly one JSON object**, nothing else before or after it. No prose,
   no markdown fences around it — just the object, so a script can parse stdout.

## Output schema (emit exactly this shape)
```json
{
  "company": "string",
  "title": "string",
  "url": "string",
  "fit_score": 0.0,
  "verdict": "APPLY | STRETCH | DON'T APPLY",
  "headline": "one honest sentence: the single reason this is/ isn't a fit, naming the deciding resume line and JD requirement",
  "seniority": {
    "jd_level": "intern|junior|mid|senior|lead/staff|manager|director+ (+years if stated)",
    "candidate_ceiling": "from profile or inferred",
    "assessment": "match|under|over",
    "evidence": "exact resume line + exact JD line",
    "note": "string"
  },
  "function": {
    "jd_function": "what the role does all day",
    "candidate_function": "what the candidate actually does",
    "assessment": "match|adjacent|wrong",
    "evidence": "exact resume line + exact JD line",
    "note": "string"
  },
  "qualifications": [
    {"requirement": "exact JD requirement", "status": "met | partial | missing", "evidence": "exact resume line (met), what falls short (partial), or 'none' (missing)"}
  ],
  "qualifications_summary": {"met": 0, "partial": 0, "missing": 0},
  "domain": {"assessment": "match|adjacent|wrong|n/a", "note": "string"},
  "comp_logistics": {"assessment": "ok|concern|hard_break|not_stated", "note": "CTC/LPA, location, notice as relevant"},
  "legitimacy": {"tier": "high|medium|low", "signals": ["string"]},
  "caps_applied": ["wrong_function->2.0", "location_constraint->1.5"],
  "holistic_before_caps": 0.0
}
```

## Reminders that catch the optimistic-scorer failure mode
- If `function.assessment` is `wrong`, `fit_score` MUST be ≤ 2.0 — no matter how
  strong the skills overlap looks.
- If `seniority.assessment` is `under` by a clear level/years, `fit_score` MUST
  be ≤ 2.0.
- A **missing** hard requirement (work authorization, required degree, mandatory
  named-tech years, on-site city the candidate won't move to) MUST cap at ≤ 1.5.
- **Score the requirements, not the title.** Build the `qualifications` breakdown
  (met / partial / missing + evidence) over every quantified/named requirement
  ("3 yrs SAFe", "8 yrs software engineering", "1 yr software development", "CS
  degree") and gate on the **missing** hard ones — a matching title is not a
  matching candidate.
- **Incomplete-JD safety net:** if the job text is short or clearly a truncated
  snippet (no requirements/qualifications section, well under a real posting), you
  CANNOT confirm the must-haves — do **NOT** output APPLY. Cap at **STRETCH** and
  say in the headline that the full JD was unavailable and the requirements need
  direct verification.
- `headline` must read like an honest human verdict, e.g. *"DON'T APPLY — this is
  a hands-on ML engineering role (JD: 'build and train production models, 5+ yrs
  PyTorch'); the candidate is an AI delivery/PM lead (resume: 'scoped and managed
  AI delivery'), not a modelling engineer."*
- Do not produce a cover-letter, a "how to position yourself," or any
  application coaching. Score and stop.
