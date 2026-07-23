# Getting Started — Job Finder India

A plain-language, step-by-step guide. If you've never used an AI coding CLI before, this is written
for you. It takes about 10 minutes to set up.

## What this tool does

It looks at real Indian job postings, compares each one against your résumé, and tells you —
honestly — which ones are worth your time to apply to and which aren't, with the reason for each.
It's built to stop you from either drowning in listings or skipping jobs you'd actually get.

It runs inside an AI coding assistant (a "CLI") that you already have or can install for free. The
tool never sees or stores your passwords — it uses your assistant's own login.

## What you need first

**A capable AI model.** This is the single most important thing. The tool's judgment is only as good
as the AI model running it.

| CLI | Works? | Notes |
|---|---|---|
| **Claude Code** | ✅ **Recommended** | Best results, proven. |
| **GitHub Copilot** | ⚠️ Works, but | The free plan only runs a small "Auto" model, which gives poor, unreliable scores. Fine to try; for real use, a paid plan or Claude Code is much better. |
| **Codex (OpenAI)** | ✅ With setup | Works on a capable model — you must switch models (see FAQ) and it blocks the internet by default (see Troubleshooting). |
| OpenCode / Qwen | ❓ Unverified | May work; not tested end-to-end. |

**Plain version:** use Claude Code if you can. Free Copilot will "work" but give you flat, unreliable
results — that's the model's limit, not the tool's.

---

## One-time setup

### 1. Get the code

```bash
git clone https://github.com/harshgarg95/job-finder-india job-finder-india
cd job-finder-india
```

### 2. Install the helper for nice menus

```bash
pip install -r requirements.txt
```

(This installs `questionary`, which gives you the arrow-key menus. Without it you'll get plain
numbered menus instead — still works, just less pretty.)

### 3. Add your free job-search keys (optional but recommended)

Copy the example file and add two free API keys:

```bash
cp .env.example .env
```

Then open `.env` and fill in:

- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` — free from [developer.adzuna.com](https://developer.adzuna.com) (~250 searches/month)
- `JSEARCH_API_KEY` — free tier from RapidAPI or OpenWeb Ninja (~200/month)

You can skip this — the tool still works using free company career pages (the "ATS floor"). But the
keys give you many more India-native jobs (LinkedIn/Naukri-style listings).

### 4. Set up your profile — run this in YOUR OWN terminal

```bash
python -m jobfinder onboard
```

> ⚠️ **Run this yourself, directly in your terminal — not by asking the AI to do it.** This is the
> one step you drive by hand, and it's quick. (It needs a real keyboard, so it will politely refuse
> if an assistant tries to run it.)

It will ask you a few things:

**First, your résumé.** Pick one:

1. **Paste it** — paste your résumé, then press Enter to move to a new line, and press Ctrl-D
   once. (Pressing Ctrl-D without first going to a new line may need several presses or not
   register — a terminal quirk, not a bug.) Simplest: type `END` on its own line instead.
2. **Give a file path** — e.g. `/Users/you/Downloads/resume.pdf` (`.pdf`, `.docx`, `.md`, or
   `.txt`). This is the easiest option for a long résumé — no pasting.
3. **Paste your LinkedIn text.**

**Then a few short questions.** For most of them the tool has already filled in a smart guess from
your résumé:

- 👉 **Press Enter to accept the suggestion**, or type a new answer to change it. You do not need to
  answer everything from scratch.
- Use the **↑ / ↓ arrow keys** to move through menu options, and **Enter** to pick one.
- The only things it asks fresh (it can't guess these from a résumé): your **work mode**
  (remote / hybrid / on-site) and whether you're **open to relocating**.
- Everything else — name, city, years, target roles — is pre-filled; just glance and hit Enter.

*(What you'll see: a small list — Remote / Hybrid / On-site / Open to a mix — that you move
through with ↑/↓ and confirm with Enter.)*

When it finishes it writes two files for you (`resume.md` and `config/profile.yml`) and tells you
what to do next. **Glance at the target roles it picked up** — they're in `config/profile.yml` and
they drive which jobs you'll see. (Your CLI can also propose better ones from your résumé on the
first run.)

### 5. Check you're ready

```bash
python -m jobfinder doctor
```

It should say **`Status: READY`**. If it says setup is incomplete, re-run step 4.

---

## Finding jobs

### 1. Open your AI assistant in this folder

```bash
copilot --allow-all-tools
```

> 👉 The `--allow-all-tools` part matters — without it, the assistant stops and asks you to approve
> every single command (you'd be typing "yes" dozens of times). This flag approves them
> automatically. (In Claude Code, the equivalent is accepting the tools when it first asks, or
> running in an auto-approve mode.)

### 2. Just say what you want

```
find me jobs
```

That's it — plain English. The tool will:

- **Discover jobs** (~1–2 min) — you'll see progress like `discovery: adzuna 91` and
  `discovery: 1384 raw → 210 candidates`
- **Shortlist** the most relevant ~40, then **score the top 15** in detail
- **Show you results** grouped as:
  - ✅ **APPLY** — strong fit, worth applying
  - 🟡 **STRETCH** — a reach, but worth considering
  - ❌ **DON'T APPLY** — with the specific reason (wrong function, too senior, wrong location…)
  - ⚠️ **Couldn't verify** — the tool couldn't read the posting; check it manually

Every verdict comes with a reason tied to your résumé — not a black-box number.

*(What you'll see: each job as a scored entry — e.g. "4.2 · APPLY — Technical Program Manager,
with the résumé-line reasons" — and further down, the DON'T APPLYs each with their reason.)*

The full report is saved at `data/results/top.md` — open it any time (on macOS:
`open data/results/top.md`). **Best viewed in the dashboard (next section):** clickable, with
Applied / Interested / Not-suitable buttons that make future runs smarter.

## The dashboard (recommended)

For a clean, clickable view of your results:

```bash
python -m jobfinder dashboard
```

This opens a page in your browser (`http://127.0.0.1:8755`) showing all your scored jobs. For each
one you can click **Applied**, **Interested**, or **Not suitable** — and the tool learns from this,
quietly down-ranking the kinds of jobs you reject in future runs. Press Ctrl-C in the terminal to
stop it.

*(What you'll see: each scored job as a card with three buttons under it —
Applied · Interested · Not suitable.)*

---

## FAQ

**Q: The assistant keeps asking me to approve each step — do I keep typing "yes"?**
No — that's the sign you didn't use the auto-approve flag. Restart with `copilot --allow-all-tools`
(or accept tools when Claude Code first asks). Then it runs without interrupting you.

**Q: During setup, do I keep pressing Enter?**
Press Enter to accept each suggested answer (the tool pre-fills most from your résumé). Only type
something when you want to change the suggestion. For menus, use arrow keys + Enter.

**Q: I pasted my résumé but it won't move to the next step / I'm pressing Ctrl-D many times.**
Ctrl-D only signals "done" when the cursor is at the start of a fresh line — pasting leaves you
mid-line, so press Enter first, then Ctrl-D once. Or type `END` on its own line and press Enter —
it ends the paste immediately. Easier still for a long résumé: choose the "give a file path" option
and skip pasting entirely.

**Q: It told me to switch to GPT-5 or Claude, but I'm on free Copilot with no model choice.**
Free Copilot only offers "Auto" — there's no dropdown to change. The tool will still run, but
scoring quality will be limited by that small model. For reliable results, use Claude Code or a paid
plan that lets you pick a capable model. This is a model limitation, not a bug.

**Q: All my scores came out the same (e.g. everything 4.0), or nothing was rejected.**
That's the signature of a weak model not applying the scoring properly. Switch to a capable model
(Claude Code, or GPT-5/Claude in a paid CLI) and re-run.

**Q: It said "Scored 3 of 15 — incomplete."**
The model stopped early (usually a smaller model running out of steam). Just say `find me jobs`
again to finish, or switch to a capable model.

**Q: A job link is dead when I click it.**
Job postings close over time. When scoring, the tool checks it can actually *read* each posting —
anything it can't read goes to "Couldn't verify" rather than being guessed at. To check whether a
specific posting is still open, run `python -m jobfinder live <job_id>`. Postings can still close
between scoring and applying, so apply promptly to the ones you like.

**Q: Where does my résumé/data go? Is it private?**
It stays on your machine. Your résumé and profile are stored locally, are never uploaded anywhere,
and are excluded from git so they can't be committed by accident. The tool uses your AI assistant's
own login for scoring — it never handles your passwords.

---

## Troubleshooting

**"⚠️ Discovery FAILED: no channel could be reached."**
Your internet isn't reachable from the tool. Two common causes:

1. **You're offline** — check your connection.
2. **You're using Codex**, which blocks internet access by default. Start it with network enabled:
   ```bash
   codex -s workspace-write -c 'sandbox_workspace_write.network_access=true'
   ```
   (If that still fails on macOS, `codex --sandbox danger-full-access` — but only in a throwaway
   copy of the folder, as it also relaxes file protections.)

Note: when discovery fails, **nothing was scored and `data/results/top.md` was not updated** — any
file there is from an earlier run, not this one.

**Codex says the model "is not supported" (a 400 error).**
Codex's default model isn't allowed on ChatGPT accounts. Type `/model` inside Codex and pick a
supported model (a `gpt-5.x`), then say `find me jobs`.

**`doctor` says setup is incomplete.**
Run `python -m jobfinder onboard` in your own terminal (not via the AI). If it still complains,
check that `config/profile.yml` and `resume.md` were created in the folder.

**The menus show as plain numbers, not arrow-key selectable.**
Install the menu helper: `pip install -r requirements.txt` (or `pip install questionary`). The
numbered menus work fine too — just type the number.

**The tool re-ran discovery in the middle of scoring / seems to loop.**
This is handled automatically now — discovery refuses to re-run while scoring is in progress. If you
ever see it, let it finish; it won't double-charge or corrupt anything.

---

## A realistic note on cost and speed

Each full run uses a few minutes and some of your AI plan's usage (on Claude Code or a paid CLI, a
handful of credits; on free tiers, more of your daily limit). This is normal for AI-heavy work. If
runs feel slow, that's the model thinking — a faster/capable model helps most.

Discovery itself is free by default (the ATS floor needs no key), and the optional Adzuna/JSearch
free tiers are capped per month so they can't run away.

---

That's everything. Set up once, then it's just: **open your CLI → "find me jobs" → review in the
dashboard.**
