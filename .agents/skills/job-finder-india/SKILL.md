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

## Command center (no arguments)
```
job-finder-india — honest India job-fit (runs in your CLI, scores in-session)

  find me jobs        → evaluate: discover → prescreen (cap) → score in-session → fit-first top-N
  scan                → discovery coverage only, no scoring (no model cost)
  tracker             → application status overview (data/tracker.md)
  set me up           → first-run onboarding (résumé, profile incl. work-mode, sources)

  (later) cover · pdf · interview-prep · followup · patterns — scaffolded to mirror career-ops

Safety: prescreen hard-caps the set before any scoring; Apify is BYO-token, probe-gated,
auto-pausing; no anti-bot bypass; no auto-apply. Your data stays local.
```

Tools (Bash): `doctor --json` · `discover --json` · `prescreen --json` · `enrich <job_id>` ·
`tracker --add -` · `live <job_id>`. The rubric in `prompts/_rubric.md` is the law.
