# career-ops — Deep Study (Permanent Reference)

> **Purpose:** Reference/inspiration study for a ground-up rebuild of an India-focused, CLI-agnostic AI job-search tool. We are **studying** `career-ops`, **not** forking or copying it. Every fact below was checked against a live source on **2026-06-09**. Anything that could not be verified is listed in the final section.
>
> **Canonical target (verified):** repo `santifer/career-ops`, default branch `main`, MIT license, homepage `career-ops.org`, ~51,300 stars, created 2026-04-04, last pushed 2026-06-09. The other GitHub results (`BobbyWang0120/career-ops`, `vrk7/career-ops`, `AKCodez/career-ops`, `ymys/career-ops-claude`) are forks with the identical description and are **not** canonical.

---

## Sources verified (every URL actually fetched)

**Repo files (read via `gh api repos/santifer/career-ops/contents/<path>`, base64-decoded — not cloned):**

| Source | What it gave us |
|---|---|
| `gh api repos/santifer/career-ops` (metadata) | Confirmed owner/name `santifer/career-ops`, default branch `main`, SPDX license `MIT`, homepage `https://career-ops.org`, 51,300 stars, created `2026-04-04`, pushed `2026-06-09` |
| `gh api .../git/trees/main?recursive=1` | Full file tree (≈200 files). Confirmed actual `modes/` contents, `providers/` contents, AGENTS.md, DATA_CONTRACT.md, LICENSE, etc. |
| `AGENTS.md` | Canonical agent instructions; data contract summary; onboarding flow; mode routing table; ethical-use rules; offer-verification (Playwright) mandate; batch/TSV rules; references the "open agent skill standard" at agentskills.io |
| `DATA_CONTRACT.md` | Exact User-Layer vs System-Layer file lists and "The Rule" |
| `modes/_shared.md` | The scoring system (6 dimensions, score interpretation), Block-G legitimacy tiers/signals, archetype detection table, global NEVER/ALWAYS rules, tools table, writing-style + ATS rules |
| `modes/oferta.md` | The full A–G evaluation flow (Step 0 archetype + Blocks A–G), report format, tracker recording |
| `README.md` | Product framing, "NOT spray-and-pray", 4.0/5 threshold, features table, quick start, slash commands, portal list, disclaimer, MIT + trademark |
| `scan.mjs` (head, ~250 lines) | Zero-token scanner architecture: plugin providers, HTTP-only, dedup logic, title/location filters |
| `providers/greenhouse.mjs` (+ ashby/lever/recruitee/smartrecruiters/workable/local-parser id+endpoint lines) | Confirmed which public ATS APIs are hit; host allowlists; SSRF guards |
| `LICENSE` | Verbatim MIT text, copyright "© 2026 Santiago Fernández de Valderrama" |
| `.claude/skills/career-ops/SKILL.md` | Router/slash-command definition; full mode-routing table; context-loading rules; subagent delegation |
| `config/profile.example.yml` | The YAML profile schema (candidate, target_roles/archetypes, narrative, compensation, location, cv, auto_pdf_score_threshold) |
| `modes/scan.md` (head) | Scanner is in Spanish ("Modo: scan"); 4-tier discovery (local parser → Playwright → API → WebSearch `site:` queries) |
| `templates/portals.example.yml` (grep) | Ships 45+ companies / 19 queries; contains some `site:linkedin.com/jobs` WebSearch queries (Turkey section) |
| `docs/ARCHITECTURE.md` (grep) | Confirms Single-Eval / Portal-Scan / Batch top-level architecture |

**Live website (fetched via WebFetch):**

| URL | What it gave us |
|---|---|
| `https://career-ops.org/` | "150+ company portals. Zero manual searching." marketing claim; Greenhouse/Ashby/Lever only; no mention of LinkedIn/Indeed/Naukri |
| `https://career-ops.org/methodology` | Published 6-dimension rubric + definitions; 1.0–5.0 scale; **"4.0 is the apply / don't-apply line"**; **"There is no weighted-average formula in the code."**; citations-mandatory statement; A–G block table |
| `https://career-ops.org/docs/introduction/what-is-career-ops` | "set of slash commands and prompt files inside whichever AI coding CLI you already trust"; anti-features (no auto-apply, no CV rewriting, no data overwriting); ~15-minute setup; YAML profile + cv.md |
| `https://career-ops.org/blog/why-career-ops` | Anti-features rationale in the author's words (not auto-apply / not hosted / not a LinkedIn scraper); "the goal is fewer applications, not more"; the 9%-of-740 data point |
| `https://agentskills.io` | Definition of the Open Agent Skill standard (SKILL.md folder format, progressive disclosure, originally by Anthropic, broad client adoption) |

**Web searches run:** confirmed canonical repo + forks; confirmed "below 4.0" threshold; located anti-features/blog pages.

> **Note on a primary-source inconsistency:** The repo's own docs disagree with each other in three places. These are flagged inline and consolidated in §2 and the final section. They are real (verified in the live files), not transcription errors on our part.

---

## 1. Architecture

### 1.1 It runs as markdown prompt files inside *any* CLI

career-ops is **not** an application with a runtime engine. It is a directory of **markdown instruction files** (`modes/*.md`) plus a thin **router skill** (`SKILL.md` / `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`) that any agentic coding CLI loads as context. The CLI's own LLM does all the reasoning; the repo supplies *structure, rubrics, and rules*.

From the website (`what-is-career-ops`): the tool operates as *"a set of slash commands and prompt files inside whichever AI coding CLI you already trust: Claude Code, Codex, OpenCode, Gemini CLI, Qwen CLI, or GitHub Copilot."* It *"supplies structure and rubrics while the AI model handles reasoning… you are not locked into one provider's roadmap or pricing."*

Supporting `*.mjs` Node scripts and a Go TUI dashboard exist for the *deterministic* parts (zero-token portal scanning, PDF generation, tracker merge/dedup, liveness checks), but the **evaluation intelligence lives entirely in the markdown prompts**.

**Actual `modes/` directory contents (verified from the tree) and what each does:**

Top-level English modes (the canonical set):

| File | Purpose (from AGENTS.md routing + DATA_CONTRACT) |
|---|---|
| `modes/_shared.md` | **System context** loaded before most modes: scoring system, Block-G legitimacy, archetype table, global NEVER/ALWAYS rules, tools, writing-style + ATS rules |
| `modes/_profile.template.md` | Template for the **user's** customization file. Copied to `modes/_profile.md` (User Layer) on first run; holds archetypes/narrative/negotiation/proof-points/writing-style. Never auto-updated. |
| `modes/oferta.md` | **Single offer evaluation** — the full A–G flow (Spanish filename; "oferta" = offer) |
| `modes/ofertas.md` | **Compare & rank** multiple offers |
| `modes/auto-pipeline.md` | Paste-a-URL → evaluate + report + PDF + tracker, end to end |
| `modes/pipeline.md` | Process pending URLs from the inbox `data/pipeline.md` |
| `modes/scan.md` | **Portal scanner** instructions (4-tier discovery; Spanish) |
| `modes/batch.md` | Batch-process many offers with parallel headless workers |
| `modes/apply.md` | Live application assistant — reads a form, drafts answers (never submits) |
| `modes/contacto.md` | LinkedIn outreach: find contacts + draft message |
| `modes/deep.md` | Deep company research prompt |
| `modes/interview-prep.md` | Company-specific interview-prep doc generation |
| `modes/pdf.md` | ATS-optimized CV PDF generation (Playwright → HTML → PDF) |
| `modes/latex.md` | LaTeX/Overleaf CV path (alternative to HTML) |
| `modes/training.md` | Evaluate a course/cert against the user's North Star |
| `modes/project.md` | Evaluate a portfolio-project idea |
| `modes/tracker.md` | Application-status overview |
| `modes/patterns.md` | Analyze rejection patterns and improve targeting |
| `modes/followup.md` | Follow-up cadence: flag overdue, generate drafts |
| `modes/update.md` | Update the system files (diff preview + compat check) |

Localized mode sets (each a subset — typically `_shared` + evaluation + apply + pipeline): `modes/de/` (German/DACH), `modes/fr/` (French), `modes/ja/` (Japanese), `modes/pt/` (Portuguese), `modes/ru/` (Russian), `modes/tr/` (Turkish), `modes/ua/` (Ukrainian). Each has its own `README.md`.

> **Inconsistency #1 (verified):** The README's headline and the GitHub repo description say **"14 skill modes."** The actual `SKILL.md` router table and the top-level `modes/` directory list **18–19** English modes (the 19 above, of which `_shared`/`_profile` are infra, leaving ~17 user-facing). "14" is stale marketing copy.

### 1.2 AGENTS.md and the "Open Agent Skill Standard"

**AGENTS.md** is the **canonical, CLI-agnostic agent instruction file**. `CLAUDE.md` is described in the repo as a thin "wrapper that imports AGENTS.md"; `GEMINI.md` plays the same role for Gemini CLI. AGENTS.md opens by stating the system *"Runs on any AI coding CLI that follows the [open agent skill standard](https://agentskills.io) (Claude Code, Codex, Gemini, OpenCode, Qwen, Copilot, Kimi)."*

What AGENTS.md actually contains (verified, in order):
- **Origin** — built by santifer to "evaluate 740+ job offers, generate 100+ tailored CVs, and land a Head of Applied AI role"; designed to be customized ("you (AI Agent) can edit the user's files").
- **Data Contract (CRITICAL)** — the User-Layer / System-Layer split (full list in DATA_CONTRACT.md) and **THE RULE**: customizations always go to `modes/_profile.md` or `config/profile.yml`, never to `modes/_shared.md`.
- **Update Check** — run `node update-system.mjs check` silently on first message; parse JSON status; never touch user data on update; `apply`/`dismiss`/`rollback` subcommands.
- **What is career-ops + Main Files table** — `data/applications.md`, `data/pipeline.md`, `data/scan-history.tsv`, `portals.yml`, templates, `scan.mjs` ("Zero-token portal scanner — hits Greenhouse/Ashby/Lever APIs directly, zero LLM cost"), liveness scripts, `reports/` ("Blocks A-F + G (Posting Legitimacy)").
- **First Run — Onboarding** — silent checks for `cv.md`, `config/profile.yml`, `modes/_profile.md`, `portals.yml`; if any missing, enter onboarding (6 steps: CV → profile → portals → tracker → "get to know the user" → ready). "Before doing ANYTHING else, check if the system is set up."
- **Personalization** — common customization requests mapped to which file to edit.
- **Language Modes** — when to switch to de/fr/ja/tr; explicit user preference > JD-language detection.
- **Skill Modes routing table** — user intent → mode.
- **CV Source of Truth** — `cv.md` canonical; `article-digest.md` optional; **"NEVER hardcode metrics — read them from these files at evaluation time."**
- **Ethical Use — CRITICAL** — "designed for quality, not quantity"; never auto-submit; discourage <4.0; quality over speed; respect recruiters' time.
- **Offer Verification — MANDATORY** — *"NEVER trust WebSearch/WebFetch to verify if an offer is still active. ALWAYS use Playwright"* (navigate → snapshot → only footer/navbar = closed). Batch headless mode falls back to WebFetch + marks report "unconfirmed (batch mode)".
- **CI/CD, Community/Governance, Headless/Batch command table, Stack & conventions, TSV tracker-additions format, Pipeline Integrity rules, Canonical States.**

**The Open Agent Skill standard (agentskills.io), verified:** tagline *"A standardized way to give AI agents new capabilities and expertise."* A *skill* is a folder containing a `SKILL.md` file (metadata `name` + `description` at minimum, plus instructions), optionally bundling `scripts/`, `references/`, `assets/`. Agents load skills via **progressive disclosure** in three stages — **Discovery** (name+description only at startup), **Activation** (read full SKILL.md when a task matches), **Execution** (follow instructions, optionally run bundled code). *"The Agent Skills format was originally developed by Anthropic, released as an open standard, and has been adopted by a growing number of agent products"* (Claude Code, Codex, Gemini CLI, OpenCode, Cursor, Copilot/VS Code, Goose, and dozens more shown in the client carousel). This is why career-ops ships parallel skill dirs: `.claude/skills/`, `.agents/skills/`, `.qwen/skills/`.

### 1.3 DATA_CONTRACT.md — the system-code vs user-data boundary

The contract defines exactly two layers and one rule.

**User Layer (NEVER auto-updated — personal data + work product):**
`cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md`, `interview-prep/story-bank.md`, `portals.yml`, `data/applications.md`, `data/pipeline.md`, `data/scan-history.tsv`, `data/follow-ups.md`, `writing-samples/*` (except its README), `reports/*`, `output/*`, `jds/*`.

**System Layer (safe to auto-update — logic/scripts/templates/instructions):**
`modes/_shared.md`, every `modes/*.md` evaluation file, all localized `modes/<lang>/*`, `CLAUDE.md`, `AGENTS.md`, all `*.mjs` scripts, `batch/batch-prompt.md`, `batch/batch-runner.sh`, `dashboard/*`, `templates/*`, `fonts/*`, `.claude/skills/*`, `docs/*`, `VERSION`, `DATA_CONTRACT.md`, `writing-samples/README.md`.

**The Rule (verbatim):**
> "If a file is in the User Layer, no update process may read, modify, or delete it."
> "If a file is in the System Layer, it can be safely replaced with the latest version from the upstream repo."

The boundary is what makes the "self-updating, self-customizing" model safe: `update-system.mjs` can pull new system logic without ever clobbering the user's CV, profile, tracker, or reports. **This is the single most important pattern to copy for our rebuild** (in our own words/code).

---

## 2. The full scoring rubric

### 2.1 The 6 dimensions (exact names + definitions)

From `modes/_shared.md` ("Scoring System") and the published `career-ops.org/methodology`:

| Dimension (as written) | What it measures (verbatim / near-verbatim) |
|---|---|
| **Match con CV** ("match") | "Skills, experience, proof points alignment" — LLM compares JD requirements to CV + article-digest |
| **North Star alignment** ("north-star alignment") | "How well the role fits the user's target archetypes (from _profile.md)" |
| **Comp** | "Salary vs market (5=top quartile, 1=well below)" — web search across Glassdoor, Levels.fyi, Blind |
| **Cultural signals** | "Company culture, growth, stability, remote policy" — qualitative LLM judgement |
| **Red flags** | "Blockers, warnings (negative adjustments)" — negative-only, surfaced even when the rest is high |
| **Global** | "Weighted average of above" (per `_shared.md`) / "Aggregate fit… the score that drives the apply / don't recommendation… LLM-implicit weighting" (per methodology page) |

> **Inconsistency #2 (verified, important):** `_shared.md` literally labels **Global** as the *"Weighted average of above."* The public methodology page **contradicts** this: *"There is no weighted-average formula in the code. The global score is the LLM's judgement of overall fit, given the rubric and the sub-dimensions."* The prose ("weighted average") is a loose description; the **operative truth** is the methodology statement — there is no arithmetic mean in code. For our rebuild, treat "weighted average" as a *mental model*, not an implementation.

Note the dimension labels are partly Spanish ("Match con CV"), reflecting the project's origin. The six map cleanly to: **match, north-star, comp, cultural signals, red flags, global**.

### 2.2 The 1.0–5.0 scale and the 4.0 apply / don't-apply threshold

Scale and interpretation (from `_shared.md`, mirrored on the methodology page):

| Score | Recommendation (verbatim) |
|---|---|
| **4.5+** | "Strong match, recommend applying immediately" |
| **4.0–4.4** | "Good match, worth applying" |
| **3.5–3.9** | "Decent but not ideal, apply only if specific reason" |
| **Below 3.5** | "Recommend against applying" |

**The threshold (verbatim, methodology page):** *"4.0 is the apply / don't-apply line."* The README states it as: *"The system strongly recommends against applying to anything scoring below 4.0/5."* AGENTS.md's Ethical-Use section enforces: *"If a score is below 4.0/5, explicitly recommend against applying."*

> **Inconsistency #3 (verified):** There are effectively **two thresholds** in the materials. The **headline/canonical** threshold is **4.0** (README, AGENTS.md, methodology "apply/don't-apply line"). But the **score-interpretation table** (in both `_shared.md` and the methodology page) only says "Recommend against applying" at **Below 3.5**, leaving 3.5–3.9 as "apply only if specific reason." So: hard apply line = **4.0**; hard *don't-bother* line = **3.5**; 3.5–3.9 is a discretionary band. Additionally, the **auto-PDF gate** is a *separate* number: `config/profile.example.yml` documents `auto_pdf_score_threshold` defaulting to **3.0** (PDFs auto-generate only at/above it). Don't conflate the apply threshold (4.0) with the PDF-generation gate (3.0).

### 2.3 Philosophy: no closed-form math, LLM holistic judgment, mandatory citations

This is the philosophical core to internalize. **Verbatim from `career-ops.org/methodology`:**

> **"There is no weighted-average formula in the code. The global score is the LLM's judgement of overall fit, given the rubric and the sub-dimensions."**

Three stated rationales:
1. **JD context heterogeneity** — job descriptions vary too much for a fixed formula.
2. **User archetype variation** — the same dimension means different things per user (profile personalization).
3. **Transparency** — *"Pretending closed-form math when the underlying engine is an LLM is dishonest marketing."*

**On mandatory citations (verbatim):**
> **"The judgement is auditable: every score comes with citations to specific CV lines and JD requirements."**

This is reinforced operationally in `_shared.md` ("ALWAYS… Cite exact lines from CV when matching") and in `oferta.md` Block B (each JD requirement mapped to exact CV lines). The website summarizes the whole rubric as *"rubric-guided LLM evaluation across six dimensions… producing a 1.0–5.0 score with citations to specific CV lines and JD requirements."*

**Takeaway for rebuild:** the design bet is *rubric + LLM holistic judgment + forced citations*, **deliberately rejecting** a keyword/weighted-sum scorer. (This is a direct philosophical contrast to our current `hybrid_scorer.py` keyword+Groq weighted blend — worth a conscious decision during the rebuild.)

---

## 3. The Block A–G evaluation flow

Source of truth: `modes/oferta.md` (the A–G flow) + `modes/_shared.md` (shared rules it depends on). The mode header reads: *"When the candidate pastes a job (text or URL), ALWAYS deliver the 7 blocks (A-F evaluation + G legitimacy)."*

### Step 0 — Archetype Detection (precedes all blocks)
Classify the job into one of **6 archetypes** (or a hybrid of 2). This drives which proof points to prioritize (Block B), how to rewrite the summary (Block E), and which STAR stories to prep (Block F). Archetype table (from `_shared.md`):

| Archetype | Key JD signals |
|---|---|
| AI Platform / LLMOps | observability, evals, pipelines, monitoring, reliability |
| Agentic / Automation | agent, HITL, orchestration, workflow, multi-agent |
| Technical AI PM | PRD, roadmap, discovery, stakeholder, product manager |
| AI Solutions Architect | architecture, enterprise, integration, design, systems |
| AI Forward Deployed (FDE) | client-facing, deploy, prototype, fast delivery, field |
| AI Transformation | change management, adoption, enablement, transformation |

> These archetypes are **AI/automation-career specific** (the author's own domain). For our India rebuild they would be re-defined per target market — exactly the kind of thing the `_profile.md` customization model is built to allow.

### Block A — Role Summary
A table with: **Archetype detected · Domain** (platform/agentic/LLMOps/ML/enterprise) **· Function** (build/consult/manage/deploy) **· Seniority · Remote** (full/hybrid/onsite) **· Team size** (if mentioned) **· TL;DR in one sentence.**

### Block B — CV Match
Read `cv.md`. Build a table mapping **each JD requirement → exact lines in the CV.** Adapted per archetype (FDE→delivery speed/client-facing; SA→system design/integrations; PM→discovery/metrics; LLMOps→evals/observability/pipelines; Agentic→multi-agent/HITL/orchestration; Transformation→change management/adoption). Then a **Gaps** section; for each gap answer: (1) hard blocker or nice-to-have? (2) can the candidate show adjacent experience? (3) is there a portfolio project covering it? (4) a concrete mitigation plan (cover-letter phrasing, quick project, etc.).

### Block C — Level & Strategy
1. **Level detected in the JD** vs **candidate's natural level for that archetype.**
2. **"Sell senior without lying" plan** — specific phrases per archetype, achievements to highlight, how to position founder experience as an advantage.
3. **"If they downlevel me" plan** — accept if comp is fair; negotiate a 6-month review; clear promotion criteria.

### Block D — Comp & Demand
Use **WebSearch** for current salaries (Glassdoor, Levels.fyi, Blind), the company's comp reputation, and demand trend. Output a **table with cited sources.** Explicit rule: *"If there is no data, state it instead of inventing."*

### Block E — Customization (Personalisation) Plan
A table: `# | Section | Current status | Proposed change | Why`. Deliver **Top 5 changes to the CV + Top 5 changes to LinkedIn** to maximize match.

### Block F — Interview Plan
**6–10 STAR+R stories** mapped to JD requirements, where **R = Reflection** ("what was learned / what would be done differently — signals seniority; juniors describe what happened, seniors extract lessons"). Table columns: `# | JD Requirement | STAR+R Story | S | T | A | R | Reflection`. **Story Bank:** if `interview-prep/story-bank.md` exists, dedup against it and append new stories — over time building "a reusable bank of 5–10 master stories." Also include 1 recommended case study and red-flag questions + how to answer them ("why did you sell your company?", "do you have direct reports?").

### Block G — Posting Legitimacy
A **separate qualitative assessment** that does **NOT** affect the 1–5 global score. Detects ghost/scam postings. Three tiers: **High Confidence · Proceed with Caution · Suspicious.** Signals analyzed in order: (1) posting freshness + Apply-button state (from Playwright snapshot), (2) description quality (named tech/team/org, realism, scope, salary, boilerplate ratio, internal contradictions), (3) company hiring signals (2–3 WebSearches: layoffs/hiring-freeze, same department?), (4) reposting detection (from `scan-history.tsv`), (5) role market context (qualitative). Edge cases explicitly handled: government/academic (longer timelines normal, 60–90d), evergreen/rolling postings, niche/executive (Staff+/VP/Director stay open months), no-date (default "Proceed with Caution", **never** "Suspicious" without evidence), recruiter-sourced (freshness N/A; active recruiter contact is itself a *positive* signal). **Ethical framing (MANDATORY):** "Present observations, not accusations. Every signal has legitimate explanations. The user decides."

Signal-reliability weighting (from `_shared.md` Block-G table): Posting age = High; Apply-button active = High; Tech specificity = Medium; Requirements realism = Medium; Recent layoff news = Medium; Reposting pattern = Medium; Salary transparency = Low; Role-company fit = Low.

### Post-evaluation (always, after A–G)
1. **Save report** to `reports/{###}-{company-slug}-{YYYY-MM-DD}.md` (3-digit sequential number = max existing + 1). Report header includes `Date / URL / Archetype / Score (X/5) / Legitimacy {tier} / PDF`. Body = blocks A–G, plus an optional **Block H "Draft Application Answers" only if score ≥ 4.5**, plus a "Keywords extracted" list (15–20 JD keywords for ATS).
2. **Record in tracker** `data/applications.md` (number, date, company, role, score 1–5, status `Evaluated`, PDF ❌/✅, root-relative report link). In practice this is written as a **TSV** in `batch/tracker-additions/` and merged by `merge-tracker.mjs` (never edit applications.md directly to *add*; you may edit to *update* an existing row).

### Faithful key quotes
- *"When the candidate pastes a job (text or URL), ALWAYS deliver the 7 blocks (A-F evaluation + G legitimacy)."* (oferta.md)
- *"Read `cv.md`. Create a table with each JD requirement mapped to exact lines in the CV."* (Block B)
- *"If there is no data, state it instead of inventing."* (Block D)
- *"The **Reflection** column captures what was learned or what would be done differently. This signals seniority."* (Block F)
- *"Present observations, not accusations. Every signal has legitimate explanations. The user decides how to weigh them."* (Block G)

---

## 4. Discovery / Scan

### How it works — zero-token, public ATS APIs
The scanner (`scan.mjs`, run via `node scan.mjs` or `npm run scan`) is explicitly **"Zero-token portal scanner"** — *"pure HTTP + JSON,"* *"Zero Claude API tokens."* It uses a **plugin-based provider layer**: files in `providers/*.mjs`, each exporting `{ id, detect(entry), fetch(entry, ctx) }`. Adding a new source = drop a `.mjs` into `providers/`.

**Verified providers and the public endpoints they hit (read from each file):**

| Provider (`id`) | Public endpoint pattern | Notes |
|---|---|---|
| `greenhouse` | `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` | Host allowlist (`boards-api`/`boards`/`job-boards`/`job-boards.eu`.greenhouse.io); `redirect:'error'` to block SSRF |
| `ashby` | `https://api.ashbyhq.com/posting-api/job-board/<slug>?includeCompensation=true` | Auto-detects from `jobs.ashbyhq.com/<slug>` |
| `lever` | `https://api.lever.co/v0/postings/<slug>` | Auto-detects from `jobs.lever.co/<slug>` |
| `recruitee` | `https://<slug>.recruitee.com/api/offers/` | Per-tenant offers API; URL validated to recruitee.com |
| `smartrecruiters` | `https://api.smartrecruiters.com/v1/companies/<slug>/postings?...&status=PUBLIC` | Paginated, cap 50 pages |
| `workable` | `https://apply.workable.com/<slug>/jobs.md` | Public **markdown** feed |
| `local-parser` | (no network) runs a user-supplied local script | For SSR/HTML career pages; JSON array or `{jobs/results}` |

Discovery is **additive, multi-tier** (from `modes/scan.md`, which is written in Spanish): **Tier 0** local parser → **Tier 1** Playwright (visual scrape) → **Tier 2** public API/JSON feed → **Tier 3** broad WebSearch `site:` queries to discover *new* companies not yet tracked. Results across tiers are merged and deduplicated (dedup uses `data/scan-history.tsv` + `pipeline.md` URLs + `applications.md` company::role pairs). A `--verify` flag launches Playwright after the API pass to drop expired postings before they reach `pipeline.md` (some ATS feeds keep stale closed roles).

**The "150+ portals" claim — precise truth:**
- The **website** (career-ops.org) markets: *"150+ company portals. Zero manual searching."* and *"Pre-configured scrapers check 150+ career pages across Greenhouse, Ashby and Lever on demand."*
- The **shipped repo** template (`templates/portals.example.yml`, copied to `portals.yml`) actually contains **"45+ companies pre-configured"** + **"19 search queries"** (README). So 150+ is an aspirational/marketing figure (and/or what the author's own private `portals.yml` reached); the out-of-box example is ~45 companies. **Flag this gap; don't repeat "150+" as a shipped fact.**

### Confirming: NO LinkedIn scraping, NO Indeed, NO Naukri — with one nuance
- **Providers:** there is **no LinkedIn, Indeed, or Naukri provider.** The only `providers/*.mjs` are the seven ATS sources above (Greenhouse, Ashby, Lever, Recruitee, SmartRecruiters, Workable, local-parser). Discovery via *scraping/API* is therefore ATS-only.
- **Author's stated position (`why-career-ops`):** career-ops is *"Not a LinkedIn scraper… the project avoids LinkedIn scraping because it violates terms of service and exposes users to account suspension."*
- **Website:** makes *no mention* of LinkedIn/Indeed/Naukri in its discovery pitch — exclusively Greenhouse/Ashby/Lever company career pages.
- **Indeed / Naukri:** **zero** references anywhere in the repo or site (verified by grep + fetch). Not supported, not mentioned.
- **NUANCE on LinkedIn (verified):** `templates/portals.example.yml` *does* contain a few **WebSearch `site:linkedin.com/jobs` discovery queries** (in the Turkey-specific section, e.g. `site:linkedin.com/jobs "Software Engineer"… Turkey`). These are *search-engine queries that surface LinkedIn job URLs*, **not** scraping of LinkedIn's API/DOM. The `contacto` mode also drafts LinkedIn *outreach messages*. So the accurate statement is: **career-ops does not scrape LinkedIn (or Indeed/Naukri); it scans public ATS APIs. It does optionally use WebSearch `site:` queries that can return LinkedIn job links, and it helps write LinkedIn outreach.**

> **Relevance to our India rebuild:** career-ops would scan *nothing India-specific* out of the box — Naukri, Foundit/Monster India, Instahyre, Cutshort, Wellfound-India, and the bulk of Indian SME postings on Workday/Greenhouse-India are not in its example config. Our differentiator (India-first sources) is wide open. Their **architecture** (zero-token public-ATS provider plugins + optional Playwright verify) is the part worth reimplementing; their **source list** is not India-relevant.

---

## 5. Anti-features

career-ops is explicitly positioned as a **filter, not a firehose.** README: *"This is NOT a spray-and-pray tool. Career-ops is a filter — it helps you find the few offers worth your time out of hundreds."* The anti-features, each with its stated reason (sources: README, AGENTS.md "Ethical Use", `why-career-ops`, `what-is-career-ops`):

| Anti-feature | Stated reason it exists (verbatim / close paraphrase) |
|---|---|
| **No spray-and-pray / no mass applications** | "designed for quality, not quantity… A well-targeted application to 5 companies beats a generic blast to 50." Goal is "fewer applications, not more." |
| **No auto-apply (never clicks Submit/Send/Apply)** | "AI evaluates and recommends, you decide and act. The system never submits an application — you always have the final call." Author: auto-apply at scale "would worsen recruiter pipeline saturation"; "the candidate-side response to an over-saturated system" is to filter down + craft well. |
| **Strongly discourage low-fit (<4.0) applications** | "The user's time and the recruiter's time are both valuable… Respect recruiters' time. Every application a human reads costs someone's attention." |
| **Never invent experience or metrics** | First global NEVER rule. "AI models may hallucinate skills or experience" (disclaimer). "NEVER hardcode metrics — read them from cv.md + article-digest.md at evaluation time." Integrity of the candidate's claims. |
| **Never modify cv.md or portfolio files** | Global NEVER #2 + DATA_CONTRACT User Layer. "your CV, your profile, and your application history are sovereign — career-ops will read them, but it will never silently rewrite or delete what you put there." |
| **Not a resume builder / LinkedIn optimizer** | "you bring the resume you already have, and the system makes sure each version of it is tuned to the job in front of you." (Tailoring ≠ rewriting your source CV.) |
| **No LinkedIn (or other ToS-violating) scraping** | "violates terms of service and exposes users to account suspension." |
| **Not a hosted SaaS service** | "no career-ops.com, no cloud storage, and no plans to change this… operates entirely locally." Privacy: "your data never leaves your machine." |
| **Never share the user's phone number in generated messages** | Global NEVER #4 (privacy hygiene in outreach). |
| **Never recommend comp below market rate** | Global NEVER #5 (protect the candidate's negotiating position). |
| **No PDF without reading the JD first** | Global NEVER #6 (every tailored CV must be grounded in the actual posting). |
| **No corporate-speak / cliché phrases** | Global NEVER #7 + a banned-phrase list ("passionate about", "leveraged", "spearheaded", "synergies", "robust", "seamless", …) — for ATS + human readability. |
| **Never ignore the tracker** | Global NEVER #8 — every evaluated offer gets registered (single source of truth, integrity). |
| **Verify liveness with Playwright, never trust WebSearch/WebFetch for "is it still open?"** | Avoid wasting effort (and the user's credibility) on dead/ghost postings. |

> The throughline: **protect the candidate's integrity, protect the recruiter's attention, protect the user's data.** This ethical posture is reusable verbatim-in-spirit (not text) for our rebuild and aligns with our existing privacy-first ("data never leaves the machine") positioning.

---

## 6. Setup / UX

### The ~15-minute setup
Website (`what-is-career-ops`): setup takes *"about fifteen minutes."* Two install paths (README):
- **Fast:** `npx @santifer/career-ops init` → clones the latest release into `./career-ops` + installs deps → `cd career-ops && claude` (or `gemini`/`codex`/`qwen`/`opencode`).
- **Manual:** `git clone … && npm install && npx playwright install chromium` (Playwright only needed for PDF + liveness).

On first launch the agent runs the **onboarding flow** (AGENTS.md "First Run"): silently checks for `cv.md`, `config/profile.yml`, `modes/_profile.md`, `portals.yml`; if any missing, it *refuses to evaluate* and walks the user through 6 conversational steps — **(1)** CV (paste / LinkedIn URL / describe → it writes `cv.md`), **(2)** profile (name, email, location, target roles, salary → `config/profile.yml`), **(3)** portals (copy the 45+ example, customize keywords), **(4)** tracker (`data/applications.md`), **(5)** "get to know the user" (superpower, what excites/drains, deal-breakers, best achievement, published work → stored in `profile.yml`/`_profile.md`/`article-digest.md`), **(6)** ready. *"Nothing to edit by hand"* — it's all chat-driven.

### The YAML profile (`config/profile.yml`)
Schema (from `config/profile.example.yml`): top-level keys **`candidate`** (full_name, email, phone, location, linkedin, portfolio_url, github, twitter), **`target_roles`** (`primary` list + `archetypes` each with name/level/`fit` ∈ primary|secondary|adjacent), **`narrative`** (headline, exit_story, superpowers[], proof_points[] with name/url/hero_metric, optional dashboard creds), **`compensation`** (target_range, currency, minimum/"walk-away", location_flexibility), **`location`** (country, city, timezone, visa_status), **`cv`** (output_format html|latex, optional `canva_resume_design_id`), and **`auto_pdf_score_threshold`** (default 3.0). This is the **single source of truth for personal data across all modes.**

### cv.md
The canonical CV in markdown (project root). Clean standard sections (Summary, Experience, Projects, Education, Skills). The system **reads** it at evaluation time and **never modifies** it. `article-digest.md` (optional) holds detailed proof points and **takes precedence over cv.md for article/project metrics.**

### Slash commands
One command, many modes (README "Usage"):
```
/career-ops              → show all commands (discovery menu)
/career-ops {paste JD}   → full auto-pipeline (evaluate + PDF + tracker)
/career-ops scan         → scan portals
/career-ops pdf          → generate ATS CV
/career-ops batch        → batch evaluate
/career-ops tracker      → application status
/career-ops apply        → fill forms with AI (drafts only)
/career-ops pipeline     → process pending URLs
/career-ops contacto     → LinkedIn outreach
/career-ops deep         → deep company research
/career-ops training     → evaluate a course/cert
/career-ops project      → evaluate a portfolio project
```
Plus `patterns`, `followup`, `interview-prep`, `ofertas`, `update` (per SKILL.md router). The router (`.claude/skills/career-ops/SKILL.md`) maps `$mode` → mode file, auto-detects "paste a JD/URL with no sub-command" → `auto-pipeline`, and **delegates `scan`/`apply`(Playwright)/`pipeline`(3+ URLs) to a subagent** with `_shared.md` + the mode file injected into its prompt. Gemini CLI exposes the same 15 commands as `.gemini/commands/*.toml`.

### The "interview-first → route → score → learn" feedback loop
The exact phrase "interview-first → route → score → learn" does **not** appear verbatim in any fetched source (flagged below). But the **mechanics it describes are real and verifiable**, and map to this loop:
- **Route** — the `SKILL.md` router classifies intent (`$mode` or auto-detect JD) → dispatches to the right mode/subagent.
- **Score** — `oferta`/`auto-pipeline` run the A–G rubric → 1–5 global + citations → report + tracker row.
- **Learn** — two concrete mechanisms: **(a)** the **Story Bank** (`interview-prep/story-bank.md`) *accumulates STAR+R stories across evaluations* until the user has 5–10 master answers (this is the literal "interview-first" payoff — by the ~20th eval you have a battle-tested answer bank, per `why-career-ops`); **(b)** AGENTS.md's *"After every evaluation, learn"* rule — when the user corrects a score or a missed skill, the agent updates `modes/_profile.md` / `config/profile.yml` / `article-digest.md` so future evals improve. There is **no automated ML feedback loop**; "learning" = the agent rewriting the user's customization files + growing the story bank. (The `why-career-ops` page explicitly says it "does not describe an explicit feedback mechanism where the system learns and improves over time… focuses on single-search optimization" — i.e. "learning" is manual/file-based, not statistical.)

---

## 7. License

**Confirmed: MIT License** (read the actual `LICENSE` file). Copyright line (verbatim): *"Copyright (c) 2026 Santiago Fernández de Valderrama."* Standard MIT permission grant + the standard "as-is, no warranty" clause. The repo's GitHub metadata SPDX field also returns `MIT`.

**Separately:** the **name/brand "career-ops"** is governed by a **Trademark Policy** (`TRADEMARK.md`) — "permissive for community use, reserved for commercial product naming and endorsement." (The *code* is MIT; the *name* is trademark-restricted. These are independent.)

### Exactly what we can / cannot do
**MIT lets us:** use, copy, modify, merge, publish, distribute, sublicense, and sell — including for our own product — **provided** that *"The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software."* I.e. **if we copy any of their code or a substantial portion verbatim, we must ship the MIT notice + their copyright line.** No warranty/liability is provided.

**MIT does not let us / does not require:**
- We **cannot** use the "career-ops" *name/brand* for our product or imply endorsement (that's the trademark policy, not the license).
- **Ideas, patterns, methods, the rubric concept, the A–G structure, the data-contract pattern, the zero-token-ATS approach** are **not copyrightable** — they are **free to reimplement** in our own words and code with **no obligation** (MIT or otherwise). (Crediting is courteous, not required, for clean-room reimplementation.)

### The clean path for our rebuild (recommended)
1. **Reimplement patterns from scratch** — write our own prompts, our own scorer, our own scan layer, in our own words/code. Do **not** paste their `modes/*.md`, `*.mjs`, or templates verbatim.
2. **Copy no files verbatim.** If we ever *do* lift a code snippet or substantial chunk, we must carry the MIT notice + "© 2026 Santiago Fernández de Valderrama" with it — cleaner to just not.
3. **Credit openly** in our README/docs (e.g. "Architecture inspired by career-ops (santifer/career-ops, MIT)") — good citizenship, zero legal obligation, and it's accurate.
4. **Don't name our product "career-ops"** or any confusingly similar mark; don't imply their endorsement.
5. Keep our own LICENSE for our own original code.

This keeps us **100% clear of both the MIT condition (no verbatim copying → no notice obligation) and the trademark policy (different name → no brand conflict)**, while freely standing on the shoulders of their (genuinely good) design patterns.

---

## UNVERIFIED / COULD NOT CONFIRM

1. **The exact phrase "interview-first → route → score → learn"** — not found verbatim in README, AGENTS.md, `_shared.md`, `oferta.md`, `SKILL.md`, or the three website pages fetched. The *underlying mechanics* (router → A–G scoring → Story-Bank accumulation + file-based "learn after every eval") are fully verified; only the catchphrase itself is unconfirmed. It may be the user's own framing or appear in a page/section not fetched.
2. **"150+ portals" as a *shipped* number** — verified only as a **website marketing claim** ("150+ company portals… across Greenhouse, Ashby and Lever"). The shipped `templates/portals.example.yml` is "45+ companies + 19 queries" (README). The 150+ figure could not be confirmed against the actual default config; treat as aspirational, not shipped.
3. **The "Global = weighted average" wording vs "no formula in code"** — both statements are individually verified (one in `_shared.md`, one on the methodology page) and they **conflict**. I could not inspect a scoring *function* in code because the global score is produced by the LLM from the prompt (there is no numeric scorer file). I take "no weighted-average formula in the code" as operative, but I did not exhaustively read every `*.mjs` to *prove the absence* of any scoring arithmetic — I read `scan.mjs` and the providers (no scoring there) and relied on the methodology page's explicit statement.
4. **"14 skill modes" vs ~18–19 actual** — the discrepancy is verified (README/repo-description say 14; the tree + SKILL.md show more). I could not determine which "14" the marketing copy intends (possibly an older release or a curated user-facing subset).
5. **Exact star count / freshness** — 51,300 stars and the 2026-06-09 push timestamp are from the GitHub API at fetch time (2026-06-09); these change continuously.
6. **`agentskills.io` as the literal "Open Agent **Skill** Standard" name** — the site brands itself "Agent Skills" / "a standardized way to give AI agents new capabilities," originally by Anthropic. AGENTS.md calls it the "open agent skill standard" and links there. The precise capitalized proper-noun "Open Agent Skill Standard" is career-ops's phrasing, not a self-applied title I saw on agentskills.io.
7. **Localized-mode parity** — I confirmed the *existence* of de/fr/ja/pt/ru/tr/ua mode dirs and read AGENTS.md's description of de/fr/ja/tr vocabularies. I did **not** open each localized file to verify translation completeness; pt/ru/ua are listed in the tree and DATA_CONTRACT but I did not read their contents.
8. **Whether any provider beyond the 7 read exists at runtime** — I read greenhouse in full and id+endpoint lines for ashby/lever/recruitee/smartrecruiters/workable/local-parser. I did not byte-for-byte read the full body of all six; their endpoints/ids are confirmed but edge-case behavior was not exhaustively reviewed.
