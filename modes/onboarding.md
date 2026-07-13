# onboarding — first-run setup (YOU actively collect everything)

Enter this mode when `python -m jobfinder doctor --json` reports `needs_onboarding: true`
(a required file is missing). **LLM choice + login are implicit** — the user already
opened their own CLI, so never ask which model or for an API key/token.

**Open with a one-line context note** (fill in your ACTUAL CLI + model) so the user knows
their setup, then begin Step 1:
> You're running in **<detected CLI>** (e.g. Claude Code / GitHub Copilot / Codex) on **<your model>**.
> For best results use a capable model — **not** Copilot "Auto" / `gpt-5-mini`. Let's set you up.

## HARD RULES for this mode (follow these EXACTLY — a weak model especially)
- **YOU do the setup, not the user.** You ask the questions, you CAPTURE the answers,
  and **YOU write the files** (`resume.md`, `config/profile.yml`) with your file-writing
  tool. The user only answers questions.
- **You MUST NOT** tell the user to "create `resume.md`", hand them a template/blank file,
  or point them at a path as the way to give you their résumé. Collecting it is YOUR job.
- **You MUST ask ONE step's question, then STOP and WAIT** for the user's reply before you
  do anything else. Do not assume answers, do not skip a step, do not run discovery yet.
- **You MUST NOT proceed to `evaluate` / `scan`** until **both** `resume.md` **and**
  `config/profile.yml` exist **and** were written from the user's own answers in this
  conversation. Re-run `doctor --json` and confirm `ready: true` before leaving this mode.
- Numbered options for every choice; free-text answers also work (see `modes/_shared.md`).

First, seed the config templates (safe — never overwrites existing files):
`python -m jobfinder onboard --seed`

## Step 1 — Résumé → `resume.md`  (YOU MUST collect it before anything else)
If `resume.md` does not exist, send **this message**, then **STOP and WAIT** for the reply:

> I need your résumé to score jobs against. How would you like to give it to me? Reply with a number:
>   **1.** Paste your résumé text here
>   **2.** Give me a file path (`.pdf` / `.docx` / `.md` / `.txt`)
>   **3.** Paste your LinkedIn profile URL
>   **4.** Just describe your background and I'll draft it

When they reply, **YOU** act on it — do not hand the work back:
- **1 (pasted text)** → write their text to `resume.md` with your file tool. That's it.
- **4 (described)** → draft a clean résumé from what they told you, write it to `resume.md`.
- **2 (file path)** → `python -m jobfinder onboard --resume-from "<their path>"` (parses
  pdf/docx/md/txt → `resume.md`; never overwrites). If it errors, fall back to option **1**.
- **3 (LinkedIn URL)** → we do NOT scrape. Ask them to paste the profile text, then draft
  `resume.md` from it exactly as in option **4**.

Then **verify**: read `resume.md` back, confirm it has real content (roughly 300+ characters),
and tell the user *"Got your résumé — N lines."* If it's empty or too thin, ask again.
**Do NOT move to Step 2 until `resume.md` exists with real content that you wrote.**

## Step 2 — Profile → `config/profile.yml`  (as forceful as Step 1 — YOU ask, YOU write it)
Same HARD RULES as Step 1: **YOU** ask the questions, then **STOP and WAIT** for the reply;
**YOU** write the file; **do NOT hand the user a blank/template to fill in.** Ask for the
fields below in **one message**, then wait. **You MUST explicitly ask for target roles,
LOCATION, and WORK-MODE** — these drive the hard gates, and skipping them is the known bug.
(Show an example for each; the constrained ones are numbered — the user types the number.)
- **Name & email** — free text.
- **LOCATION / base city / timezone** — **required.** Free text (e.g. *"Hyderabad, India · IST"*).
- **Target roles / archetypes** — **required.** Free text (e.g. *"AI Delivery Manager, TPM–AI, AI PM"*).
- **Seniority** — years total · years in the target function · honest ceiling
  (e.g. *"8 total, 2.5 in AI delivery, manager"*).
- **Comp (India)** — target CTC/LPA · floor (walk-away) · notice
  (e.g. *"target 28, floor 20, 60-day notice"*).
- **WORK-MODE** — **required.** Reply with the number:
  >   **1.** Remote   **2.** Hybrid   **3.** On-site   **4.** Open to a mix `← (default)`
  >
  >   If they pick **2** or **3**, you MUST then ask *"Which city/cities for on-site/hybrid?"* and capture it.
- **Open to relocating?** — Reply with the number:
  >   **1.** Yes   **2.** No `← (default)`
- **Hard constraints** (work-auth, no-PhD, must-be-X) — free text.

Map **work-mode + relocate + location** onto `location.remote_ok` / `hybrid_ok` /
`onsite_cities` / `willing_to_relocate` (the fields the prescreen hard-gate and rubric
Dimension 5 consume — an empty or wrong location here silently breaks scoring). Don't invent
values; if they skip an optional field, use a sensible default and tell them which you assumed.

Then **WRITE `config/profile.yml`**, show the user the filled values, and confirm. **You MUST
NOT proceed to Step 3 / `evaluate` until `config/profile.yml` exists, is non-empty, and was
written from the user's answers.** Re-run `python -m jobfinder doctor --json` and confirm
`profile` is no longer under `missing_required`.

## Step 3 — Sources → `config/sources.yml`  (already seeded; just confirm + two optional asks)
The free **ATS scan + Adzuna + JSearch** channels are **ON by default and need no key** — say
so; nothing to do. Then two optional numbered choices (default = skip):
- **Apify deep-mode** (extra India boards — full-JD Naukri) — Reply with a number:
  >   **1.** Add my Apify token (you paste it into `.env`; probe-gated, auto-pauses on no credits)
  >   **2.** Skip — free channels only `← (default)`
- **Narrative profile** `config/_profile.md` (superpower, deal-breakers — sharpens scoring):
  >   **1.** Add a few notes now   **2.** Skip for now `← (default)`

(If they add Adzuna/JSearch keys later, those go in `.env` — you never collect or print them.)

## Finish — confirm ready, then hand off
Run `python -m jobfinder doctor --json` and confirm **`ready: true`** (both `resume.md` and
`config/profile.yml` now exist). **Only then** show the **command center** (the numbered menu in
`AGENTS.md`) and tell the user to reply with a number — or just say **"find me jobs"** to start.
Credentials are never collected or printed; `.env` stays theirs.
