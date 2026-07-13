---
name: job-finder-india
description: Honest India job-fit — evaluate jobs, scan portals, track applications. Runs in your own AI CLI; scores in-session.
arguments: mode
user_invocable: true
user-invocable: true
argument-hint: "[evaluate | scan | tracker | onboarding | cover | pdf | interview-prep | followup | patterns]"
license: MIT
---

# job-finder-india — Router

**Canonical instructions live in [`AGENTS.md`](../../../AGENTS.md). Read it first.**
On the first message of a session run the cold-start gate
(`python -m jobfinder doctor --json`); if `needs_onboarding`, go to onboarding and
refuse everything else until `resume.md` + `config/profile.yml` + `config/sources.yml`
exist. Always read `modes/_shared.md` (the India scoring law) before evaluate/scan.

## Mode routing — from `$mode`
| Input | Mode |
|-------|------|
| (empty / no args) | **command center** — show the menu below |
| "find me jobs" / "score these" / a JD or URL | `modes/evaluate.md` |
| `scan` / "what's out there" / coverage only | `modes/scan.md` |
| `tracker` / "application status" | `modes/tracker.md` |
| not set up yet (doctor gate) | `modes/onboarding.md` |
| `cover` / `pdf` / `interview-prep` / `followup` / `patterns` | scaffolded — **not built yet**; say so, don't fake it |

## Command center (no arguments) — numbered menu, reply with a number
```
job-finder-india — what would you like to do? Reply with a number:
  1. Find jobs        — discover → prescreen → score in-session → fit-first top-N
  2. Scan coverage    — see what's out there (no scoring, no model cost)
  3. Re-run last      — re-score / refresh the last prescreened set
  4. Onboarding/Setup — résumé, profile (incl. work-mode), sources
  5. Help             — what each option does

  (later) cover · pdf · interview-prep · followup · patterns — scaffolded to mirror career-ops
```
Reply with the number (or just tell me — free text works too). Routing: 1 → `modes/evaluate.md`
· 2 → `modes/scan.md` · 3 → re-run evaluate on `data/results/prescreened.jsonl` ·
4 → `modes/onboarding.md` · 5 → explain, then show this menu again.

Safety (always): prescreen hard-caps the set before any scoring; Apify is BYO-token,
probe-gated, auto-pausing; no anti-bot bypass; no auto-apply. Your data stays local.

Tools (Bash): `doctor --json` · `discover --json` · `prescreen --json` · `enrich <job_id>` ·
`tracker --add -` · `live <job_id>`. The rubric in `prompts/_rubric.md` is the law.
