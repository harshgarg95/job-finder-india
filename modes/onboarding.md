# onboarding — first-run setup (conversational, 3 steps)

Enter this when `python -m jobfinder doctor --json` reports `needs_onboarding: true`.
Refuse `evaluate` / `scan` until `resume.md` + `config/profile.yml` +
`config/sources.yml` exist. **LLM choice + login are implicit** — the user already
opened their own CLI, so do NOT ask which model or for any API key/token.

Be conversational. Never invent data — ask. Never overwrite a user file without
saying so; for a fresh setup, seed templates first:
```bash
python -m jobfinder onboard --seed     # copies any MISSING config/*.example.* into place
```

## Step 1 — Résumé → `resume.md`
Ask for a file path or pasted text.
- Path: `python -m jobfinder onboard --resume-from <path>` (parses pdf/docx/md/txt; refuses to overwrite an existing `resume.md`).
- Pasted: write it to `resume.md` yourself (plain text), only if `resume.md` doesn't already exist.
Confirm it parsed (non-trivial length).

## Step 2 — Profile → `config/profile.yml`
Capture conversationally, then write the `[GATE]` fields the scorer/prescreen rely on:
- name, email, **location + timezone**, base city;
- **target roles / archetypes** (what they want; primary vs stretch);
- seniority truth: years_total, **years_in_function**, honest ceiling;
- **comp (India): target CTC/LPA, floor (walk-away), notice period**;
- **work-mode — ask explicitly: remote / hybrid / on-site?** plus *which city if on-site* and *open to relocating?* Map the answer onto:
  `location.remote_ok`, `location.hybrid_ok`, `location.onsite_cities`, `location.willing_to_relocate`.
  (These drive the prescreen hard-constraint gate and rubric Dimension 5 — e.g. on-site-Hyderabad-only means non-Hyderabad on-site roles are dropped, but India-remote is kept.)
- hard constraints (work-auth, must-not-relocate, no-PhD, etc.).
Edit `config/profile.yml` in place (it was seeded from the example). Show the user the filled values and confirm.

## Step 3 — Sources → `config/sources.yml`
- **ATS scan: on by default** (free, keyless — greenhouse/lever/ashby/workable/workday/smartrecruiters + the curated India list).
- **Apify: optional.** If they have an Apify token, they add `APIFY_TOKEN` to `.env` and set `apify.enabled: true`; it is probe-gated and auto-pauses on no credits. Otherwise skip — coverage is just reduced, never broken.
- Google Jobs: optional (needs a SerpAPI/Serper key); off by default.
- *(Optional)* narrative `config/_profile.md` (superpower, what excites/drains, deal-breakers) for scoring nuance.

## Finish
Run `python -m jobfinder doctor --json` again to confirm `ready: true`, then tell the
user they can say **"find me jobs"** (→ `modes/evaluate.md`) or **"show coverage"**
(→ `modes/scan.md`). Credentials are never collected or printed; `.env` stays theirs.
