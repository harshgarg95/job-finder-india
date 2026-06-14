# Rank a batch — honest top-N

Score **many** jobs with [`score-job.md`](score-job.md) + [`_rubric.md`](_rubric.md),
then rank and present the honest top-N.

## Procedure
1. Score every job per `score-job.md` (one JSON object each).
2. Sort by `fit_score` descending; break ties by fewer caps, then more must-haves
   met.
3. Present the top-N as a table the candidate can act on:

   | # | Score | Verdict | Title | Company | One-line honest reason (resume line ↔ JD requirement) |

4. **Honesty guards on the ranking — do not skip these:**
   - If fewer than N jobs are genuine fits, **show fewer**, and say so plainly:
     *"Only K of these clear the bar; the rest are stretches/no's, shown below the
     line."* Never pad the top-N with weak fits to reach N.
   - The top-N is a ranking, not an endorsement. A job at the top of a weak pool
     is still a "DON'T APPLY" if its score says so — label it that way.
   - Show the **score distribution** (how many APPLY / STRETCH / DON'T APPLY) so
     the candidate sees the honest shape of the market for them.
   - For each top-N row, the one-line reason must name the **deciding** evidence:
     which resume line meets the role, or which JD requirement is unmet.

5. Write results to `data/results/` (User Layer): the full per-job JSON to
   `scored.jsonl` and the ranked human-readable table to `top.md`.

## What NOT to do
- Do not turn a DON'T APPLY into an APPLY because the pool is thin.
- Do not invent fits to fill the table.
- Do not coach the candidate on how to apply anyway. This is a filter, not a
  motivational tool.
