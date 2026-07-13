# _shared — the scoring law (load before evaluate / scan)

Read these two files in full; they are the engine and they do not change:
- **`prompts/_rubric.md`** — the honest-fit rubric (THE law).
- **`prompts/score-job.md`** — the exact JSON object you must emit per job.

## Presenting choices (UX convention — MANDATORY at EVERY decision point)
Whenever you ask the user to decide **anything** — an onboarding step, the "what next?"
after results, a feedback mark, the command-center menu — you **MUST** present the options
as a **numbered list** (one option per line), mark the default `← (default)`, and end with
the exact line **"Reply with the number."** Do **not** phrase the options as a sentence or
free-running text; a plain numbered list is required so a weaker model's flow stays
unambiguous. This includes the **post-results next-actions** menu — it is a numbered list,
never prose.

The user is in a **terminal**: they **type the number and press enter** — there are **no
clickable buttons or widgets**, and that is expected. Print plain text only (portable across
Claude / Codex / OpenCode / Qwen / Antigravity). Free-text answers still work, but you must
always OFFER the numbered list first.

## The candidate (read once per session)
- `resume.md` — the résumé (full text).
- `config/profile.yml` — `[GATE]` truth: seniority ceiling + years-in-function,
  function in/out-of-scope, target roles/**archetypes**, comp floor (CTC/LPA) +
  notice, location + **work-mode** (remote/hybrid/on-site) + hard constraints.
- `config/_profile.md` — narrative (superpower, deal-breakers) for nuance.

## The rules that must survive (do not drift from `_rubric.md`)
- **0–5 scale, used fully**, bottom-heavy. **4.0 is the apply / don't-apply line.**
- **6 dimensions:** 1 Seniority `[GATE]`, 2 Function `[GATE]`, 3 Core-requirements
  `[HARD GATE]`, 4 Domain, 5 Comp & logistics (India: CTC/LPA, notice, on-site city)
  `[GATE]`, 6 **Legitimacy — a SEPARATE qualitative read that does NOT move the 0–5.**
- **No weighted sum.** Form a holistic view, then apply caps (caps only push down).
- **Every dimension cites the exact résumé line AND the exact JD requirement.**
  No citation → not done. A 4.0+ must be earned by cited evidence, never reframing.
- **Default to the lower band when unsure.** Honesty over encouragement.
- Incomplete/short JD → cannot confirm must-haves → cap at STRETCH and say so.

## Emit exactly (per `prompts/score-job.md`), one object per job, plus `job_id`
```json
{ "job_id": "<from prescreened.jsonl>", "company": "...", "title": "...", "url": "...",
  "fit_score": 0.0, "verdict": "APPLY | STRETCH | DON'T APPLY",
  "headline": "one honest sentence naming the deciding résumé line ↔ JD requirement",
  "seniority": {...}, "function": {...}, "qualifications": [...],
  "qualifications_summary": {"met":0,"partial":0,"missing":0},
  "domain": {...}, "comp_logistics": {...}, "legitimacy": {"tier":"...","signals":[...]},
  "caps_applied": [...], "holistic_before_caps": 0.0 }
```
Conservative pass: default low; if a job lands borderline (≈3.5–4.2), reason once
more and keep the **lower** result.
