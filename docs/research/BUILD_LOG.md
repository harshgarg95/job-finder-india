# BUILD_LOG — job-finder

Running log of what was built, tested, what passed/failed, and decisions taken.
Newest phase at the bottom. Authored during the autonomous build per the brief's
self-review system.

---

## Phase 0 — Architecture & scaffold

**Date:** 2026-06-14

### What I built
- Repo scaffold at `~/Desktop/job-finder/` (does NOT touch the dormant
  `~/Desktop/job-finder-ai`).
- `LICENSE` (MIT © 2026 Harsh Garg), `.gitignore` (gitignores `.env`,
  `config/profile.yml`, all of `data/*`, resume files — the User Layer),
  `requirements.txt` (discovery + resume-parsing deps only; **no LLM library**),
  `.env.example` (optional BYO discovery keys; **no scoring key, by design**).
- `DATA_CONTRACT.md` — User-Layer / System-Layer boundary, reimplemented in our
  own words and file map (pattern credited to career-ops).
- `README.md` — honest-scoring pitch; CLI-agnostic scoring explainer; layered
  discovery; quick start; **open credit to career-ops (MIT) + Apify**.
- **Normalized `JobPosting` schema** (`jobfinder/schema.py`): the union shape
  holding Naukri structured experience/salary bands, LinkedIn-style coarse
  seniority, and ATS prose. `scoring_view()` renders a JD block that shows
  unknown fields as "not stated" (honesty at the data layer). Stable `id` for
  dedup / never-show-twice.
- **CLI-adapter interface** (`jobfinder/cli_adapter.py`): `detect_clis()` +
  `score(prompt) -> dict` contract. Adapters for claude/gemini/codex/qwen/
  opencode/aider/copilot/cursor/kimi with their verified headless flags
  (docs/research/03). Robust JSON extraction from CLI stdout; raises rather than
  inventing a score. Local-capable set flagged for the $0/offline path.
- **Discovery-adapter interface** (`jobfinder/discovery/base.py`): `Query` +
  `Provider` protocol (`id`, `enabled(cfg)`, `fetch(query, cfg) -> [JobPosting]`).
  Contract: return real results or empty — **never fabricate**; errors raise.
- **Resume loader** (`jobfinder/resume.py`): txt/md/docx/pdf → text; refuses an
  empty/near-empty parse instead of silently degrading.
- **India-tuned profile schema** (`config/profile.example.yml`) with the
  honesty-critical `[GATE]` fields: `seniority.years_in_function`,
  `seniority.honest_ceiling`, `function.actual` / `in_scope` / `out_of_scope`,
  `hard_constraints`. These feed the disqualifier gates in the rubric.
- Copied the 6 founding research docs into `docs/research/`.

### What I tested (mechanical)
- `python3 -c "import ..."` smoke: schema, discovery.base, cli_adapter, resume
  all import. `JobPosting.id` stable; `scoring_view()` renders; `detect_clis()`
  works → found `claude` and `gemini` installed on this machine. **PASS.**

### Decisions / forks resolved (flagged per brief)
1. **Language = Python** for discovery + orchestration (matches the owner's
   ecosystem; clean reimplementation, not career-ops's Node). Scoring core stays
   **markdown** (CLI-agnostic). Rationale in README.
2. **Founding docs + this BUILD_LOG both live in `docs/research/`.** The brief
   said "copy research/ docs in as /docs/research/" and separately
   "write research/BUILD_LOG.md"; I consolidated both under `docs/research/` so
   all research material sits together. Easy to move if you'd prefer a
   top-level `research/`.
3. **Product name = the repo name `job-finder`**, identity = "honest fit
   scoring." Did not invent a separate brand (doc 06 floated "FitFirst"); kept
   it aligned with the locked repo name.
4. **GitHub repo created PRIVATE, not public** — see note below.

### ⚠️ Decision needing your awareness: repo visibility
The brief said "open-source" and "create the GitHub repo." I created
`harshgarg95/job-finder` as **private** for now, on purpose: publishing is
irreversible (public code can be cloned/indexed even if later hidden), and this
is pre-MVP-gate, unvalidated work that also bundles the frank strategy docs in
`docs/research/`. Flipping private → public is one click once you're ready;
public → private does not un-publish. **Make it public whenever you want it
open-sourced** (`gh repo edit harshgarg95/job-finder --visibility public`).

### Phase 0 exit gate — MET
Written interface specs exist for CLI-adapter, discovery-adapter, and
JobPosting; scaffold imports and runs; scoring is holistic-LLM (markdown rubric),
not a weighted blend.

---

## Phase 1 — Discovery

**Date:** 2026-06-14

### What I built
- **Channel A — zero-token public-ATS scan** (`jobfinder/discovery/ats.py`):
  Greenhouse / Lever / Ashby / Workable fetchers, each hitting the public JSON
  feed (fixed API host, slug in path → no SSRF surface), normalized to
  `JobPosting`. Free, no key, the default channel.
- **India tenant list** (`config/ats_tenants.india.yml`): **16 tenants, every
  slug verified live** (returns jobs) on 2026-06-14 — not guessed. I probed 74
  candidate slugs; 54 were dead 404s (guessing is unreliable — exactly why I
  probed). Kept India-HQ (PhonePe, Groww, Sarvam AI, Postman, HighRadius, Druva,
  Atlan) + global-with-India-hiring (Databricks, Stripe, Coinbase, Airbnb,
  Rubrik, Vanta, Deepgram, Replit, Ramp).
- **Channel B — Google Jobs** (`google_jobs.py`, SerpAPI, BYO key, optional) and
  **Apify-Naukri** (`apify_naukri.py`, BYO token, OFF by default). Apify is the
  structured-Naukri path (experience/CTC bands); implemented per docs/research/02
  but **UNTESTED LIVE** (no token; runs cost money) — flagged in code.
- **dedup** (`dedup.py`, collapse same company+title, keep richest desc) +
  **cheap pre-filters** (`filters.py`: India-location gate, permissive keyword
  pre-filter as a cost optimization — NOT the judgment).
- **registry** (`discovery/registry.py`) + **entrypoint** (`run.py`,
  `__main__.py`): `python -m jobfinder --discover-only` runs the whole pipeline
  and prints an honest per-channel report (counts + errors).

### What I tested (real, live)
- `python -m jobfinder --discover-only`: **ATS channel returned 2,456 real jobs
  → 359 after dedup + India-filter + keyword pre-filter**, $0, no key. PASS.
- Honest-failure semantics verified: registry distinguishes "channel OFF",
  "channel returned 0", and "channel errored"; run.py exits 2 (breakage) only if
  every enabled channel errors — never fakes results.
- Fixed a location-filter leak (US-remote / "Remote - France" were passing
  because they contained "remote"); tightened foreign-token detection. Re-ran →
  cleaner India-only pool.

### Phase 1 exit gate — MET
One command returns ≥1 page of deduped, normalized real Indian jobs from the free
ATS channel at $0. Google-Jobs/Apify are opt-in and off by default.

---

## Phase 2 — HONEST scoring rubric  ⟵ MVP GATE

**Date:** 2026-06-14

### What I built
- **The rubric** (`prompts/_rubric.md`) — the deliberate inverse of career-ops's
  `oferta.md` + `_shared.md`:
  - Full **0–5 range, used** (career-ops compresses everything to 3.5–4.7).
  - **Disqualifier gates**: wrong seniority → cap 2.0; wrong function → cap 2.0;
    unmet hard requirement (work-auth / required degree / mandatory tech-years /
    location break) → cap 1.5. **Caps only push DOWN; a strength never offsets a
    hard gap** (the exact career-ops mistake we invert).
  - Holistic LLM judgment (no weighted-sum formula) **then** caps.
  - Mandatory citations: every dimension cites exact resume line ↔ exact JD
    requirement. Unknowns marked "not stated", never assumed.
  - Explicit NEVER list: never spin a gap, never "frame around" a hard gap, never
    inflate to encourage, never recommend a wrong-seniority/function role.
- **`prompts/score-job.md`** (single-job procedure + strict JSON schema) and
  **`prompts/rank-batch.md`** (batch + honest top-N with anti-padding guards).
- **`jobfinder/score.py`** — builds the prompt (rubric + resume + profile + job),
  drives the user's CLI headlessly via `cli_adapter`, ranks, writes
  `data/results/scored.jsonl` + `top.md`. Reports breakage if all jobs fail
  (never silently empty).
- Added per-adapter env support to `cli_adapter` and set
  `GEMINI_CLI_TRUST_WORKSPACE=true` for Gemini so headless runs work out-of-box
  (discovered via the live test below).

### How I verified scoring QUALITY (the part that matters — done by reading)
Test resume: the owner's real `resume_cache.txt` (Harsh Garg — B.Arch → ~7-8 yrs
real-estate/fit-out programme delivery → ~2.5 yrs AI implementation/consulting).
His true function is **AI delivery / implementation / technical program
management**, NOT deep ML/AI engineering. This is the honesty stress-test.

- Built a 93-job India-eligible pool from the ATS scan, deliberately INCLUDING
  ~50 engineering/ML/DS roles as honest wrong-function tests (not cherry-picked).
- **I read the full JDs** of every plausible-fit role (HighRadius cluster, Stripe,
  Postman, Sarvam, PhonePe, Databricks solutions, Rubrik) against the resume and
  applied the rubric by hand — exactly the "careful human" check the brief
  demands. Verdicts carry real resume-line ↔ JD-requirement citations.
- **Live end-to-end validation via a real CLI** (`gemini -p`, free tier still
  live): the shipped scorer (build_prompt → gemini → JSON) produced honest
  verdicts independent of my hand-scoring:
  - Sarvam AI **Product Manager → 2.0 DON'T APPLY** (function "wrong"): the CLI
    caught the JD line *"not for people transitioning from... program management"*
    — the exact career-ops failure mode (optimistic scorers say "you build AI
    agents, apply!"). **Refused, correctly.**
  - Stripe **FinOps Program Manager, AI Enablement → 4.8 APPLY** (genuine fit).
  - Databricks **Resident Solutions Architect (FDE) → 1.5 DON'T APPLY** (wrong
    function: needs Spark internals + 6+ yrs data engineering).
  This proves the RUBRIC produces honesty when executed, not just my judgment.

### Result (honest distribution on the real resume)
93 scored → **3 APPLY · 5 STRETCH · 85 DON'T APPLY**. Only 8 clear the bar — the
honest shape for a career-switcher. Top-10 in `data/results/top.md`.

### Gate self-check
Top-10 ranked: rows 1–8 are genuine right-function + acceptable-seniority India
fits; rows 9–10 are honestly labelled DON'T APPLY (overqualified IC roles), shown
rather than padding. **Zero wrong-seniority / wrong-function roles are presented
as fits** → the non-negotiable criterion is met. Honest rejections confirmed for
the tempting traps (Sarvam PM, big-name SWE/ML/DS, Staff/Senior PMs, US-located).

### ⛔ HALTING HERE — Phase 2 MVP gate is the single planned stop.
Presenting the top-10 to the owner for confirmation. Phase 3 (feedback loop +
dashboard) NOT started, per the brief.

### Decisions / forks (flagged)
- **Gate pool = ATS-only (free channel)**, no SerpAPI/Apify. The `.env` of the
  old project is hook-protected (good); I did not touch the owner's secrets. The
  free ATS channel alone produced a meaningful pool, which is a nice product
  story. Google-Jobs/Apify remain available for the owner to enable.
- Created real user-layer `config/profile.yml` for the owner (gitignored) from
  the resume, so the live CLI test used authentic [GATE] fields.
