# onboarding — first-run setup (the agent ASKS · Python WRITES)

Enter this mode when `python -m jobfinder doctor --json` reports `needs_onboarding: true` — a
required file is missing, **or** `config/profile.yml` is empty / still the placeholder template.
**LLM choice + login are implicit** — the user already opened their own CLI; never ask which
model or for an API key/token.

**Open with a one-line context note** (fill in your ACTUAL CLI + model), then begin Step 1:
> You're running in **<detected CLI>** (Claude Code / GitHub Copilot / Codex / …) on **<your model>**.
> For best results use a capable model — **not** Copilot "Auto" / `gpt-5-mini`. Let's set you up.

## HARD RULES (follow EXACTLY — a weak model especially)
- **YOU ask the questions; PYTHON writes the files.** You collect the answers in chat, write them
  to ONE JSON file, and run `python -m jobfinder onboard --answers <file>` — the tool writes
  `resume.md` + `config/profile.yml` from your JSON. **You NEVER hand-author YAML**, and you never
  tell the user to create or edit the files themselves.
- **Ask a step's questions, then STOP and WAIT** for the reply and capture it. No assuming, no skipping.
- **You MUST NOT proceed to `evaluate` / `scan`** until `python -m jobfinder doctor --json` shows
  `profile` is **gone from `missing_required`** (i.e. `resume.md` + a non-empty `config/profile.yml`,
  both written from the user's answers).
- **Phrase every CHOICE as its own discrete multiple-choice prompt** — one question, options one
  per line, ending **"Reply with the number."** — and ask the choice questions **one at a time**
  (not bundled). Capable CLIs (Codex / GitHub Copilot) render these as native **arrow-select**
  menus; others show a plain numbered list the user types into. Free-text fields (name, city,
  target roles, comp) are open questions. Either way, the answers feed the same `--answers` write.

## Step 1 — Collect the RÉSUMÉ
Ask this, then STOP and WAIT:
> How would you like to give me your résumé? Reply with the number:
>   **1.** Paste your résumé text here
>   **2.** Give me a file path (`.pdf` / `.docx` / `.md` / `.txt`)
>   **3.** Paste your LinkedIn profile URL
>   **4.** Just describe your background and I'll draft it

Capture it into the answers object (written in Step 3) — do not hand the work back:
- **1 (pasted)** → `"resume_text": "<their full text>"`.
- **4 (described)** → draft a clean résumé from what they say → `"resume_text": "<your draft>"`.
- **2 (path)** → `"resume_path": "<their path>"`.
- **3 (LinkedIn)** → we do NOT scrape; ask them to paste the profile text, then draft → `"resume_text"`.

(If the résumé is empty/too short, `onboard` rejects it — you then re-ask for the pasted full text.)

## Step 2 — Collect the PROFILE
You **MUST** explicitly ask for **target roles, LOCATION, and WORK-MODE** — they drive the hard gates.

**Free-text questions** (open input — ask, then STOP and WAIT):
- **Full name** · **email** (optional).
- **Base city** — e.g. *"Hyderabad, India"* — **required**.
- **Target roles** — comma-separated, e.g. *"AI Delivery Manager, TPM–AI, AI PM"* — **required**.
- **Years** — total experience · years in your target function — **required**.
- **Comp** — floor / walk-away LPA (**required**) · target LPA (optional).
- **Hard constraints** — optional (e.g. no-PhD, work-authorisation).

**Discrete multiple-choice questions** (ask each as its OWN arrow-select prompt, one at a time):
- **Honest ceiling** — the highest level you can credibly claim today. Reply with the number:
  >   **1.** Intern  **2.** Junior  **3.** Mid  **4.** Senior  **5.** Lead  **6.** Manager  **7.** Director
- **Work-mode** — Reply with the number:
  >   **1.** Remote   **2.** Hybrid   **3.** On-site   **4.** Open to a mix
  >
  >   If **2 / 3 / 4**, then ask (free text) *"Which city/cities for on-site?"* — **required** for those.
- **Open to relocating?** — Reply with the number:
  >   **1.** Yes   **2.** No

## Step 3 — WRITE via the tool (Python writes; you don't)
Assemble everything into one file `data/_onboard_answers.json` (flat keys — shape below), then run:
```bash
python -m jobfinder onboard --answers data/_onboard_answers.json
```
Answers shape (include only what you collected — the tool derives `function.*` and defaults the rest):
```json
{"resume_text":"…full text…","full_name":"…","email":"…","base_city":"Hyderabad, India",
 "target_roles":["AI Delivery Manager","Technical Program Manager - AI"],
 "years_total":8,"years_in_function":2.5,"honest_ceiling":"manager",
 "work_mode":"remote","onsite_cities":["Hyderabad"],"willing_to_relocate":false,
 "floor_ctc_lpa":20,"target_ctc_lpa":28,"hard_constraints":["No PhD-required roles"]}
```
- The tool writes `resume.md` + `config/profile.yml`, then **deletes the answers file** (it holds PII).
- **If the output JSON has `"error"` / `"problems"`** (e.g. `missing required: floor_ctc_lpa`, or
  "résumé too short"), ask the user for exactly those, update the JSON, and re-run. **Never proceed
  on an error**, and never fabricate a value to get past validation.

## Step 4 — Confirm the wrong-function guardrail (a quick confirm, not a hard question)
The tool auto-derived `function.out_of_scope` (the list that powers the **wrong-function gate**) from
a sensible default. **Read that list from `config/profile.yml` back to the user and confirm it:**
> To gate out wrong-function roles, I've marked these as out-of-scope for you:
> <the function.out_of_scope list>. Anything to add or remove? (or say "looks good")

If they change it, re-run the write with the correction, e.g.
`python -m jobfinder onboard --answers data/_onboard_answers.json --set function_out_of_scope="ML research engineer, Data scientist, Backend engineer" --force`.

## Step 5 — Sources + finish
- The free **ATS + Adzuna + JSearch** channels are ON by default and need no key — say so. Optional:
  **Apify deep-mode** (`APIFY_TOKEN` in `.env`) and a narrative `config/_profile.md` (sharpens scoring).
- Run `python -m jobfinder doctor --json`, confirm `profile` is no longer in `missing_required`, then
  show the **command-center** menu (numbered) or tell them to say **"find me jobs."**
  `.env` stays theirs; keys are never collected or printed.
