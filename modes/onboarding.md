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
options are exactly: **paste (Ctrl-D) · file path · LinkedIn text**. There is **no** template /
sample profile and **no** score-without-a-résumé path.

## Automation fallback (only if the user can't use a terminal, or for scripting)
You MAY write the files non-interactively — you ask the questions, **Python writes the YAML** (you
never hand-author it): collect the answers into a JSON file and run
`python -m jobfinder onboard --answers <file.json>`. Flat schema:
`full_name, base_city, target_roles[], years_total, years_in_function, honest_ceiling, work_mode,
onsite_cities[] (required unless remote), floor_ctc_lpa`, plus `resume_text` **or** `resume_path`.
It validates the required fields (refusing a partial write, and a résumé under ~300 chars), writes
both files, then **deletes the answers file** (PII). This is the fallback, **not** the primary path.

## After setup
Re-run `python -m jobfinder doctor --json`, confirm `profile` is gone from `missing_required`, then
show the **command-center** menu (numbered) or tell them to say **"find me jobs."** `.env` stays theirs.
