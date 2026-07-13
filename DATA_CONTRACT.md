# Data Contract

job-finder runs entirely on your machine. This document is the promise about
**what is yours and never touched** versus **what is program logic and safe to
update**. It is the operational form of the privacy guarantee: *your data never
leaves your machine, and an update never rewrites your CV.*

> Pattern credit: the two-layer boundary is inspired by career-ops
> (`santifer/career-ops`, MIT). This is a clean reimplementation in our own
> words and file map — see [README](README.md) attribution.

## User Layer — NEVER read by an updater, NEVER auto-modified, NEVER uploaded

Your personal data and work product. The app reads these to do its job, but no
update process may modify or delete them, and nothing here is ever sent over the
network except (a) to the AI CLI **you** chose to run scoring, and (b) the job
text itself to a discovery channel **you** explicitly enabled.

| File / dir | What it is |
|---|---|
| `resume.md` (canonical) / `resume.txt` / `.docx` / `.pdf` (any path you pass) | Your resume. Onboarding writes the canonical `resume.md` from what you paste/upload. Read-only to this app afterward — never edited, never uploaded to us. |
| `config/profile.yml` | Your identity, target roles/archetypes, comp floor (CTC/LPA), location, notice period. The `[GATE]` truth the scorer and prescreen key off. |
| `config/sources.yml` | Which discovery channels you turned on (ATS / Google Jobs / Apify) and their settings. |
| `config/run.yml` | Your run knobs — the `prescreen.max_llm_jobs` volume cap, scoring samples, top-N. |
| `config/_profile.md` | Your narrative profile (archetypes, superpower, deal-breakers) from onboarding Step 5. |
| `config/preferences.yml` | Revealed-preference layer, **derived** from your feedback (rejected/liked patterns). Machine-maintained; rebuild/clear anytime. Never edits the rubric. |
| `data/results/*` | Your scored job results and ranked top-N. |
| `data/tracker.md` | Your single-source-of-truth tracker — every job ever scored, with score, verdict, and citation summary. |
| `data/feedback.md` / `data/feedback.jsonl` | Your scoring corrections ("wouldn't apply", "wrong level/location/domain"). The memory the feedback loop learns from + replays into scoring. Written by the local dashboard or `jobfinder feedback`. |
| `data/.state/*` | Runtime state the app manages for you (e.g. Apify auto-pause status). Not personal data, but yours and machine-local. |
| `data/seen.jsonl` | Jobs already shown to you (so you are not shown the same job twice). |
| `.env` | Your optional discovery keys (SerpAPI / Apify). Secrets. Gitignored — **never read, printed, or transmitted by the app except as the `Authorization` header to the channel you enabled.** |

## System Layer — safe to replace with a newer version on update

Program logic, prompts, templates, docs. These improve over releases and carry
no personal data.

| File / dir | What it is |
|---|---|
| `prompts/*.md` | The scoring rubric and prompts (the CLI-agnostic scoring core). |
| `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `OPENCODE.md`, `modes/*.md`, `.agents/skills/*`, `.antigravitycli/skills/*` | The prompt-pack: canonical agent instructions, per-CLI entry files, modes, and the skill router (the in-CLI scoring flow). |
| `jobfinder/**/*.py` | Discovery + orchestration code, incl. the agent tool subcommands. |
| `config/profile.example.yml` | Template you copy to `config/profile.yml`. |
| `config/sources.example.yml`, `config/run.example.yml`, `config/_profile.example.md`, `config/preferences.example.yml` | Templates / schema references for the user files above. Onboarding seeds the real files from these. |
| `config/ats_tenants.india.yml` | The India ATS tenant list scanned by the free channel. |
| `dashboard/*` | The local tracker UI. |
| `README.md`, `DATA_CONTRACT.md`, `LICENSE`, `docs/*` | Documentation. |
| `requirements.txt`, `.env.example`, `.gitignore` | Project config templates. |

## The Rule

1. **If a file is in the User Layer, no update may read, modify, or delete it.**
2. **If a file is in the System Layer, it may be replaced wholesale with the
   newer upstream version.**
3. **No User-Layer data leaves the machine except through a channel you
   explicitly turned on**, and even then only the minimum needed:
   - Scoring: your resume + a job's text go to the AI CLI *you* selected.
   - Discovery (opt-in): a search query / job URL goes to the channel *you*
     enabled (Google Jobs via your SerpAPI key, or a board via your Apify token).
   - The default discovery channel (public ATS scan) sends only a company slug
     to a public jobs API and needs no key and no personal data at all.

If a future feature would cross this line, it must be off by default, named
explicitly, and consented to per run.
