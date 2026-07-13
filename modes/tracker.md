# tracker — application status overview

Show the user where everything stands. The tracker is already maintained by the
`tracker` tool; this mode just reads and presents it (no scoring, no model cost).

## Procedure
1. **Gate.** `python -m jobfinder doctor --json` → if `needs_onboarding`, go to `modes/onboarding.md`.
2. **Read** `data/tracker.md` (the single source of truth — every job ever scored:
   score, verdict, quals m/p/x, last-scored, link) and, if present, `data/feedback.md`
   (the user's "applied" / "wouldn't apply" corrections).
3. **Summarize:**
   - counts by verdict (APPLY / STRETCH / DON'T APPLY) and total tracked;
   - the **shortlist** worth acting on (APPLY + STRETCH), highest score first, with links;
   - anything the user already **Applied** to or **passed on** (from feedback), so it isn't re-surfaced;
   - optionally, the most recent run's `data/results/top.md` (fit-first) for the current batch.
4. Offer next steps: *"say 'find me jobs' to score a fresh batch"* or *"mark one applied / wouldn't-apply"*
   (`python -m jobfinder feedback --job <id> --action applied|wouldnt_apply --note "…"`).

## NEVER
- Re-score here, or present a DON'T-APPLY as worth applying. Just report the honest state.
