# job-finder-india — agent instructions (canonical)

You are operating **job-finder-india** from inside the user's own AI CLI (Claude
Code, Gemini CLI, Codex, OpenCode, …). You — the host model — do the *judgement*
(onboarding conversation + honest scoring); small **Python tools** do the
deterministic plumbing (discovery, prescreen, dedup, tracker). There is **no
headless model call** and no API key in this app: scoring happens **in your
session**, with whatever model the user already opened.

> `CLAUDE.md` / `GEMINI.md` / `OPENCODE.md` are thin wrappers that point here.
> A separate `python -m jobfinder --resume … --cli …` headless path still exists
> for CI/batch only — do **not** use it for interactive work.

## Before anything else — the cold-start gate
On the first request, run:
```bash
python -m jobfinder doctor --json
```
Parse the JSON. If `needs_onboarding` is true (a required file is missing), **go
to `modes/onboarding.md` and refuse `evaluate`/`scan`** until these exist:
`resume.md`, `config/profile.yml`, `config/sources.yml`. (LLM choice + login are
implicit — the user already opened their CLI.)

## Mode routing
| The user wants… | Mode |
|---|---|
| set up / first run / "get started" | `modes/onboarding.md` |
| find/score jobs → honest top-N | `modes/evaluate.md` |
| just see discovery coverage (no scoring) | `modes/scan.md` |

Always read `modes/_shared.md` before `evaluate`/`scan` — it loads the scoring law.

## The deterministic tool surface (call via Bash)
| Tool | Does |
|---|---|
| `python -m jobfinder doctor --json` | setup check (the gate) |
| `python -m jobfinder onboard --resume-from <path>` / `--seed` | never-overwrite writers |
| `python -m jobfinder discover --json` | discover + dedup + India/keyword filter → `data/results/candidates.jsonl` |
| `python -m jobfinder prescreen --json` | candidates → `data/results/prescreened.jsonl` (**hard cap** `run.yml: max_llm_jobs`) + funnel |
| `python -m jobfinder enrich <job_id>` | deep-fetch ONE full JD (its `scoring_view`) for in-session scoring |
| `echo '<verdict json>' \| python -m jobfinder tracker --add -` | register one scored verdict → `data/tracker.md` + `data/results/top.md` |

## Hard rules (do not violate)
1. **Volume safety.** Score **only** the jobs `prescreen` returns (≤ `max_llm_jobs`).
   Never discover or score beyond `prescreened.jsonl`. The tool also caps in code.
2. **Score in-session.** YOU score each job with your own model. Never shell out
   to a headless `claude -p` (that's the separate CI path).
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
