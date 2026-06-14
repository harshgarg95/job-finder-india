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

---

## Gate review — feedback round 1 (owner, end-user QA)

**Date:** 2026-06-14. The owner reviewed the top-10 at the gate. Two corrections,
both fixed **generically** (rubric/code), with the owner's specifics staying in
his user-layer `config/profile.yml` only.

### Correction 1 — location (Hyderabad-only)
Owner: Bengaluru/Bangalore/Delhi onsite = NOT applicable; only Hyderabad onsite
or fully-remote. I'd wrongly assumed Bengaluru was acceptable.
- Fix (user-layer): `profile.yml` `onsite_cities: ["Hyderabad"]` + hard
  constraints updated. No code hardcoding — the location rule reads from profile.
- Effect: #1/#4/#5/#8 (Stripe/Postman/Sarvam) drop to location-DON'T-APPLY; the
  HighRadius Hyderabad cluster becomes the real top. Owner confirmed the 4
  HighRadius JDs suit him.

### Correction 2 — domain weighting (Stripe FinOps PM rated too high)
Owner challenged the #1 (Stripe FinOps PM, AI Enablement, 4.3): it's a finance
role and his resume isn't finance — should a strong function match rate it
highest? **He was right — this was optimism creep.** Fixes to `prompts/_rubric.md`
(all GENERIC, improve honesty for any resume/domain):
1. **Domain weighted by role-dependency**: domain-as-context (delivery/PM role
   where the employer's industry is just product context) = soft gap; vs
   domain-as-substance (role's core is reasoning about the domain's processes) =
   material gap. Employer industry alone is NOT a domain gap for a delivery role.
2. **Seniority floor**: meeting the bottom of a stated range (8 of "8–12") is a
   MATCH, not "under."
3. **Anti-stacking**: soft gaps (missing cert, low-edge tenure, unworked-but-not-
   required industry) must not compound into a false DON'T APPLY without a real
   hard gate. (Mirror-image of optimism = equally dishonest.)
4. **One adjacent project ≠ domain fluency** for a function-spanning role.
5. **Enforced cap**: domain-as-substance + domain `adjacent` → cap 3.7 (STRETCH);
   `wrong` → cap 3.0. A role in an unworked domain can't outrank a domain-fit role.
- Also corrected profile `years_total` 7 → 8 (calendar-accurate: May 2018–present).

### Live re-validation (gemini -p, real CLI)
- First fix over-corrected: HighRadius APM briefly hit a false **1.5** (stacked
  soft gaps + treated fintech industry as a domain gap on a delivery role).
  Caught it, added anti-stacking + domain-as-context clarity.
- After all fixes: **Stripe FinOps (location aside) 4.8 APPLY → 3.7 STRETCH**
  (domain-substance cap); **HighRadius APM → 3.7** (recovered, genuine fit).
- **Honest limitation recorded:** across tuning runs gemini scored HighRadius APM
  1.5 → 4.4 → 4.1 → 3.7. Single-pass LLM scoring has real variance; the rubric
  CAPS now bound it and the feedback loop is the corrector. Not hidden.

### Corrected ranking (real profile, with location)
2 APPLY · 2 STRETCH · 89 DON'T APPLY — only 4 clear the bar, all HighRadius
Hyderabad (PM 3.9, APM 3.7, APM-II 3.3, Solution Design 3.1). Honest, and it
exposes the next real gap: **discovery breadth** (16 mostly-Bengaluru ATS tenants;
HighRadius is the only Hyderabad-HQ one; zero remote delivery roles). Broadening
discovery for Hyderabad + remote is the agreed next step, owner's call.

### Still halted at the gate. Phase 3 not started.

---

## Phase 1b — Discovery broadening + Google Jobs link verification

**Date:** 2026-06-14. Owner chose to broaden discovery (option A) after the gate,
and flagged a real Google Jobs problem: its `apply_options` links often point to
junk aggregators or dead pages, not a real JD/company page. "Authentication is a
problem."

### What I built
- **Expanded ATS tenant list** (16 → ~41), round 2: added Hyderabad-present
  (Notion) + remote-first companies (GitLab, Twilio, Grafana, Datadog, Vercel,
  Supabase, OpenAI, PostHog, Airtable, Harvey, Cloudflare, MongoDB, Elastic,
  Observe.AI, Sierra, Decagon, ElevenLabs, LangChain, Cockroach, Scale). All
  slugs verified live. Effect: pool 2,456→6,110 raw; **314 Hyderabad-or-remote**
  candidates (was ~the HighRadius cluster).
- **Link resolver + verifier** (`jobfinder/discovery/link_resolver.py`) — the
  "authentication" the owner asked for:
  - Ranks apply links by source: employer (company domain / ATS) > LinkedIn /
    Naukri > acceptable board > junk aggregator (talent.com, jooble, trabajo,
    bebee, lensa, …).
  - Verifies the best link over HTTP using **deterministic structural signals**:
    `error=` redirect + job-id-token survival across redirects (catches ATS
    soft-404s that return 200 but bounce to the board), 404/410 = dead, anti-bot
    codes on a trusted host (LinkedIn 999 / Naukri 403) = real, junk host =
    dropped. Prefers the employer's own page ("go deeper, find its website").
  - First cut used page-text parked-detection → **flaky** (chunked body scan;
    "404" in valid JS). Replaced with structural-only checks → **deterministic**
    (real greenhouse job: ok ×5; soft-404: dead).
- Wired into `google_jobs.py` (threaded verify; `verify_links`/`drop_unverified`
  config) and marked ATS jobs `link_verified=True` by construction. Added
  `link_verified` + `link_source` to `JobPosting`.
- Tests: +3 deterministic resolver tests (tier classification, token, ranking).
  Suite 10/10.

### Validated (real HTTP, no key)
- Tier classify: greenhouse→employer, careers.<co>→employer, linkedin/naukri→
  platform, indeed→board, talent.com/jooble→junk. ✓
- verify: real greenhouse job → ok (stable ×5); expired greenhouse (200→board
  `?error=true`) → dead; junk → dropped. ✓
- resolve_best prefers employer link, skips junk. ✓

### Google Jobs live run — DONE (owner authorized using the old project's key)
Owner authorized copying the discovery key. Copied **only** SERPAPI_KEY +
SERPER_API_KEY into the new `.env` (masked; Groq/Gemini scoring keys deliberately
left out; old project untouched).

**Live result (Hyderabad AI-PM/delivery queries):**
- Google Jobs returned 52 listings → **24 verified, 28 junk dropped**. The
  verifier killed exactly the junk the owner complained about: `google.com/search`
  links, bebee, shine, jobrapido, jobleads, ai-search.io, infinityfree/liveblog365
  free-host spam. Surfaced real employer/LinkedIn/board links.
- Combined verified pool (Google Jobs + ATS, Hyderabad-or-remote): **70 Hyderabad
  + 268 remote**, all link-verified.
- Scored 16 verified-Hyderabad candidates through the real CLI (gemini). Honest,
  well-calibrated output:
  - **APPLY:** D.E. Shaw "Program Manager (GAI Tech)" 4.8 (verified
    deshawindia.com); Southwest "Technology PM, Agentic AI" 4.4; TriNet "Sr TPM" 4.1.
  - **STRETCH:** Google TPM-Payments 3.7 / PM-Voice-AI 3.7; Warner Bros Sr TPM 3.4
    (3+yr eng gate); Eltropy PM-AI-Agents 3.0 (FinTech domain cap); ORBCOMM 3.0
    (logistics domain cap) — the domain-substance cap working in the wild.
  - **DON'T APPLY:** Medtronic Eng Director (20+ yrs), Michael Page Global Head
    (15+ yrs + healthcare mandatory), Amazon Sr TPM (3+ yrs software-dev hard
    gate), Eli Lilly PM (15+ yrs + CS degree) — wrong seniority / hard gates.
- Robustness fixes from the run: SerpAPI "no results" handled as empty (was a
  crash); unknown domains no longer auto-trusted.
- Known item: 1/16 gemini calls errored (long prompt passed as a CLI arg) — single
  transient; consider switching arg-delivery adapters to stdin/temp-file. Logged.

Discovery is now genuinely useful for a Hyderabad seeker. Still pre-Phase-3.

---

## Gate review — feedback round 2 (the analysis gap)

**Date:** 2026-06-14. Owner read the full JDs of the top-3 APPLY picks and showed
all three were actually unsuitable — D.E. Shaw (needs CS degree + 1yr software
dev), Southwest (3yrs AI/ML-platform TPM + 3yrs SAFe + CS degree), TriNet (8yrs
SWE/TPM + deep agile scrum). My scorer rated them 4.1–4.8 APPLY. Two real,
generic gaps found:

### Gap A — truncated JD (data completeness)
Google Jobs/SerpAPI often returns a short *snippet*, not the full JD. D.E. Shaw's
was 1,810 chars with ZERO mention of the degree/dev requirements — the scorer
never saw them. Fixes:
- `discovery/job_fetcher.py`: deep-fetch the full JD from the verified page;
  **Playwright headless fallback** for JS-rendered career pages (Chromium cached);
  enrich threshold raised to 4,000 chars (D.E. Shaw's 1,810 snippet was being
  skipped). Wired into `score.py` (enrich before scoring). LinkedIn/Naukri stay
  snippet-only (bot-blocked) → covered by the safety-net below.

### Gap B — scoring the TITLE, not the REQUIREMENTS (rubric rigor)
Southwest/TriNet had the requirements in-text, but the scorer matched the title
("Technical Program Manager + AI + Hyderabad") and ignored "3yrs SAFe / 8yrs
SWE". Fixes to `prompts/_rubric.md` Dimension 3 + `score-job.md` (generic):
- "**Score the requirements, not the title.**" Extract every quantified/named
  must-have (N years in a SPECIFIC skill/methodology/platform, hands-on software
  development, CS degree, certs) and HARD-gate the unmet ones: one → cap 2.5; core
  or two-plus → cap 1.5; required degree/work-auth → cap 1.5.
- **Incomplete-JD safety net:** if the JD text is a thin snippet (can't confirm
  must-haves), never output APPLY — cap STRETCH and flag for direct verification.

### Re-validated (deep-fetch + stricter rubric, live gemini)
- D.E. Shaw: snippet 1,810 → **8,109 chars deep-fetched** → 4.6 APPLY → **1.5
  DON'T APPLY** (cites unmet CS-degree requirement).
- Southwest: 4.4 APPLY → **1.5 DON'T APPLY** (CS degree + 3yrs AI/ML TPM unmet).
- TriNet: 4.1 APPLY → **1.5 DON'T APPLY** (8yrs SWE/TPM + deep agile scrum unmet).
All three now match the owner's expert read. Tests 10/10.

---

## Phase 3 — Feedback loop + dashboard (owner approved)

**Date:** 2026-06-14.

### What I built
- **`jobfinder/feedback.py`** — the file-based feedback loop (the core
  differentiator; career-ops issue #35 says nobody built it). Corrections persist
  to `data/feedback.jsonl` + a human-readable `data/feedback.md` and **retune
  future scoring** two ways: (a) rejected job_ids are suppressed from future
  results; (b) `lessons_digest()` replays corrections into the scoring prompt as
  binding lessons. Actions: good_match / applied / interested / not_interested /
  wouldnt_apply / wrong_location / wrong_level / wrong_function / wrong_domain.
- **Scorer integration** (`score.py`): loads feedback, suppresses rejected jobs,
  injects the lessons digest into every prompt.
- **`jobfinder/dashboard.py`** — a local tracker UI on `127.0.0.1:8755` (Python
  stdlib http.server, **no new dependency, local-only**). Renders the scored
  shortlist (score, verdict badge, verified link + source, cited reason) with
  one-click corrections that POST to the feedback store. `python -m jobfinder
  dashboard`. CLI alternative: `python -m jobfinder feedback --job … --action …`.
- **Variance fix (important):** a dashboard pre-load run showed Southwest score
  4.2 APPLY when round-2 had correctly given it 1.5 DON'T APPLY — single-pass LLM
  scoring is non-deterministic (owner had also seen HighRadius swing 1.5↔4.4↔3.7).
  Fixed in `score.py`: **score each job N=3× and keep the most conservative
  (lowest) result** (honest scoring errs toward "skip", and records `score_range`
  for transparency). Generic.
- Tests +2 (feedback suppress/lessons/validation), 12/12. Docs updated
  (README feedback-loop section, DATA_CONTRACT, requirements).

### Result (3×-sampled re-score of 12 verified-Hyderabad roles)
- **0 APPLY · 1 STRETCH · 11 DON'T APPLY** — honest for this batch (mostly
  director/15–20yr roles or CS-degree/specific-skill-year gates). The variance fix
  worked: Southwest now **1.5** (range 1.5–2.5 — it kept the low instead of the
  spurious 4.2); Warner Bros/TriNet 1.5 (range 1.5–2.0); lone STRETCH is Google
  TPM-Payments 3.0 (range 3.0–3.7, payments-domain caveat). `score_range` surfaces
  the spread for transparency.
- Dashboard verified end-to-end: GET / renders; GET /api/data returns 12 jobs +
  stats; POST /api/feedback persisted a correction → `suppressed_ids` picked it up
  + `lessons_digest` populated (the loop closes). Test correction then cleared so
  the owner starts clean.

### Note
This batch was Hyderabad Google-Jobs roles; the owner's strongest fits remain the
HighRadius delivery-PM roles (from the gate). The dashboard reads whatever the
latest scoring run wrote; a full re-score across the combined verified pool is a
cheap follow-up.

### Phase 3 exit gate — MET (pending owner confirmation)
A correction made in the dashboard persists to `data/feedback.*`, suppresses the
job, and replays into the next scoring run — no user data leaves the machine.

---

## Discovery widening — Apify multi-platform (owner enabled)

**Date:** 2026-06-14. Owner supplied an Apify token and asked to add LinkedIn /
other platforms (not just Naukri). Confirmed: cookieless Apify actors are the
legitimate way to reach LinkedIn/Indeed/Naukri (public guest API, no login, no
account-ban; BYO-token bears the access).

### What I built
- **`discovery/apify.py`** — generalized multi-platform provider (replaces the
  Naukri-only module). Platforms (actor handles + I/O field maps confirmed
  against live runs): **Naukri** `epicscrapers/naukri-scraper` (startUrls +
  structured experience/CTC), **LinkedIn** `curious_coder/linkedin-jobs-scraper`
  (search URLs + count; no full-permission approval needed), **Indeed**
  `misceres/indeed-scraper` (startUrls + country=IN). One actor run per platform
  per search (multiple title-URLs in a single run → cost-efficient). All actors
  configurable via `discovery.apify.platforms`/`actors`. Links from a platform's
  own API → `link_verified=True`.
- Registry uses it; off unless `APIFY_TOKEN` set. Docs + `.env.example` +
  `profile.example.yml` updated. +1 test (URL builders + mappers). 13/13.
- Note: `harvestapi/linkedin-job-search` (the structured-salary pick) needs a
  one-time "full access" approval in the Apify console; used curious_coder
  instead (works out of the box).

### Live validation
`ApifyProvider.fetch` (Hyderabad, 3 titles, 15/platform) → **45 jobs, 15 each,
0 errors**, correct mapping (Naukri structured experience bands, real verified
URLs across all three). These are India-native roles ATS + Google Jobs never
surfaced.

### Cost note
Each search now also triggers 3 Apify actor runs (billed to the owner's account;
~$0.10 for ~120 results; well within the $5/mo free credit). Trim
`discovery.apify.platforms` to control. Owner advised to rotate the token (shared
in chat).

---

## Naukri full-JD fix (the validation-pass enabler)

**Date:** 2026-06-15. The wider run surfaced the owner's real best-fit roles via
Naukri, but they capped at "STRETCH — verify the JD yourself" because the
`epicscrapers` actor returned only **snippets** (median ~366 chars; the top
"BT Delivery Manager" was 392). Diagnosed it, then switched the Naukri actor to
**`memo23/naukri-scraper`**, which returns the **full** HTML JD (4,153 chars for
the same kind of role; provider median ~1,046, max 7,205) plus structured
experience/salary/location and the absolute URL.

- `discovery/apify.py`: Naukri actor → memo23; input via `startUrls` (multi-title,
  one run) + `maximumJobs`; `_map_naukri` now robust across both actor shapes
  (memo23 full `description` HTML stripped, `locations[]`, `companyDetail.name`,
  `staticUrl`; epicscrapers fallback). cheapest actor ($0.60/1k), most-used.
- Effect: the Naukri channel — the owner's most relevant source — now feeds the
  scorer COMPLETE postings, so its best-fit roles get requirement-gated verdicts
  instead of the incomplete-JD safety-net STRETCH.

