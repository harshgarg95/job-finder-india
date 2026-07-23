# evaluate — discover → prescreen → score in-session → fit-first top-N

Goal: an honest, citation-backed top-N for the user's résumé, scored by YOU (the
host model) in this session. No headless model call.

> **HOW SCORING WORKS — read this before you start.** Scoring is done **BY YOU, the model,
> IN-SESSION.** You read `prompts/_rubric.md` + `resume.md` + the job's JD and **write the JSON
> verdict yourself.** There is **NO `score` (or `evaluate`) CLI subcommand — do not run one, and
> do not search for one; it does not exist.** The ONLY `jobfinder` subcommands are: `doctor`,
> `discover`, `prescreen`, `enrich`, `tracker`, `live`, `preferences`, `benchmark`. If you ever
> catch yourself looking for a way to "run scoring," STOP — **you are the scorer**; producing the
> verdict JSON and saving it with `tracker --add` is the entire act of scoring.

## Procedure
> **Announce each long step BEFORE you run it** (discover / prescreen / score) —
> one line saying what's about to happen and the rough time ("Running discovery…
> ~1–2 min"). The Python tools ALSO stream human progress to stderr as they work
> (`discovery: greenhouse 526 · adzuna 93`, `prescreen: 1063→40`), so a watching
> user can see the run is moving, not stuck — but you still narrate the step and,
> for scoring (which is YOU, not a tool), post "N/total" progress yourself.

1. **Gate.** `python -m jobfinder doctor --json`. If `needs_onboarding` → go to
   `modes/onboarding.md` and stop.
2. **Load the law.** Read `modes/_shared.md` (→ `prompts/_rubric.md` + `score-job.md`),
   then `resume.md` and `config/profile.yml` (+ `config/_profile.md`). Also run
   `python -m jobfinder preferences --context` and hold that block as a **tie-breaker
   for BORDERLINE (≈3.5–4.2) calls only** — it never overrides the rubric or a hard gate.
3. **Discover.** Say "Running discovery across the ATS floor + Adzuna/JSearch… (~1–2 min)"
   first, then `python -m jobfinder discover --json`.
   **FIRST check `discovery_status.failed`.** If it is `true`, discovery BROKE — this is NOT an
   empty result. Relay `discovery_status.message` verbatim and **STOP**: do NOT prescreen, do NOT
   score, do NOT say "0 candidates", and do NOT point the user at `data/results/top.md` (it was NOT
   updated — any file there is from an earlier run, not this one). The usual cause is no network
   access (e.g. Codex's sandbox blocks network by default — see the README). Only when
   `discovery_status.failed` is `false` do you continue.
   If the output carries a **`prefilter_note`** ("all N raw jobs failed the keyword prefilter…"),
   relay it verbatim — that 0 is a profile/keyword mismatch cut at the keyword stage, NOT "no jobs
   exist"; suggest the user check `target_roles` before re-running.
   Then report the funnel, per-channel `status` (ok/errored/skipped), `candidates_by_source`, and
   `quota_remaining` (monthly free-tier left per channel). Adzuna is the co-primary India-native
   channel; JSearch fills in only when Adzuna is thin (a `skipped: adzuna sufficient` is the
   quota-saving gap-fill, not an error); Apify deep-mode is off by default; the ATS floor always
   runs. A single channel `errored` while others returned jobs is a quiet degrade — keep going.
4. **Prescreen (the cap + the full-score cutoff).** Say "Prescreening the candidates down
   to the cap…", then `python -m jobfinder prescreen --json`.
   It returns the bounded, RANKED list (≤ `run.yml: max_llm_jobs`) plus **`score_these`** —
   the top `full_score_top_n` (default 15) **verifiable** jobs by prescreen rank (fit-correlated:
   function + location + seniority, so the top-N are the most likely fits, not arbitrary order).
   **Full-score ONLY the jobs in `score_these`.** It also returns **`couldnt_verify`** (URL-level
   non-job-links — bare domains / careers-landing pages — that can't be scored) and a
   **`backfill_pool`** (the next verifiable jobs). The rest are auto-listed by the tracker under
   "Prescreen-filtered (not individually scored)" — do NOT score them or invent verdicts. (Latency
   win: 15 scored, not 40. FIX 2: couldn't-verify jobs never eat a scoring slot.)

   First, log every job in **`couldnt_verify`** DIRECTLY as an unverifiable entry (no enrich, no
   score — they land in "⚠️ Couldn't verify"): for each, write `{"job_id","title","company","url",
   "unverifiable":true,"reason":"<its reason>"}` and `tracker --add` it.
5. **Score each job in `score_these`, in-session — YOU are the scorer, one job at a time.**
   First tell the user how many you're about to score ("Scoring the top 15 in-session — I'll
   note progress as I go"). Scoring is YOU, not a tool, so **post your own progress** every few
   jobs ("Scoring 3/15…") — a long scoring pass must never look stuck.
   For each `job_id` in `score_these`:
   1. **Enrich:** `python -m jobfinder enrich <job_id>` → read `verifiability.status` and
      `location_gate.status` from its JSON output.
   2. **If either is NOT `"ok"`** — `no_jd` / `non_job_link` (the tool couldn't read the
      posting), or `onsite_elsewhere` / `location_unverified` (location fails your gate):
      **DO NOT score it and do NOT invent a verdict.** Write an unverifiable record (reason =
      the failing check's reason) and add it — it lands in "⚠️ Couldn't verify", never APPLY:
      ```bash
      # data/results/_verdict.json = {"job_id":"<id>","title":"…","company":"…","url":"…",
      #                               "unverifiable":true,"reason":"<the failing check's reason>"}
      python -m jobfinder tracker --add data/results/_verdict.json
      ```
      Then **backfill the slot**: take the next job from `backfill_pool` and score it, so you
      still reach `full_score_top_n` real verdicts (a couldn't-verify job never costs you a slot).
   3. **If both are `"ok"`:** take `scoring_view` (the full JD) from the enrich output. **Check
      `jd_source` first** — if it is `"snippet"`, the full JD could not be fetched (bot-blocked
      host or dead page) and you are scoring incomplete evidence: the rubric's incomplete-JD
      safety net applies **deterministically** — do NOT output APPLY, cap at STRETCH, and say in
      the headline that the full JD was unavailable. (`"full"` scores normally.) **YOU**
      apply `prompts/_rubric.md` against `resume.md` + `config/profile.yml` — cite the exact
      résumé line ↔ exact JD requirement for every dimension, keep legitimacy separate, default
      low, re-score a borderline (≈3.5–4.2) once and keep the lower. **Write the JSON verdict
      yourself** (schema in `prompts/score-job.md`, include `job_id`) to
      `data/results/_verdict.json`, then persist it:
      `python -m jobfinder tracker --add data/results/_verdict.json`.

   Persist each as you go (crash-safe; the tracker upserts by `job_id`). **There is no `score`
   command** — writing the verdict JSON and adding it IS the scoring. (File-based add is robust
   across CLIs; a raw `printf … | tracker --add -` pipe breaks on the apostrophe in `DON'T APPLY`.)

   ### Worked example — one job, end to end (copy this exact pattern)
   ```bash
   python -m jobfinder enrich 5f2a1c9b
   # → {"verifiability":{"status":"ok"}, "location_gate":{"status":"ok"},
   #    "scoring_view":"Title: Technical Program Manager, AI\nCompany: Acme\n… full JD …"}
   ```
   You read that `scoring_view` + `resume.md` + `prompts/_rubric.md`, decide the verdict
   yourself, and write `data/results/_verdict.json`:
   ```json
   {"job_id":"5f2a1c9b","company":"Acme","title":"Technical Program Manager, AI","url":"https://…",
    "fit_score":4.2,"verdict":"APPLY",
    "headline":"APPLY — TPM-AI is your function and you clear the JD's 5-yr program-management minimum",
    "seniority":{"assessment":"match","evidence":"resume '8y programme management' vs JD 'Mid, 5 years program management'"},
    "function":{"assessment":"match","evidence":"resume 'AI delivery / technical program management' vs JD 'Technical Program Manager, AI'"},
    "qualifications":[{"requirement":"5 years program management","status":"met","evidence":"8y across Skootr + Blueprint"}],
    "qualifications_summary":{"met":1,"partial":0,"missing":0},
    "domain":{"assessment":"n/a","note":"delivery role; domain is context"},
    "comp_logistics":{"assessment":"ok","note":"Hyderabad onsite OK; comp not stated"},
    "legitimacy":{"tier":"high","signals":["real employer JD, specific team"]},
    "caps_applied":[],"holistic_before_caps":4.2}
   ```
   Then `python -m jobfinder tracker --add data/results/_verdict.json`. A DON'T-APPLY looks the same
   but with e.g. `"verdict":"DON'T APPLY"`, `"fit_score":1.5`, `"caps_applied":["wrong_function->2.0"]`.

   **Batch to cut round-trips (fewer chances to bail):** you MAY write several verdicts to ONE file —
   JSONL (one JSON object per line) or a JSON array — and add them in a single call (e.g. score 5,
   then `python -m jobfinder tracker --add data/results/_batch.jsonl`). Single-verdict add still works.

   **COMPLETION GATE — you cannot silently skip.** After every `tracker --add`, run
   `python -m jobfinder tracker --status --json` → `{target, scored, remaining, remaining_ids}`.
   **While `remaining > 0` you are NOT done — keep scoring the `remaining_ids`** (each is a `score_these`
   `job_id` with no record yet). You may move to step 6 ONLY when `remaining == 0` (every score_these
   job has a verdict or an unverifiable record). **Do NOT present results or move to feedback while
   `remaining > 0`. Do NOT claim to have scored jobs you have not written verdicts for** — narrating
   "scoring 12/15" while `scored` is 3 is a lie. If you stop anyway, `top.md` carries a
   "⚠️ Scored N of M — incomplete" banner and the dashboard shows it: never present a partial run as complete.
   If `--status` reports **`unreadable: true`** the progress file is corrupt — completeness CANNOT
   be verified: relay its `warning` verbatim, do NOT present the run as complete, and re-run
   `prescreen` to regenerate the progress file before continuing.
6. **Present.** Show `data/results/top.md`. It now has four parts: **✅ APPLY / STRETCH**
   (full detail + citations) · **⚠️ Couldn't verify — check manually** (unreadable / non-job
   links, with reason) · **Filtered out — and why** (DON'T APPLY) · **Prescreen-filtered —
   not individually scored** (rank + reason). The footer prints the wall-clock time. If a
   "raise `full_score_top_n`" risk note appears in top.md, relay it to the user.
7. **Review & learn (feedback loop) — do this IMMEDIATELY after top.md, BEFORE the next-actions
   menu** (so a "Done" can never skip it; this loop is what makes each run better). For each shown
   job, offer a MANDATORY numbered mark (per the `_shared.md` choice convention — the user types
   the number):
   > Mark this one? Reply with the number:
   >   **1.** Applied   **2.** Interested   **3.** Not suitable   **4.** Skip `← (default)`

   If **3 (Not suitable)**, ask the reason as a numbered list — "Reply with the number.":
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

   **Alternative review surface:** instead of (or besides) the inline marks, you may point the user
   to the local dashboard — `python -m jobfinder dashboard` (opens http://127.0.0.1:8755; data never
   leaves their machine) — where they click Applied / Wouldn't-apply(+reason). It writes the SAME
   feedback store and replays the same way next run. Always surface one of the two — never skip the review.
8. **Offer next actions — MANDATORY numbered list (never free text; see `_shared.md`).**
   Present exactly this and end with "Reply with the number." (the user types it in the terminal):
   > What next? Reply with the number:
   >   **1.** Open the full report (`data/results/top.md`)
   >   **2.** {the STATE-AWARE widen option — see below}
   >   **3.** Adjust target roles / filters (`config/profile.yml`) and re-run
   >   **4.** Check whether a posting is still live (`python -m jobfinder live <job_id>`)
   >   **5.** Done `← (default)`

   **Option 2 is state-aware — never offer adding keys that are already set.** You already know
   the state from THIS run: `doctor --json` → `discovery_keys` {adzuna, jsearch, apify}, and the
   `discover` output's per-channel statuses (`no ADZUNA_APP_ID…` reasons), `apify` state, and
   `quota_remaining`. Pick ONE:
   - Adzuna/JSearch keys **missing** →
     "Widen sources — add free Adzuna/JSearch keys (`.env`) for India-native listings"
   - keys **present** →
     "Widen sources — raise `scoring.full_score_top_n`, broaden `target_roles`, or enable Apify deep-mode"
     (drop the Apify clause if `apify` is already `active`; if a keyed channel is
     quota-exhausted this month, say that instead — more keys won't help until it resets)

**Finally, ALWAYS offer the dashboard — after the results, before you finish.** Ask exactly:

> View these in a clickable dashboard (mark Applied/Interested/Not-suitable)? Run:
> `python -m jobfinder dashboard`

If the user says **yes**: `dashboard` is a **blocking server** (runs until Ctrl-C) — **never run it
in the foreground; that hangs your session.** Run it as a **background task** if your CLI supports
backgrounding; otherwise hand the user the command to run in their own terminal (it opens
http://127.0.0.1:8755 in their browser automatically; Ctrl-C stops it). It renders this run the same
honest way (APPLY/STRETCH · Couldn't-verify · Prescreen-filtered, with the funnel + quota) and turns
one-click **Applied / Interested / Not-suitable(+reason)** into the same feedback store prescreen
replays — **deterministic and model-independent**, the reliable review path when the inline marks
above get skipped. (top.md's footer carries the same pointer.)

## NEVER
- **Run or search for a `score` / `evaluate` subcommand — it does not exist.** YOU write the
  verdict JSON; `tracker --add` persists it. That is the whole scoring step.
- Score, discover, or enrich anything outside `prescreened.jsonl` / `score_these`.
- **Re-run `discover` during scoring.** Once discovery + prescreen are done, score ONLY from the
  existing `score_these` / `prescreened.jsonl` — re-discovering mid-flow churns state and wastes quota.
  (Now enforced: `discover` REFUSES while `tracker --status` shows `remaining > 0`; `--force` overrides.)
- **Present results, or narrate progress you haven't written**, while `tracker --status` reports
  `remaining > 0`. Finish the `remaining_ids` first; a partial run is never "complete".
- Invent a citation, or output APPLY without a cited résumé line.
- Shell out to a headless `claude -p` (that's the separate CI path).
- Auto-apply or draft an application. Score and stop.

## Speed option (Claude Code only; build later)
Spawn one subagent per batch to score in parallel, then merge via `tracker`.
**Sequential in-session scoring above is the always-available fallback** on every CLI.
