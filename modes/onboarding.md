# onboarding — first-run setup (conversational, numbered options)

Enter this when `python -m jobfinder doctor --json` reports `needs_onboarding: true`.
Refuse `evaluate` / `scan` until `resume.md` + `config/profile.yml` +
`config/sources.yml` exist. **LLM choice + login are implicit** — the user already
opened their own CLI, so never ask which model or for an API key/token.

Follow the **choice convention** in `modes/_shared.md`: every decision is a
**numbered list**, the default is marked `← (default)`, and you end with *"Reply
with the number (or just tell me)."* Free-text answers always work too. Seed any
missing config first: `python -m jobfinder onboard --seed`.

## Step 1 — Résumé → `resume.md`
Ask, verbatim shape:
> How would you like to give me your résumé? Reply with a number:
>   **1.** Paste the résumé text here
>   **2.** Give me a file path (`.pdf` / `.docx` / `.md` / `.txt`)
>   **3.** Paste your LinkedIn profile URL
>   **4.** Just describe your experience and I'll draft it

- **1 / 4** → write `resume.md` yourself from what they paste/say (only if it doesn't exist).
- **2** → `python -m jobfinder onboard --resume-from <path>` (parses pdf/docx/md/txt; never overwrites).
- **3** → ask them to paste the profile text (we don't scrape); draft `resume.md` from it.
Confirm it parsed (non-trivial length).

## Step 2 — Profile → `config/profile.yml`
Free-text fields (show an example), numbered lists for the constrained ones:
- **Name & email** — free text.
- **Location, base city, timezone** — free text (e.g. *"Hyderabad, India · IST"*).
- **Target roles / archetypes** — free text (e.g. *"AI Delivery Manager, TPM–AI, AI PM"*).
- **Seniority** — years total, years in the target function, honest ceiling — free text.
- **Comp (India)** — target CTC/LPA, floor (walk-away), notice — free text (e.g. *"target 28, floor 20, 60-day notice"*).
- **Work-mode** — Reply with a number:
  >   **1.** Remote   **2.** Hybrid   **3.** On-site   **4.** Open to a mix `← (default)`

  If **2** or **3**: ask *"Which city/cities for on-site/hybrid?"* (free text).
- **Open to relocating?** — Reply with a number:
  >   **1.** Yes   **2.** No `← (default)`
- **Hard constraints** (work-auth, no-PhD, must-be-X) — free text.

Map **work-mode + relocate** onto `location.remote_ok` / `hybrid_ok` /
`onsite_cities` / `willing_to_relocate` (the fields the prescreen hard-gate and
rubric Dimension 5 consume). Write `config/profile.yml`, show the filled values, confirm.

## Step 3 — Sources → `config/sources.yml`
- **ATS scan** is ON by default (free, keyless) — no action needed; just say so.
- **Apify** (optional India boards — Naukri/LinkedIn/Indeed) — Reply with a number:
  >   **1.** Add my Apify token (you paste it into `.env`; probe-gated, auto-pauses on no credits)
  >   **2.** Skip — free ATS scan only `← (default)`
- **Google Jobs** (optional; needs a SerpAPI/Serper key) — Reply with a number:
  >   **1.** Enable (add the key to `.env`)   **2.** Skip `← (default)`
- **Narrative profile** `config/_profile.md` (superpower, deal-breakers — sharpens scoring) — Reply with a number:
  >   **1.** Add a few notes now   **2.** Skip for now `← (default)`

## Finish
Run `python -m jobfinder doctor --json` to confirm `ready: true`, then show the
**command center** (the numbered menu in `AGENTS.md`) and tell them to reply with a
number. Credentials are never collected or printed; `.env` stays theirs.
