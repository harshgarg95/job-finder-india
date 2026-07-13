# evaluate — discover → prescreen → score in-session → fit-first top-N

Goal: an honest, citation-backed top-N for the user's résumé, scored by YOU (the
host model) in this session. No headless model call.

## Procedure
1. **Gate.** `python -m jobfinder doctor --json`. If `needs_onboarding` → go to
   `modes/onboarding.md` and stop.
2. **Load the law.** Read `modes/_shared.md` (→ `prompts/_rubric.md` + `score-job.md`),
   then `resume.md` and `config/profile.yml` (+ `config/_profile.md`). Also run
   `python -m jobfinder preferences --context` and hold that block as a **tie-breaker
   for BORDERLINE (≈3.5–4.2) calls only** — it never overrides the rubric or a hard gate.
3. **Discover.** `python -m jobfinder discover --json`. Report the funnel + channel
   states (Apify auto-pauses on no credits — that's expected; ATS-only is fine).
4. **Prescreen (the cap).** `python -m jobfinder prescreen --json`. This returns the
   bounded job list (≤ `run.yml: max_llm_jobs`). **Score ONLY these. Never more.**
5. **Score each, in-session, in batches of ~8–10:**
   - `python -m jobfinder enrich <job_id>` → use the returned `scoring_view` (the full JD).
   - Apply `prompts/_rubric.md` against `resume.md` + `config/profile.yml`. Cite the
     exact résumé line ↔ exact JD requirement for every dimension. Keep legitimacy
     separate. Default low; re-score borderline (≈3.5–4.2) once, keep the lower.
   - Emit ONE JSON verdict (schema in `score-job.md`, include `job_id`) and persist it.
     **Write the JSON to a temp file, then add the file** — this is robust across every
     CLI; a raw `printf '…' | tracker --add -` pipe breaks on apostrophes (e.g. the one
     in `DON'T APPLY`):
     ```bash
     # write the verdict with your file tool to data/results/_verdict.json, then:
     python -m jobfinder tracker --add data/results/_verdict.json
     ```
     (`tracker --add -` still reads stdin if your JSON has no shell-hostile characters.)
   - Persist each verdict as you go (crash-safe; the tracker upserts by `job_id`).
6. **Present.** Show `data/results/top.md` — it leads with **APPLY / STRETCH** (full
   detail + citations) and collapses DON'T-APPLY into "Filtered out — and why".
7. **Offer next actions** (numbered, per the `_shared.md` convention):
   > What next? Reply with a number:
   >   **1.** Open the full report (`data/results/top.md`)
   >   **2.** Re-run with Apify enabled for more India boards (needs `APIFY_TOKEN`)
   >   **3.** Adjust target roles / filters (`config/profile.yml`) and re-run
   >   **4.** Check whether a posting is still live (`python -m jobfinder live <job_id>`)
   >   **5.** Done `← (default)`
8. **Review & learn (feedback loop).** For each shown job, offer a numbered mark
   (per the `_shared.md` choice convention):
   > Mark this one? Reply with a number:
   >   **1.** Applied   **2.** Interested   **3.** Not suitable   **4.** Skip `← (default)`

   If **3 (Not suitable)**, ask the reason:
   >   **1.** Too senior   **2.** Wrong function   **3.** Location   **4.** Comp   **5.** Company   **6.** Other

   Store each (Skip records nothing) — pass the job's fields so the preference layer can learn:
   ```bash
   python -m jobfinder feedback --job <job_id> --action <action> --company "<c>" --title "<t>" --url "<u>" --note "<optional>"
   ```
   Action map: 1→`applied` · 2→`interested` · 3+reason→`wrong_level`/`wrong_function`/
   `wrong_location`/`wrong_comp`/`wrong_company` · 3+Other→`wouldnt_apply`.
   Then rebuild the preference layer: `python -m jobfinder preferences --refresh`.
   Next run's prescreen drops already-decided jobs and **down-ranks** (never hides)
   repeat-rejected patterns — logged — and the refreshed context tilts borderline
   scores. **The rubric never changes.** Undo a mis-mark:
   `python -m jobfinder feedback --job <id> --undo`; reset all learning:
   `python -m jobfinder preferences --clear`.

## NEVER
- Score, discover, or enrich anything outside `prescreened.jsonl`.
- Invent a citation, or output APPLY without a cited résumé line.
- Shell out to a headless `claude -p` (that's the separate CI path).
- Auto-apply or draft an application. Score and stop.

## Speed option (Claude Code only; build later)
Spawn one subagent per batch to score in parallel, then merge via `tracker`.
**Sequential in-session scoring above is the always-available fallback** on every CLI.
