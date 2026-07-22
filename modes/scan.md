# scan — discovery coverage only (no scoring, no LLM cost)

Use when the user wants to see *what's out there* before committing to scoring —
or to sanity-check channel/credit state. This mode never scores.

## Procedure
1. **Gate.** `python -m jobfinder doctor --json`. If `needs_onboarding` → `modes/onboarding.md`.
2. **Discover.** `python -m jobfinder discover --json`.
   - **FIRST check `discovery_status.failed`.** If `true`, discovery BROKE (not empty): relay
     `discovery_status.message` verbatim and **STOP** — do NOT say "0 candidates" or point at
     `data/results/top.md` (it's from an earlier run, not this one). Usual cause: no network access
     (Codex's sandbox blocks network by default — see README). Only continue when it's `false`.
   - If the output carries a **`prefilter_note`** ("all N raw jobs failed the keyword prefilter…"),
     relay it verbatim — that 0 candidates is a profile/keyword mismatch, NOT "no jobs exist";
     point the user at `target_roles` in `config/profile.yml`.
   - the funnel `raw → candidates`, the per-channel `status` (ok/errored/skipped), `candidates_by_source`,
     and `quota_remaining` (remaining monthly free-tier requests per channel).
   - Channel priority: `ats` = always-on floor; `adzuna` = co-primary India-native;
     `jsearch` = supplement, runs only when Adzuna is thin (else `skipped: adzuna
     sufficient` — that's the quota-saving gap-fill, not an error); `google_jobs` /
     `apify` = optional, off by default. A `no-key` / `quota reached` / `paused`
     state on any keyed channel is expected and fine — the floor still runs.
3. **Prescreen.** `python -m jobfinder prescreen --json`. Report:
   - `input → kept` (the **hard cap** from `run.yml: max_llm_jobs`, and `truncated_from`
     if the cap bit), plus the top drop reasons (`by_reason`).
4. **Present coverage.** Summarize how many India-eligible candidates surfaced and the
   bounded set size, then **offer next actions** (numbered, per the `_shared.md` convention):
   > What next? Reply with a number:
   >   **1.** Score these now → evaluate `← (default)`
   >   **2.** Widen sources — add Adzuna/JSearch keys (`.env`), or enable Apify deep-mode
   >   **3.** Adjust target roles / filters (`config/profile.yml`) and re-scan
   >   **4.** Done

## NEVER
- Score, enrich-for-scoring, or call any model here. Discovery + prescreen only.
- Treat a keyed channel's `no-key` / `quota reached` / `paused` / gap-fill `skipped`
  state as an error — it's an optional channel degrading cleanly onto the ATS floor.
