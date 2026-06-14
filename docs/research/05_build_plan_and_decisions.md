# 05 — Build Plan & Decisions

**Purpose:** This is the synthesis document. It folds the four research studies — [career-ops](01_career_ops_deep_study.md), [Apify](02_apify_discovery_study.md), [CLI/API economics](03_cli_and_api_economics.md), and the [competitive landscape](04_competitive_landscape.md) — into one build plan for a ground-up rebuild of an **India-focused, CLI-agnostic AI job-search tool**.

**Date compiled:** 2026-06-09. Every load-bearing fact here traces back to a verified claim in Docs 1–4 (each of which cites its live source). Where this document makes a *decision* or an *assumption* rather than restating a verified fact, it is marked **[DECISION]** or **[ASSUMPTION]** so we don't silently reverse it later.

> **Relationship to the current codebase.** The existing `job-finder-ai` (Flask + `hybrid_scorer.py` keyword+Groq weighted blend + SerpAPI/Serper scraping) is the "before." This plan is the "after." Nothing in the current code is modified by this research effort — these are reference docs only. The rebuild is a deliberate architectural reset, not a refactor.

---

## TL;DR — the build decision (5 lines)

1. **Architecture:** CLI-agnostic (no default AI provider) + markdown-prompt holistic scoring (career-ops pattern) + Apify-for-Naukri/LinkedIn/Indeed **plus** zero-token public-ATS scan for discovery — all local-first, data never leaves the machine.
2. **Borrow** career-ops's 6-dimension holistic rubric, mandatory citations, data-contract boundary, no-spray ethics, and feedback-via-files loop; **add** India structured data (Naukri CTC/experience bands), India job-board breadth, and standalone discovery that doesn't depend on a paid coding agent.
3. **The wedge** (from the gap analysis): *no tool combines Naukri-grade structured data + holistic LLM fit-scoring + CLI-agnostic + local/free/self-hosted + no-spray ethics.* The only thing close is a 10-star solo fork. That intersection is ours to own.
4. **Roadmap:** Phase 0 architecture → Phase 1 discovery → **Phase 2 scoring (MVP GATE)** → Phase 3 feedback → Phase 4 deferred (PDF/cover-letter/UI). The gate is hard.
5. **Non-negotiable success criterion:** on the owner's real resume, the **top 10 results contain zero wrong-seniority and zero wrong-function matches.** Everything else is secondary to this.

---

## 1. Confirmed architecture

The rebuild has three pillars, each chosen because the research closed off the alternatives.

### 1.1 CLI-agnostic scoring with NO default provider  **[DECISION]**

**What:** The tool does not bundle or assume an AI provider. It detects whichever agentic CLI the user already has, lets the user pick, and drives it **headlessly** to score jobs against the resume. Every major CLI exposes a non-interactive one-shot flag we can shell out to (verified in [Doc 3](03_cli_and_api_economics.md)):

| CLI | Headless invocation | Local/Ollama? |
|---|---|---|
| Claude Code | `claude -p … --output-format json --json-schema …` | No (hosted/Bedrock/Vertex) |
| Gemini CLI | `gemini -p … --output-format json` | No |
| Codex CLI | `codex exec …` | **Yes** (`--oss` → Ollama/LM Studio) |
| Qwen Code | `qwen -p …` | **Yes** (Ollama/vLLM) |
| OpenCode | `opencode run …` / `opencode serve` `--format json` | **Yes** (any provider) |
| Copilot CLI | `copilot -p …` | No |
| Aider | `aider -m …` / `-f` | **Yes** (Ollama + any OpenAI-compatible) |
| Cursor CLI | `agent -p … --output-format json` | No |
| Kimi CLI | `kimi -p … --quiet` | Partial (self-host K2) |
| Amazon Q | `q chat` (headless flag **unverified** — Doc 3) | No |

**Why default-less, not "pick a sensible default":** the economics research found **four first-party free-tier upheavals inside a ~2-month window** (all verified against official sources):
- **Qwen** discontinued its free OAuth tier (1,000 → 100 → 0 req/day, Apr 13–15 2026).
- **GitHub Copilot** moved everyone to usage-based AI Credits (Jun 1 2026).
- **Anthropic** carved `claude -p`/Agent SDK out of subscription limits into a separate metered credit at full API rates (**Jun 15 2026**).
- **Google** is terminating Gemini CLI's free individual access (**Jun 18 2026** — i.e. ~9 days after this document) and migrating users to Antigravity, whose free cap is much smaller and only community-reported.

Hard-depending on any one of these is unsafe by construction. The career-ops project reached the same conclusion ("you are not locked into one provider's roadmap or pricing" — [Doc 1 §1.1](01_career_ops_deep_study.md)). **CLI-agnostic is the only durable posture.**

**Design implication — the local-model escape hatch is the privacy-and-cost story:** Codex (`--oss`), Qwen, OpenCode, and Aider can all run a local Ollama/vLLM model. For a self-hosted, privacy-first Indian tool whose promise is "data never leaves your machine," **the recommended steer for cost/privacy-sensitive users is a local model via one of those four CLIs** — genuinely $0, offline, no card, no data egress. Hosted CLIs (Claude Code, Gemini, Cursor) are supported for users who prioritize quality and already pay.

> **Contrast with career-ops worth keeping in mind:** career-ops *is* the prompt files and relies on the user's coding CLI to do *everything*, including the scan. We are taking the CLI-agnostic *scoring* idea but **decoupling discovery from the CLI** (§1.3) so our scraper/scorer can run standalone and the LLM is invoked only for the judgment step. This is the one place we deliberately diverge from career-ops's architecture.

### 1.2 Markdown-prompt holistic scoring (career-ops pattern, India-retuned)  **[DECISION]**

**What:** Scoring is a **rubric-guided LLM holistic judgment**, expressed as markdown prompt files, **not** a closed-form keyword/weighted-sum scorer. We adopt career-ops's verified core ([Doc 1 §2](01_career_ops_deep_study.md)):

- **6 dimensions:** match, north-star alignment, comp, cultural signals, red flags, global.
- **1.0–5.0 scale**, with **4.0 as the apply / don't-apply line** (and a softer 3.5 "don't bother" floor — both verified).
- **No closed-form math.** career-ops states it verbatim: *"There is no weighted-average formula in the code. The global score is the LLM's judgement of overall fit, given the rubric and the sub-dimensions."* Their rationale (JD heterogeneity, per-user archetype variation, honesty about the engine being an LLM) applies equally to us.
- **Mandatory citations.** Every score cites **exact CV lines + exact JD requirements**. This is the auditability mechanism and the single most important quality guardrail.

**Why this over our current `hybrid_scorer.py`:** the existing tool uses keyword score + Groq score in a weighted blend. The competitive research ([Doc 4 §5](04_competitive_landscape.md)) shows keyword-match is exactly what Jobscan and Naukri's Relevance Score already do — and it "optimizes for the bot, not the human." The holistic-LLM-with-citations approach is the differentiator a *seeker* can trust. **This is a conscious move away from weighted-blend scoring.** (We may still keep a cheap keyword pre-filter to cut the candidate set before the expensive LLM pass — see §1.3 — but the *scoring decision* is holistic, not arithmetic.)

**India retuning — what changes vs career-ops's rubric:**
- **Archetypes** are India-market roles, defined in a user-editable profile (career-ops's `_profile.md` customization model is built exactly for this). The `career-ops-india` fork already proved the move: 7 India archetypes (AI/ML, GenAI, Data Science, consulting, …).
- **Comp dimension** scores on **CTC/LPA, in-hand estimate, notice period, and bond penalties** — the fields India actually negotiates on — not Western base-salary heuristics.
- **Red-flags / legitimacy** gains an India-tuned ghost-job signal (career-ops-india's "Ghost Likelihood Score 0–100 across 9 signals" is the template; Naukri repost-spam is rampant). Keep career-ops's rule that legitimacy is a *separate qualitative assessment that does not move the 1–5 score* ([Doc 1 §3 Block G](01_career_ops_deep_study.md)).

**The evaluation flow** we reimplement (in our own words) mirrors career-ops's Step-0 archetype detection + Blocks A–G (Role Summary → CV Match → Level Strategy → Comp & Demand → Personalisation → Interview Prep → Posting Legitimacy). For the MVP we likely only *need* A–D (summary, CV match, level, comp) to hit the success gate; E–G are quality layers added later.

### 1.3 Discovery: Apify (incl. Naukri structured) + zero-token public-ATS scan  **[DECISION]**

career-ops scans **only** public ATS APIs (Greenhouse/Ashby/Lever/Recruitee/SmartRecruiters/Workable) and ships **zero India sources** ([Doc 1 §4](01_career_ops_deep_study.md)). That's our opening. We run **two discovery channels** side by side:

**Channel A — Zero-token public-ATS scan (borrowed pattern).** Reimplement career-ops's plugin-provider model: each source is a small adapter hitting a public JSON endpoint, no LLM tokens. Borrow the *architecture*; **replace the source list with India-relevant ATS tenants** (Indian companies on Greenhouse/Ashby/Lever/Workable, plus Wellfound-India). Free, fast, legally clean (public ATS APIs), good for funded-startup roles.

**Channel B — Apify for the big Indian boards (the India differentiator).** The Naukri/LinkedIn/Indeed coverage career-ops refuses to do, we do via **the user's own Apify token** ([Doc 2](02_apify_discovery_study.md)):
- **Endpoint:** `POST /v2/acts/<actor>/run-sync-get-dataset-items`, token as `Authorization: Bearer` header (never in URL), POST body = actor input.
- **Naukri is the unlock.** Multiple community actors return **structured experience + salary** — `epicscrapers/naukri-scraper` returns exactly `minimumExperience` / `maximumExperience` / `salaryDetail{minimumSalary,maximumSalary,currency}`; `memo23/naukri-scraper` ($0.60/1k, most-maintained) returns structured experience; `makework36` parses "6-15 Lacs PA" into `salaryMin/Max`. **Structured Indian comp + experience bands is the data nobody else feeds to a holistic scorer.** **[ASSUMPTION]** the India-row salary parsing on the chosen actor works as advertised — Doc 2 flagged `memo23` India-row salary as needing a live test; **a one-run validation is a Phase 1 gate** (§3).
- **LinkedIn:** `harvestapi/linkedin-job-search` ($1/1k, no-cookies → no account-ban risk, structured salary object) as the data-quality pick; `curious_coder/linkedin-jobs-scraper` (97K users, mature) as the volume pick.
- **Indeed:** `misceres/indeed-scraper` (the only Apify-*maintained* job actor) as default.
- **Cost reality (verified, Doc 2 §3):** the **$5/mo free Apify credit (no card)** covers ~3,250 blended results/month ≈ one full 3-platform search every other day. **Single-platform Naukri at ~3 searches/day stays inside free credits ($4.05/mo).** A daily all-platform habit (~$10/mo) exceeds it. **Design the default to be free-tier-friendly:** Naukri-first, cap `limit`, make LinkedIn/Indeed opt-in. Avoid rental actors (the $20/mo `curious_coder/indeed` rental alone blows the budget).

**Channel A + B feed a common pipeline:** dedup → cheap keyword pre-filter (cut obvious non-matches to save LLM cost) → **holistic LLM scoring (§1.2)** → ranked results with citations. The keyword step is a *cost optimization before* the judgment, not the judgment itself.

### 1.4 Data-contract boundary + local-first  **[DECISION]**

Adopt career-ops's **User-Layer / System-Layer split** ([Doc 1 §1.3](01_career_ops_deep_study.md)) — *"the single most important pattern to copy."* User data (resume, profile, application history, reports, scraped JDs) is **never** auto-modified or auto-uploaded; system logic (prompts, adapters, scripts) is freely updatable. This is what makes "self-updating tool that never clobbers your CV" safe, and it operationalizes the privacy promise. **Everything runs locally; the only network egress is (a) the user's chosen LLM CLI if hosted, and (b) the user's own Apify token to the boards.** A fully-local config (local Ollama CLI + ATS-only scan) makes the tool **100% offline and $0**.

### Pipeline at a glance

```
                 ┌─────────────────────────────────────────────┐
   resume.md ───▶│  PROFILE (user layer: archetypes, comp,      │
   profile.yml   │  location, notice period — never auto-edited)│
                 └───────────────────┬─────────────────────────┘
                                     │
   ┌─────────────────────────────────┴──────────────────────────┐
   │ DISCOVERY                                                    │
   │  A) zero-token public-ATS scan (India tenants) — free       │
   │  B) Apify (user token): Naukri[structured] + LinkedIn+Indeed │
   └─────────────────────────────────┬──────────────────────────┘
                                     ▼
                    dedup → cheap keyword pre-filter (cost cut)
                                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ SCORING — markdown rubric, holistic LLM judgment, NO formula  │
   │  driven via user's chosen CLI headless flag (default-less)    │
   │  6 dims · 1.0–5.0 · 4.0 apply line · cite CV lines + JD reqs   │
   └─────────────────────────────────┬────────────────────────────┘
                                     ▼
            ranked results + per-score citations + legitimacy flag
                                     ▼
              feedback (user corrects → profile files updated)
```

---

## 2. What we BORROW vs what we ADD

| | **Borrow from career-ops** (reimplement in our own code/words — see §5) | **Add / change for India** |
|---|---|---|
| **Scoring** | 6-dimension holistic rubric; 1.0–5.0; 4.0 apply line; **no closed-form math**; mandatory CV-line + JD-requirement citations | India archetypes; **CTC/LPA/in-hand/notice/bond** comp model; India ghost-job (GLS-style) signals |
| **Discovery** | Zero-token public-ATS **plugin-provider architecture** (one adapter per source) | India ATS tenants + **Apify for Naukri/LinkedIn/Indeed**, with **Naukri structured experience+salary** as the headline differentiator |
| **Safety/Privacy** | User-Layer/System-Layer **data contract**; local-first; data never leaves the machine | A genuinely free, **fully-offline** path (local Ollama CLI + ATS-only) |
| **Ethics** | No spray-and-pray; no auto-apply (never clicks Submit); never invent experience; never modify the user's CV; discourage <4.0 | Keep verbatim-in-spirit; it's also the anti-pattern that sinks the commercial tier (2.1–2.4 Trustpilot, Doc 4) |
| **Feedback** | File-based "learn after every eval": user correction → rewrite profile files; Story-Bank accumulation | Same mechanism; tune to India archetypes/comp |
| **UX** | YAML profile + `cv.md` + slash-command modes; ~15-min chat-driven onboarding | **Lower-setup eventually** (Doc 4 shows setup friction is a real barrier); standalone discovery so the user isn't forced to drive every step through a paid CLI |
| **CLI posture** | CLI-agnostic; runs in any agentic CLI | Same, but **decouple discovery from the CLI** so scrape+scorer run standalone (§1.1) |

**Net:** we take career-ops's *judgment philosophy, safety model, and ethics* almost wholesale (they're genuinely good and verified), and we own the *India data layer* and *standalone discovery* that career-ops deliberately doesn't do. The `career-ops-india` fork ([Doc 4 §2](04_competitive_landscape.md)) already validated demand for every India move above — it just never productized them or re-architected around Naukri's structured data. We do both.

---

## 3. Phased roadmap

Each phase has an explicit **exit gate**. Do not start the next phase until the gate passes.

### Phase 0 — Architecture
**Goal:** lock the skeleton so later phases don't churn.
- Define the User-Layer/System-Layer file map (§1.4) and the on-disk profile/resume schema.
- Define the **CLI adapter interface**: detect installed CLIs; one adapter per headless flag (§1.1); a `score(prompt) → structured JSON` contract. Ship at least the local-capable set (Codex `--oss`, Qwen, OpenCode, Aider) + Claude Code first.
- Define the **discovery adapter interface** (Channel A providers + Channel B Apify actors behind one `fetch(query) → normalized JobPosting[]`).
- Define the **normalized `JobPosting` schema** — the union that holds Naukri's structured `minimumExperience/maximumExperience/salaryDetail`, LinkedIn's `seniorityLevel`, and ATS prose, so the scorer sees one shape.
- **Exit gate:** a written interface spec for CLI-adapter, discovery-adapter, and JobPosting; agreement that scoring is holistic-LLM (not weighted blend).

### Phase 1 — Discovery
**Goal:** reliably pull real Indian jobs into the normalized schema, free-tier-first.
- Implement Channel A (India ATS scan) and Channel B (Apify: **Naukri primary**, LinkedIn/Indeed opt-in).
- **Validate the Naukri structured-data assumption with a live run** (Doc 2's flagged risk): confirm the chosen actor returns usable India-row experience **and** salary numbers. If `memo23` India salary is prose-only, switch to `epicscrapers` (`salaryDetail`) or `makework36`. Keep a primary + one fallback actor (all are low-adoption community actors — resilience risk is real).
- Implement dedup + the cheap keyword pre-filter.
- **Exit gate:** one command returns ≥1 page of deduped, normalized Indian jobs (Naukri + ≥1 ATS source) with structured experience/comp populated, at **$0–$5/mo** for the target usage; Naukri structured-salary confirmed or fallback actor chosen.

### Phase 2 — Scoring  ⟵ **MVP GATE**
**Goal:** the rubric scorer produces trustworthy ranked results on a real resume.
- Implement the markdown rubric (6 dims, 1.0–5.0, 4.0 line, citations) as system prompts; drive via the CLI adapter; parse structured output.
- India comp/seniority logic: use Naukri's structured experience bands to enforce seniority correctness; use archetypes to enforce function correctness.
- Tune against the **owner's real resume** on real pulled jobs.
- **★ Exit gate (the single non-negotiable, see §4):** on the owner's real resume, the **top 10 ranked results contain ZERO wrong-seniority and ZERO wrong-function matches.** Scores carry citations to specific CV lines + JD requirements. If this fails, iterate here — do **not** proceed to feedback/UX. This gate is the whole product.

### Phase 3 — Feedback
**Goal:** the tool improves from user corrections without statistical ML.
- File-based learning (career-ops model): when the user marks a result wrong (wrong seniority/function/comp), the agent updates the profile/archetype files so future runs improve.
- Record actions (interested / not / applied) to local storage for ranking signal — reuse the *idea* of the current `metrics_db`/`feedback` loop, but feeding the holistic scorer's context, not a weighted formula.
- **Exit gate:** a correction visibly changes subsequent rankings; no user data leaves the machine in the process.

### Phase 4 — Deferred (explicitly NOT in MVP)
Pulled out so they don't creep into the gate:
- ATS-optimized **PDF/CV tailoring** per posting (career-ops's `pdf`/`latex` modes; Playwright).
- **Cover-letter / application-answer drafting** (career-ops's `apply` mode — drafts only, never submits).
- **Web UI** (the current Flask front-end). MVP is CLI/file-driven.
- Interview-prep Story-Bank, deep company research, intern/fresher mode (PPO probability, city-wise stipends — a uniquely Indian, uniquely-career-ops-india feature worth doing later).
- **Auto-apply: never.** Out of scope permanently by design and ethics (§2, Doc 4's Trustpilot evidence).

---

## 4. Assumptions & risks

Kept explicit so we don't quietly reverse a decision when something shifts.

### Verified (high confidence — cited in Docs 1–4)
- career-ops is **MIT**, repo `santifer/career-ops`; its philosophy (no closed-form math, mandatory citations, 6 dims, 4.0 line, data contract, anti-features) is read from the actual repo/site.
- Apify's **$5/mo free, no-card** plan; the `run-sync-get-dataset-items` endpoint + Bearer auth; **structured Naukri actors exist** (`epicscrapers` returns `minimumExperience/maximumExperience/salaryDetail`).
- Every major CLI has a **headless flag**; **Codex/Qwen/OpenCode/Aider support local Ollama**.
- The **four free-tier shifts** (Qwen, Copilot, Anthropic Jun 15, Gemini Jun 18) — all confirmed against official sources.
- The **market gap**: no tool combines India-structured-data + holistic-LLM + CLI-agnostic + local/free + no-spray. Closest is a 10-star fork (`career-ops-india`).

### Assumed / unverified (must validate; do not build deep on these)
- **[ASSUMPTION]** The chosen Naukri actor returns usable **India-row salary numbers**, not just experience. *Doc 2 flagged `memo23` India salary as Gulf-only-confirmed.* → **Validate in Phase 1 with a live run** before relying on Naukri comp scoring.
- **[ASSUMPTION]** Apify per-result prices **bundle platform usage** (the cost model assumes it). → Confirm per actor before quoting users a monthly cost.
- **[ASSUMPTION]** Low-adoption community Naukri actors stay **maintained** against Naukri site changes. → Mitigate with a primary + fallback actor and a health check.
- **[ASSUMPTION]** Amazon Q and Antigravity headless one-shot flags exist for scripting. *Doc 3 could not verify either.* → Don't ship those adapters until confirmed; they're not needed for MVP.
- **[ASSUMPTION]** Local-model scoring quality is *good enough* to pass the Phase-2 gate. → Test a local Ollama model (via Codex `--oss`/Qwen/OpenCode/Aider) against the gate early; if it can't hold seniority/function correctness, the free-offline story is "best-effort" and quality users need a hosted CLI. **Be honest about this in docs.**

### What could change (and our hedge)
- **Free tiers will keep shifting** (four moves in two months). **Hedge: CLI-agnostic default-less design** (§1.1) — any single vendor's move is survivable.
- **Gemini CLI free access ends Jun 18 2026** (~9 days out). **Hedge:** don't make Gemini a default or a tutorial assumption; treat its free tier as already gone.
- **Apify actor prices/availability drift.** **Hedge:** BYO-token (cost is the user's, transparently), primary+fallback actors, free-tier-friendly defaults (Naukri-first, capped limits).
- **Scraping legality** (LinkedIn ToS, India DPDP Act 2023 — *not researched for Naukri specifically*, Doc 2). **Hedge:** BYO-token shifts first-line liability to the user; data minimization (scrape only matching fields, drop recruiter PII); a clear ToS-responsibility disclaimer; prefer no-cookies LinkedIn actor; lean on the free public-ATS channel where possible. **Open item: dedicated India-law review before any public launch that touches Naukri.**

### The single non-negotiable success criterion
> **On the owner's real resume, the top 10 results contain zero wrong-seniority and zero wrong-function matches, each score justified by citations to specific CV lines and JD requirements.**

This is the Phase-2 gate and the reason the product exists (it's the exact failure mode of keyword/black-box scorers in Doc 4). If a feature doesn't serve this, it's Phase 4 or later. If we ever have to choose between breadth and this, this wins.

---

## 5. Attribution & licensing plan (MIT-clean)

From the verified license analysis ([Doc 1 §7](01_career_ops_deep_study.md)):

- **career-ops is MIT.** MIT only obligates us to carry the copyright + permission notice **if we copy their code or a substantial portion verbatim.** **Ideas, patterns, the rubric concept, the A–G structure, the data-contract pattern, the zero-token-ATS approach are NOT copyrightable** — free to reimplement with no obligation.
- **The clean path** [DECISION]:
  1. **Reimplement every pattern from scratch** in our own words/code. Do **not** paste their `modes/*.md`, `*.mjs`, or templates. (This keeps us entirely clear of the MIT notice obligation.)
  2. **Copy no files verbatim.** If we ever lift a snippet, carry the MIT notice + "© 2026 Santiago Fernández de Valderrama" with it — cleaner to just not.
  3. **Credit openly** in our README/docs: e.g. *"Scoring philosophy and data-contract pattern inspired by [career-ops](https://github.com/santifer/career-ops) (MIT). Discovery for Indian boards uses [Apify](https://apify.com)."* Courteous and accurate; zero legal obligation.
  4. **Do not name the product "career-ops"** or anything confusingly similar — the **name is trademark-restricted separately from the MIT code** (career-ops has a `TRADEMARK.md`). Pick our own name.
  5. Ship our own LICENSE for our own original code.
- **Apify:** credited as the discovery data layer; users bring their own token and agree to Apify's ToS directly. Credit the specific actor authors (e.g. `epicscrapers`, `memo23`, `harvestapi`, `misceres`) in docs where we recommend them.
- **`career-ops-india` (MIT):** if we adopt any of its *specific* India moves closely (GLS signal set, intern mode), credit it too — same clean-reimplementation rule.

**Result:** we stand openly on good prior art, owe nothing legally (no verbatim copying), and avoid both the MIT notice condition and the trademark.

---

## 6. Cross-references

- Architecture, rubric, data contract, anti-features, license → [01_career_ops_deep_study.md](01_career_ops_deep_study.md)
- Apify API, actors, Naukri structured fields, cost model, ToS → [02_apify_discovery_study.md](02_apify_discovery_study.md)
- CLI headless flags, free-tier shifts, local-model support → [03_cli_and_api_economics.md](03_cli_and_api_economics.md)
- Competitive tools, the market gap, India platforms → [04_competitive_landscape.md](04_competitive_landscape.md)

> **Standing caveat:** all four source docs are a **2026-06-09 snapshot** with explicit UNVERIFIED sections. Before acting on a number (Apify price, free-tier limit, actor schema, star count), re-check it against the live source. The volatility is the point — it's why the architecture is default-less and BYO-token.
</content>
</invoke>
