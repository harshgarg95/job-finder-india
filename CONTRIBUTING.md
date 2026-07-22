# Contributing to Job Finder India

Thanks for considering a contribution. This project has an unusual shape — read the
architecture note first so your change lands in the right layer.

## The architecture in one paragraph (prompt-pack + tools)

This is **not** a classic Python app with an LLM API call inside. The AI CLI the user
already runs (Claude Code, Codex, Copilot, …) reads **[`AGENTS.md`](AGENTS.md)** (the
canonical instructions) and the **[`modes/`](modes/)** playbooks, does the *judgement*
(onboarding conversation, honest scoring) **in-session with its own model**, and calls
small deterministic Python tools (`doctor`, `discover`, `prescreen`, `enrich`,
`tracker`, `live`, `dashboard`) for the plumbing. There is no scoring API key and no
`score` command. Consequences for contributors:

- Behavior lives in **two places**: Python (`jobfinder/`) for anything deterministic,
  and markdown (`AGENTS.md`, `modes/*.md`) for anything the agent does. A fix is not
  done until the right one of the two carries it — prompt rules alone get skipped by
  weak models, so anything that MUST hold is enforced in Python.
- **`prompts/_rubric.md` and `prompts/score-job.md` are the scoring law** and
  `jobfinder/score.py` is the frozen headless renderer. Don't change them in a PR
  without opening an issue first — verdict semantics are the product.
- User files (`resume.md`, `config/profile.yml`, `.env`, `data/*`) are gitignored and
  never committed — see [`DATA_CONTRACT.md`](DATA_CONTRACT.md).

## Setup

```bash
git clone https://github.com/harshgarg95/job-finder-india
cd job-finder-india
pip install -r requirements.txt pytest
```

CI runs Python 3.13; anything ≥ 3.11 should work locally.

## Running tests

```bash
python -m pytest tests/ -q
```

The suite is offline — no network, no API keys, no model calls (providers are
stubbed). It runs in about a second; run it before every push. Two live checks exist
separately: CI runs the suite on every push/PR, and a daily `discovery-smoke`
workflow hits the real free APIs (you don't need keys to contribute — the ATS
channel and the whole test suite are keyless).

## Submitting a PR

1. Fork, branch from `main`, make the change.
2. `python -m pytest tests/ -q` — green, including new tests for new behavior.
   Fixes for silently-wrong behavior should come with a test that fails without
   the fix; that's the house style.
3. Behavior changes to discovery/prescreen/ranking need **before/after evidence**
   in the PR description (this repo's history shows the pattern).
4. Push and open a PR against `main`. The `tests` check is required and history is
   linear (PRs are squash- or rebase-merged).
5. Keep PRs focused — one concern per PR.

Ground rules (from [`AGENTS.md`](AGENTS.md), non-negotiable):

- **No auto-apply.** The tool recommends; the human applies.
- **No stealth scraping / anti-bot bypass.** Blocked sites are detected and skipped.
- **No credential handling.** Keys stay in the user's `.env`; never log or persist them.
- **Honesty over optimism.** A degraded state (network failure, partial scoring,
  unreadable file) must surface loudly — never render as a normal/empty result.
- No personal data in code, tests, fixtures, or docs.

## Reporting issues

Use the issue templates. **Security vulnerabilities go to
[SECURITY.md](SECURITY.md)** (private reporting), not public issues. Never paste
your `.env` keys or résumé content into an issue.
