# scan — discovery coverage only (no scoring, no LLM cost)

Use when the user wants to see *what's out there* before committing to scoring —
or to sanity-check channel/credit state. This mode never scores.

## Procedure
1. **Gate.** `python -m jobfinder doctor --json`. If `needs_onboarding` → `modes/onboarding.md`.
2. **Discover.** `python -m jobfinder discover --json`. Report:
   - the funnel `raw → candidates`, and the per-channel report (`ats` on; `apify`
     state — `paused-no-credits` / `no-token` is expected and fine; `google_jobs`).
3. **Prescreen.** `python -m jobfinder prescreen --json`. Report:
   - `input → kept` (the **hard cap** from `run.yml: max_llm_jobs`, and `truncated_from`
     if the cap bit), plus the top drop reasons (`by_reason`).
4. **Present coverage.** Summarize how many India-eligible candidates surfaced and the
   bounded set size, then **offer next actions** (numbered, per the `_shared.md` convention):
   > What next? Reply with a number:
   >   **1.** Score these now → evaluate `← (default)`
   >   **2.** Re-run with Apify enabled for more India boards (needs `APIFY_TOKEN`)
   >   **3.** Adjust target roles / filters (`config/profile.yml`) and re-scan
   >   **4.** Done

## NEVER
- Score, enrich-for-scoring, or call any model here. Discovery + prescreen only.
- Treat a paused/again-no-token Apify as an error — it's the optional channel degrading cleanly.
