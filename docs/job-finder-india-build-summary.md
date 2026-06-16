# Job Finder India — Build Summary & Handoff

*A shareable summary of what was built in the Claude Code session, for continuing
the conversation elsewhere. Written 2026-06-15.*

---

## 1. What it is

**Job Finder India** — a free, open-source, **local-first**, **CLI-agnostic** AI
job-search tool built for the **Indian market**. Upload a résumé → it discovers
real jobs, then scores each against your résumé and **tells you the honest truth
about fit** — it says "don't apply" when it's a no, instead of talking you into
applying.

- **The one differentiator: honest fit scoring.** Built as the deliberate
  *opposite* of optimistic "AI match" tools (and of career-ops's scoring, which
  inspired the architecture). A gap in seniority, function, or a hard requirement
  is a **disqualifier**, not "something to frame around."
- **Repo:** `github.com/harshgarg95/job-finder-india` (currently **private**),
  MIT licensed, openly credits **career-ops** (MIT) and **Apify**.
- **No AI API key held by the app.** Scoring runs through whatever AI CLI the
  user already has (Claude Code / Gemini / Codex / etc.), driven headlessly. Your
  résumé and search history never leave your machine.
- Status: **21 commits, 18/18 tests passing, feature-complete and verified** on
  the owner's real résumé.

---

## 2. How it works (the pipeline)

```
résumé + profile
   │
   ▼
DISCOVER  ── 4 channels ──────────────────────────────────────────────
   │   • ATS scan (free, no key): 37 Greenhouse/Lever/Ashby tenants
   │   • Google Jobs (BYO SerpAPI key): indirect LinkedIn/board coverage
   │   • Apify (BYO token): Naukri + LinkedIn + Indeed (cookieless, no stealth)
   ▼
VERIFY LINKS ── drop junk/dead, prefer the employer's real page
   ▼
DEEP-FETCH the FULL JD (Playwright fallback for JS pages)
   ▼
TIER-0 PRE-SCREEN (free, deterministic) ── reject clear misfits, no LLM
   ▼
HONEST SCORING ── your AI CLI runs prompts/_rubric.md
   │   • requirements-gated (score the requirements, not the title)
   │   • normalized skills injected (our mini "skills graph")
   │   • scored 3× → keep the most conservative; auto-fails over between CLIs
   ▼
RANKED SHORTLIST  +  qualifications breakdown (met/partial/missing)
   ▼
DASHBOARD + FEEDBACK LOOP ── corrections persist & retune the next run
```

Run it: `python -m jobfinder --resume <path>` then `python -m jobfinder dashboard`.

---

## 3. The honest-scoring engine (the heart)

The rubric (`prompts/_rubric.md`, executed by the user's CLI) enforces:
- **Full 0–5 scale, actually used** — most jobs score low for any given résumé;
  that's honest. Verdict: **APPLY / STRETCH / DON'T APPLY**.
- **Disqualifier caps** — wrong function → ≤2.0; wrong seniority → ≤2.0; a missing
  hard requirement (degree / work-auth / N-years-in-named-skill) → ≤1.5. Caps only
  push *down*; a strength never offsets a hard gap.
- **Score the requirements, not the title** — extract every quantified/named
  must-have ("3 yrs SAFe", "8 yrs software engineering", "CS degree") and gate on
  the missing ones. A matching title is not a matching candidate.
- **Domain weighted by role-dependency** — a delivery/PM role at a fintech is
  *domain-as-context* (soft); a role whose core job is reasoning about finance is
  *domain-as-substance* (caps to STRETCH if the candidate lacks it).
- **Qualifications breakdown** — every score lists each requirement as
  **met / partial / missing** with the exact résumé-line ↔ JD-requirement citation
  (the LinkedIn "how you match" model, but kept honest).
- **Conservative + resilient** — each job scored multiple times, lowest kept;
  automatic **CLI failover** (if one CLI hits a quota/rate/auth wall, switch to
  the next).

---

## 4. Key components (file map)

| Path | What it owns |
|---|---|
| `prompts/_rubric.md` | The honest scoring law (the anti-optimistic rubric) |
| `prompts/score-job.md` · `rank-batch.md` | Single-job + batch scoring procedures + JSON schema |
| `jobfinder/score.py` | Orchestration: prompt build, CLI drive, conservative 3×, rank |
| `jobfinder/cli_adapter.py` | Default-less CLI driver + **auto-failover** + JSON extraction |
| `jobfinder/discovery/ats.py` | Zero-token Greenhouse/Lever/Ashby/Workable scan |
| `jobfinder/discovery/google_jobs.py` | Google Jobs (SerpAPI) + link verification |
| `jobfinder/discovery/apify.py` | Naukri + LinkedIn + Indeed via Apify (cookieless) |
| `jobfinder/discovery/link_resolver.py` | "Authentication": rank + verify apply links, drop junk |
| `jobfinder/discovery/job_fetcher.py` | Deep-fetch full JD (requests + Playwright fallback) |
| `jobfinder/prescreen.py` | Tier-0 free deterministic gate (experience/comp) |
| `jobfinder/skills.py` | Lightweight skills taxonomy: normalize / extract / match |
| `jobfinder/feedback.py` | File-based feedback loop (suppress + replay as lessons) |
| `jobfinder/dashboard.py` | Local-only tracker UI (stdlib server) |
| `config/profile.example.yml` | India-tuned profile schema with `[GATE]` fields |
| `config/ats_tenants.india.yml` | 37 live-verified India-relevant ATS tenants |
| `DATA_CONTRACT.md` | User-Layer vs System-Layer boundary (privacy promise) |
| `docs/research/BUILD_LOG.md` | Granular per-phase dev log |

---

## 5. Discovery — layered & legitimate (no stealth, ever)

1. **ATS scan** (default, free, no key) — 37 verified India-relevant company
   boards. Reliable, but misses Naukri-native + recruiter-posted roles.
2. **Google Jobs** (optional, BYO SerpAPI key) — indirect LinkedIn/board coverage;
   every apply link is **verified** (junk aggregators like bebee/jobrapido/
   google-search links are dropped; the employer's own page is preferred).
3. **Apify, BYO-token** (optional) — **Naukri + LinkedIn + Indeed** via cookieless
   community actors (public guest APIs — no login, no account-ban risk). Naukri is
   the key India unlock; `memo23` actor returns full JDs.

**Never:** anonymous proxy scraping, stealth/anti-bot evasion, or auto-apply.

---

## 6. How it got good — the QA rounds (the real story)

The owner stress-tested as an end user; **each round found a real bug, fixed
generically.** This is why the scoring is trustworthy:

1. **Location** — "Bengaluru isn't acceptable, Hyderabad-only/remote" → corrected
   the location gate.
2. **Domain over-weighting** — a finance role (Stripe FinOps) was rated #1 despite
   no finance background → added domain-weighted-by-role-dependency.
3. **Title vs requirements** — top picks had buried gates ("CS degree", "3 yrs
   SAFe") the scorer ignored → **score-the-requirements-not-the-title** + **full-JD
   deep-fetch** (Google/Naukri served snippets that hid the gates).
4. **Single-pass variance** — same job scored 1.5↔4.8 across runs → **score 3×,
   keep the most conservative**.
5. **CLI quota wall** — gemini's free quota hit `TerminalQuotaError` mid-run →
   built **automatic CLI failover**.
6. **gemini stdin bug** — a "hardening" change broke `gemini -p` (it needs the
   prompt as an arg) and dropped the 2 best roles → reverted; caught only by
   running it for real.
7. **LinkedIn matching research** — dissected how LinkedIn matches; verdict: it's a
   **data moat** (skills taxonomy + behavioral signals), not a secret method →
   built our own lightweight skills taxonomy/normalization (`skills.py`).
8. **Feedback UX** — simplified to **Applied / Wouldn't-apply (+reason)**, hid
   DON'T-APPLY behind a toggle, collapsed qualifications by default, added undo.

---

## 7. Validation on the real résumé (Harsh Garg)

Profile: B.Arch → ~8 yrs delivery/programme management → ~2.5 yrs AI
implementation/consulting. True function = **AI delivery / implementation /
technical PM**, not deep ML/AI engineering.

- **Honest result:** most roles correctly score DON'T APPLY (wrong function for
  SWE/ML/DS roles; wrong seniority for Director/15–20yr roles; hard gates like
  "CS degree" / "comp below floor").
- **Best-fit roles found via the India-native Naukri channel:** *BT Delivery
  Manager, AI Automation* (LiveRamp / Matchpoint, Hyderabad, 3–5 yrs) → **APPLY
  ~4.4 / STRETCH 3.8** — genuine function + level + location match, with a
  qualifications breakdown and a deterministic skills check.
- The tool reliably distinguishes "looks related" (AI/ML keyword overlap) from
  "actually a fit" (right function + seniority + requirements).

---

## 8. Decisions & constraints (locked)

- CLI-agnostic, **no scoring API key** in the app; user picks the CLI.
- **No stealth, no auto-apply, no anonymous scraping.**
- **Local-first**; data never leaves the machine (see `DATA_CONTRACT.md`).
- **India-first** scoring (CTC/LPA, notice period, experience bands, Naukri).
- Clean reimplementation of career-ops *patterns* (no copied files); open credit.

---

## 9. What's left / open

**Two-minute housekeeping (owner action):**
- **Rotate the Apify token** (it was pasted in chat during the build).
- **Flip the repo public** (`gh repo edit harshgarg95/job-finder-india --visibility public`) when ready to open-source.

**Optional next refinements (designed, not built):**
- Cache the structured JD-requirements extraction (separate extract from match).
- Confidence-gating: skip the expensive 3× pass when Tier-0 + a quick check
  already make it a clear yes/no.
- Local-embedding pre-rank for triage.

**Deferred by design (Phase 4 — not built):** PDF/CV tailoring, cover-letter
drafting, full web UI, interview-prep. (Auto-apply: never.)

**Honest caveats:**
- Scoring quality depends on the user's chosen CLI + its free-tier limits (which
  shift often — hence the CLI-agnostic design).
- The skills taxonomy is scoped to AI/tech/delivery/PM (extensible to other fields).
- Naukri/LinkedIn links are real but Apify runs cost the user's own credits.

---

## 10. One-line pitch

*"The job-search tool that tells you the truth about fit — built for India, runs
on your machine, learns from your corrections, and never talks you into a job
you'd be auto-rejected from."*
