# onboarding — direct-run setup (the USER runs it; you just route them)

`needs_onboarding: true` means a required file is missing, or `config/profile.yml` is empty /
still the placeholder. **Onboarding is a one-time terminal command the USER runs — you do NOT
conduct it in chat, and you NEVER tell the user to hand-edit YAML.** LLM choice + login are
implicit (they already opened their CLI).

## Primary path — tell the user to run it
Show this, then STOP and wait for them to come back:
> Setup needed (one time). In YOUR terminal, run:
> ```
> python -m jobfinder onboard
> ```
> It asks a few questions (arrow-key menus for the choices) and writes your résumé +
> `config/profile.yml` for you. Then come back here and say **"find me jobs"**.

Offer only these two (numbered — the user types the number):
- **1.** I've run it — re-check → run `python -m jobfinder doctor --json`; continue only if
  `needs_onboarding` is now **false** (else tell them it's still not set up and show this again).
- **2.** Help — what setup collects & why → explain briefly (résumé + target roles + location +
  work-mode + seniority + comp floor → written to `resume.md` + `config/profile.yml`; keys are
  never collected), then show this again.

`python -m jobfinder onboard` is interactive and needs a real terminal — it **refuses** if launched
without a TTY (so don't run it yourself from here; it can't read the user's keyboard). Résumé
options are exactly: **paste (Ctrl-D or type `END` on its own line) · file path · LinkedIn text**.
There is **no** template / sample profile and **no** score-without-a-résumé path.

## Automation fallback (only if the user can't use a terminal, or for scripting)
You MAY write the files non-interactively — you ask the questions, **Python writes the YAML** (you
never hand-author it): collect the answers into a JSON file and run
`python -m jobfinder onboard --answers <file.json>`. Flat schema:
`full_name, base_city, target_roles[], years_total, years_in_function, honest_ceiling, work_mode,
onsite_cities[] (required unless remote), floor_ctc_lpa`, plus `resume_text` **or** `resume_path`.
It validates the required fields (refusing a partial write, and a résumé under ~300 chars), writes
both files, then **deletes the answers file** (PII). This is the fallback, **not** the primary path.

## After setup — refine target roles (recommended, agent-side)
Once `config/profile.yml` exists, do this ONCE before the first run. It is an **ENHANCEMENT, not a
gate** — if the user skips it or you're a weak model, the résumé-derived roles stand and the run
still works. **Why it matters:** prescreen is keyword-driven, so `config/profile.yml: target_roles`
decides which jobs enter the funnel *at all*. The regex writer can only lift PRINTED designations —
it may keep a résumé header (e.g. "Project Coordination & Operations") and miss roles the person
should actually target. You can infer better from the real experience; a regex can't.

1. **Read** `resume.md` + `config/profile.yml` (note its current `target_roles.primary`).
2. **Propose 3–5 realistic target roles** grounded in what the résumé shows the person has *done* —
   not just their printed titles (e.g. AI Delivery Manager, Implementation Consultant, Technical
   Program Manager, Solutions Consultant). **FLAG any role the résumé does not support** instead of
   silently accepting it — advisory, not a block: *"your résumé shows no aviation experience, so
   'Pilot' would return jobs that all score DON'T APPLY — keep it anyway?"* The user decides.
3. Show the proposal as a **numbered confirm/edit** list (they reply with a number, or edit it).
4. On accept, WRITE it (Python patches the profile in place — you NEVER hand-edit YAML):
   ```
   python -m jobfinder onboard --set target_roles="AI Delivery Manager,Implementation Consultant,Technical Program Manager"
   ```
   `--set` updates ONLY `target_roles` (and mirrors `function.in_scope`, which prescreen reads);
   every other field is preserved. The same `--set` can correct a mis-answered field without redoing
   onboarding — `work_mode`, `honest_ceiling`, `base_city`, `floor_ctc_lpa` (unknown keys are refused).
5. **Also propose `function.out_of_scope`** — same enhancement-not-gate pattern. Onboarding leaves it
   **empty on purpose**: one persona's opposites are another's core function (defaulting it to
   "ML research / data science / backend" would pre-declare a data scientist's own job out of scope).
   Empty is safe — the rubric's wrong-function cap simply doesn't fire on an unknown. From the résumé,
   propose 2–4 **adjacent-but-different** functions this person should NOT be matched into (for a
   delivery/PM profile: "ML research engineer"; for a data scientist: "front-end engineering"), show
   them as a numbered confirm/edit, and on accept:
   ```
   python -m jobfinder onboard --set function_out_of_scope="ML research engineer,Backend software engineering"
   ```
   If the user skips this or you're a weak model, **empty stands** and the run still works — the
   wrong-function cap just won't fire. Never invent exclusions the résumé doesn't support.

## Then
Re-run `python -m jobfinder doctor --json`, confirm `profile` is gone from `missing_required`, then
show the **command-center** menu (numbered) or tell them to say **"find me jobs."** `.env` stays theirs.
