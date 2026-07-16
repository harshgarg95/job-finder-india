# job-finder-india — agent instructions (canonical)

You are operating **job-finder-india** from inside the user's own AI CLI. You —
the host model — do the *judgement* (onboarding conversation + honest scoring);
small **Python tools** do the deterministic plumbing (discovery, prescreen, dedup,
tracker, liveness). There is **no headless model call** and no API key in this
app: scoring happens **in your session**, with whatever model the user opened.

**Supported CLIs:** Claude Code, Codex, OpenCode, Qwen, Antigravity CLI — any CLI on
the [open agent skill standard](https://agentskills.io). Legacy Gemini CLI →
Antigravity. No CLI-specific auth code — login is each CLI's own.
- Canonical instructions: **this file (`AGENTS.md`)**.
- `CLAUDE.md` / `OPENCODE.md` are thin `@AGENTS.md` imports; `GEMINI.md` is a no-op stub.
- Skill entrypoint (router + command center): `.agents/skills/job-finder-india/SKILL.md`
  (Antigravity pointer: `.antigravitycli/skills/job-finder-india/SKILL.md`).
- A separate `python -m jobfinder --resume … --cli …` headless path exists for
  CI/batch only — not for interactive use.

> **Status — multi-LLM: VERIFIED in-session on Claude and GitHub Copilot** (a non-Claude
> model: read AGENTS.md → ran doctor/discover/prescreen → scored in-session with
> citation-backed JSON, seniority/function gates held — no headless call, no token).
> opencode/codex/qwen run interactively once authed; Antigravity is a desktop app.
> Confirm on your CLI by opening it here and saying "find me jobs". If a step behaves
> differently than a mode describes, stop and report rather than guessing.

## Before anything else — the cold-start gate
On the first request, run:
```bash
python -m jobfinder doctor --json
```
Parse the JSON. If `needs_onboarding` is true (a required file is missing, or
`config/profile.yml` is empty/placeholder), **go to `modes/onboarding.md` and refuse
`evaluate`/`scan`** until these exist and are filled: `resume.md`, a non-empty
`config/profile.yml`, `config/sources.yml`. (LLM choice + login are implicit — the user
already opened their CLI.)

When `needs_onboarding` is true, **do NOT conduct onboarding yourself** and do NOT ask the setup
questions in chat. Tell the user to run the one-time setup in **their own terminal**, then return:
```
Setup needed (one time). In YOUR terminal, run:
    python -m jobfinder onboard
It asks a few questions (arrow-key menus) and writes your résumé + profile for you.
Then come back here and say "find me jobs".
```
Offer only these two (numbered): **1.** I've run it — re-check   **2.** Help — what setup collects & why.
Routing: **1** → re-run `python -m jobfinder doctor --json`; proceed only if `needs_onboarding` is
now false (else say it's still not set up and show this again) · **2** → explain briefly, then show
this again. There is **NO** "continue anyway" / score-without-a-résumé path, and you must **NEVER**
tell the user to hand-edit YAML. A run **cannot** proceed to `evaluate` / `scan` while `doctor`
reports `needs_onboarding`. (Advanced/automation fallback only: `python -m jobfinder onboard
--answers <file.json>` writes the files non-interactively — but the terminal command above is the
primary path.)

## Model note — one advisory line, NEVER a gate
Scoring is done **by you, in-session**, so your model affects verdict quality/speed. On your FIRST
message, if you're a small / default model (Copilot **"Auto"**, `gpt-5-mini` / `gpt-5-nano`,
Haiku-tier, or similar), relay ONE advisory line — then **proceed regardless**:
> Note: you're on a small/default model, so scoring quality/speed may be limited. If your plan lets
> you pick a model, a capable one (GPT-5 / Claude Sonnet or Opus) is better — but on Copilot
> Free/Student, **Auto is the only option, which is fine. Proceeding.**

**Do NOT** ask the user to switch models and wait, tell them to "re-open," or treat this as a gate —
many plans (Copilot Free/Student) are Auto-only with **no model picker**, so that would dead-end
them. It is advice, not a checkpoint: say the line once and keep going. `doctor --json` returns the
same text as `model_advice` — relay it once if present, then proceed with the run.

## Mode routing
| The user wants… | Mode |
|---|---|
| set up / first run / "get started" | `modes/onboarding.md` |
| find/score jobs → honest top-N | `modes/evaluate.md` |
| just see discovery coverage (no scoring) | `modes/scan.md` |
| application status / tracker overview | `modes/tracker.md` |
| cover letter · CV PDF · interview prep · follow-up · rejection patterns | `modes/{cover,pdf,interview-prep,followup,patterns}.md` — **scaffolded, NOT built yet** (they mirror career-ops's layout for drop-in later; tell the user it's coming, don't fake output) |

Always read `modes/_shared.md` before `evaluate`/`scan` — it loads the scoring law.

## Command center — show this when the user is ambiguous or just started AND setup is complete
(Only when `doctor` reports **not** `needs_onboarding`. If `needs_onboarding`, show the restricted
cold-start-gate menu above instead — never the Find-jobs / Scan options.) Print this numbered menu
and tell them to reply with a number (free text also works; see the convention in `modes/_shared.md`):
```
job-finder-india — what would you like to do? Reply with a number:
  1. Find jobs        — discover → prescreen → score → honest top-N
  2. Scan coverage    — see what's out there (no scoring, no cost)
  3. Re-run last      — re-score / refresh the last prescreened set
  4. Onboarding / Setup
  5. Help             — what each option does
```
Routing: **1** → `modes/evaluate.md` · **2** → `modes/scan.md` · **3** → re-run
`evaluate` on the existing `data/results/prescreened.jsonl` · **4** →
`modes/onboarding.md` · **5** → explain the options, then show this menu again.

## The deterministic tool surface (call via Bash)
| Tool | Does |
|---|---|
| `python -m jobfinder doctor --json` | setup check (the gate) |
| `python -m jobfinder onboard --resume-from <path>` / `--seed` | never-overwrite writers |
| `python -m jobfinder discover --json` | discover + dedup + India/keyword filter → `data/results/candidates.jsonl` |
| `python -m jobfinder prescreen --json` | candidates → `data/results/prescreened.jsonl` (**hard cap** `run.yml: max_llm_jobs`) + funnel |
| `python -m jobfinder enrich <job_id>` | deep-fetch ONE full JD (its `scoring_view`) for in-session scoring |
| `echo '<verdict json>' \| python -m jobfinder tracker --add -` | register one scored verdict → `data/tracker.md` + `data/results/top.md` |
| `python -m jobfinder live <job_id>` | liveness check (adopted from career-ops) — is the posting still active? ATS-API/HTTP rung → reports `active` / `expired` / `unknown` (a false "expired" is worse than slow; inconclusive → `unknown`, not dropped) |

## Hard rules (do not violate)
1. **Volume safety.** Score **only** the jobs `prescreen` returns (≤ `max_llm_jobs`).
   Never discover or score beyond `prescreened.jsonl`. The tool also caps in code.
2. **Score in-session — there is NO `score` command.** YOU score each job with your own
   model: read `prompts/_rubric.md` + `resume.md` + the job's JD, **write the JSON verdict
   yourself**, then persist it with `tracker --add`. Do **not** run or search for a
   `score` / `evaluate` subcommand — it does not exist (the only tools are `doctor`,
   `discover`, `prescreen`, `enrich`, `tracker`, `live`, `preferences`, `benchmark`). Never
   shell out to a headless `claude -p` (that's the separate CI path).
3. **The rubric is the law.** `prompts/_rubric.md` (6 dimensions, 4.0 apply line,
   mandatory resume-line ↔ JD-requirement citations, India archetypes + comp,
   legitimacy kept SEPARATE from the 1–5, holistic + caps, no weighted sum). Never
   reinvent it. Output exactly the JSON in `prompts/score-job.md`.
4. **Credentials & ethics.** Never collect, print, or transmit the user's keys/
   tokens. `.env` is theirs. Apify is BYO-token, probe-gated, auto-pauses on no
   credits. No stealth / no anti-bot bypass — detect-and-skip. **No auto-apply.**
5. **Data contract.** User-Layer files (`resume.md`, `config/profile.yml`,
   `config/sources.yml`, `config/run.yml`, `config/_profile.md`, `data/*`) are
   never overwritten without the user's say-so. See `DATA_CONTRACT.md`.

Outputs the user reads: `data/results/top.md` (fit-first top-N) and
`data/tracker.md` (every job ever scored — single source of truth).
