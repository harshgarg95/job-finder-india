# evaluate — discover → prescreen → score in-session → fit-first top-N

Goal: an honest, citation-backed top-N for the user's résumé, scored by YOU (the
host model) in this session. No headless model call.

## Procedure
1. **Gate.** `python -m jobfinder doctor --json`. If `needs_onboarding` → go to
   `modes/onboarding.md` and stop.
2. **Load the law.** Read `modes/_shared.md` (→ `prompts/_rubric.md` + `score-job.md`),
   then `resume.md` and `config/profile.yml` (+ `config/_profile.md`).
3. **Discover.** `python -m jobfinder discover --json`. Report the funnel + channel
   states (Apify auto-pauses on no credits — that's expected; ATS-only is fine).
4. **Prescreen (the cap).** `python -m jobfinder prescreen --json`. This returns the
   bounded job list (≤ `run.yml: max_llm_jobs`). **Score ONLY these. Never more.**
5. **Score each, in-session, in batches of ~8–10:**
   - `python -m jobfinder enrich <job_id>` → use the returned `scoring_view` (the full JD).
   - Apply `prompts/_rubric.md` against `resume.md` + `config/profile.yml`. Cite the
     exact résumé line ↔ exact JD requirement for every dimension. Keep legitimacy
     separate. Default low; re-score borderline (≈3.5–4.2) once, keep the lower.
   - Emit ONE JSON verdict (schema in `score-job.md`, include `job_id`) and persist it:
     ```bash
     printf '%s' '<verdict json>' | python -m jobfinder tracker --add -
     ```
   - Persist each verdict as you go (crash-safe; the tracker upserts by `job_id`).
6. **Present.** Show `data/results/top.md` — it leads with **APPLY / STRETCH** (full
   detail + citations) and collapses DON'T-APPLY into "Filtered out — and why".

## NEVER
- Score, discover, or enrich anything outside `prescreened.jsonl`.
- Invent a citation, or output APPLY without a cited résumé line.
- Shell out to a headless `claude -p` (that's the separate CI path).
- Auto-apply or draft an application. Score and stop.

## Speed option (Claude Code only; build later)
Spawn one subagent per batch to score in parallel, then merge via `tracker`.
**Sequential in-session scoring above is the always-available fallback** on every CLI.
