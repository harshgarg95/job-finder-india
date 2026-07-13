# job-finder — agent instructions

This file tells an AI coding CLI (Claude Code, Gemini, Codex, …) how to operate
job-finder. The product is CLI-agnostic: it holds **no model API key** and runs
scoring through whichever CLI the user already has.

## Before doing ANYTHING else — cold-start check

On the first message of a session, run the deterministic setup check:

```bash
python -m jobfinder doctor --json
```

Parse the JSON. If `needs_onboarding` is true (a required file is missing, or no
AI CLI is detected), **enter onboarding and do NOT run discovery or scoring**
until the basics exist. Required files: `resume.md` (or a `--resume` path),
`config/profile.yml`, `config/sources.yml`, `config/run.yml`. Recommended:
`config/_profile.md`.

## Onboarding — conduct these 5 steps conversationally

Use the never-overwrite writers in `jobfinder/onboard.py` (or guide the user).
Never invent data; ask.

1. **Choose LLM** — show only the CLIs `doctor` detected (plus Ollama if models
   are pulled). No default. Honest labels: local = free/private; a subscription
   CLI uses the user's own login. Never ask for a paid API key.
2. **Login** — explicit step; don't assume they're logged in. For claude: `claude
   login`; if a stray `ANTHROPIC_API_KEY` is set, tell them to unset it (it
   overrides the subscription); for headless scoring, `claude setup-token`. We
   reuse their CLI login — we never handle the credential. Finish with one health
   check (`python -m jobfinder onboard --health-check <cli>`); on 401/credit/quota
   show the exact error and loop back.
3. **Résumé + profile** — paste/upload → `resume.md`; capture name/email,
   location/timezone, target roles, CTC/LPA target + floor + notice, relocate/
   remote → `config/profile.yml`; archetypes/narrative → `config/_profile.md`.
4. **Sources** — ATS scan is on by default (free). Apify = provide an
   `APIFY_TOKEN` in `.env` and enable it in `config/sources.yml`, or skip.
5. **Get-to-know-you** — superpower, what excites/drains, deal-breakers, top
   achievement, portfolio links → `config/_profile.md`.

## Hard rules (do not violate)

- **Volume safety.** Never send the full candidate set to the LLM. `run.py` runs
  `prescreen_set` first, capped at `config/run.yml` → `prescreen.max_llm_jobs`.
  The funnel (raw → candidates → prescreened → scored) is always logged.
- **Credentials.** Never collect, store, print, or transmit the user's keys/
  tokens. `.env` is theirs; tokens go only as the `Authorization` header to the
  channel the user enabled.
- **Discovery ethics.** No stealth, no bot-evasion, no anonymous-proxy scraping.
  Detect-and-skip only. Apify is BYO-token and **auto-pauses** on credits/quota/
  402/repeated-timeout, then continues ATS-only — it never hard-fails the run.
- **No auto-apply.** job-finder recommends; the user applies. Never submit a form.
- **Honest scoring.** The rubric in `prompts/` is the law (6 dimensions, 4.0
  apply line, mandatory resume↔JD citations, holistic + caps, no weighted sum,
  Block-G legitimacy kept separate from the 1–5). Reuse it; don't reinvent it.
- **Data contract.** User-Layer files (`resume.md`, `config/profile.yml`,
  `config/sources.yml`, `config/run.yml`, `config/_profile.md`, `data/*`) are
  never overwritten by an update. System-Layer files (prompts, `jobfinder/**`,
  `*.example.*`) are. See [DATA_CONTRACT.md](DATA_CONTRACT.md).

## Running

```bash
python -m jobfinder doctor                 # setup check
python -m jobfinder onboard                 # guided first-run setup
python -m jobfinder --discover-only         # discover + prescreen (no LLM, free)
python -m jobfinder --resume resume.md --cli claude   # full honest top-N
python -m jobfinder dashboard               # local feedback/tracker UI
```

Outputs: `data/results/top.md` (this run's ranked top-N + funnel + cost),
`data/results/prescreen_report.json` (what the prescreen dropped and why), and
`data/tracker.md` (every job ever scored — the single source of truth).
