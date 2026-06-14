# 04 — Competitive Landscape

**Purpose:** Permanent reference for the ground-up rebuild of an India-focused, CLI-agnostic AI job-search tool. This document maps the WIDER market — open-source GitHub tools, commercial auto-appliers, ATS/resume scanners, and India-native job platforms — so we know exactly where the opening is.

**Research date:** 9 June 2026
**Method:** Every star count, license, and "what it does" below was pulled from the LIVE GitHub repo page or official product site via WebFetch/WebSearch on the research date. Numbers change daily — treat them as a 9 June 2026 snapshot. Anything not confirmable live is flagged in the final section.

---

## Sources verified (every URL fetched)

GitHub repo pages (live, via WebFetch — stars/license/last-commit read directly):
- https://github.com/santifer/career-ops
- https://github.com/poferraz/career-ops
- https://github.com/santifer/career-ops/forks
- https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk
- https://github.com/vasu-devs/JustHireMe
- https://github.com/itsmedhawal/career-ops-india
- https://github.com/srbhr/Resume-Matcher
- https://github.com/Gsync/jobsync
- https://github.com/Pickle-Pixel/ApplyPilot

Official product sites (live, via WebFetch):
- https://redrob.io/ (homepage)
- https://redrob.io/job-search

Verified via WebSearch result aggregation (product sites + third-party reviews; pricing/traction figures NOT read off a single canonical live page — see UNVERIFIED section):
- LazyApply, Jobscan, LoopCV, Sonara, Massive (usemassive.com), Tal.ai (talplatform.ai), JobHire.AI
- Naukri (Resdex / FastForward / Relevance Score), Instahyre, Cutshort, Apna, Hirect

---

## 1. Open-source AI job-search / job-matching tools (GitHub)

All figures read from the live repo page on 9 June 2026.

| Repo | Stars | Forks | License | Last activity | What it does | Searches/scrapes jobs? | India boards? |
|---|---|---|---|---|---|---|---|
| [santifer/career-ops](https://github.com/santifer/career-ops) | **51.3k** | 10.4k | MIT | v1.8.0, 15 May 2026 | CLI-agnostic skill: evaluate offers (A–F, 6 blocks + legitimacy/Block G), generate tailored ATS CVs, track apps, batch 10+ in parallel | Yes — scans 45+ preconfigured cos across Greenhouse/Ashby/Lever/Workable/Wellfound | **No** |
| [srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher) | **27.3k** | 4.9k | Apache-2.0 | v1.2, 2 Apr 2026 | Upload resume + paste ONE JD → tailored resume, keyword gaps, score, cover letter, PDF. Local (Ollama) or cloud (OpenAI/Anthropic/Gemini/DeepSeek) | **No** — scores against a single pasted JD only; zero aggregation | **No** |
| [feder-cr/Jobs_Applier_AI_Agent_AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk) | **29.9k** | 4.6k | AGPL-3.0 | **ARCHIVED 17 May 2026** (read-only); code last touched ~Nov 2024 | The famous LinkedIn/Easy-Apply auto-applier. AI-tailored mass apply + dynamic resume gen | Yes (LinkedIn-centric) | No |
| [Pickle-Pixel/ApplyPilot](https://github.com/Pickle-Pixel/ApplyPilot) | **1.1k** | 390 | AGPL-3.0 | v0.3.0, 21 Feb 2026 | 6-stage autonomous agent: discover → enrich → score (1–10 vs resume) → tailor → cover letter → **auto-submit** via browser. `pip install applypilot` | Yes — Indeed/LinkedIn/Glassdoor/ZipRecruiter/Google Jobs + 48 Workday + 30+ career sites | No |
| [vasu-devs/JustHireMe](https://github.com/vasu-devs/JustHireMe) | **2.0k** | 316 | AGPL-3.0 | v1.0.42, 28 May 2026 | Local-first Tauri desktop workbench: scrape → quality-gate → rank (deterministic + feedback + optional LLM) → generate resume/cover/outreach PDFs. Local ONNX embeddings (no API key). | Yes — ATS boards, RSS, HN, Reddit, GitHub-style, custom adapters | **No (but India-governed entity)** |
| [Gsync/jobsync](https://github.com/Gsync/jobsync) | **609** | 108 | MIT | v1.1.12, 6 Jun 2026 | Self-hosted (Docker) job-search tracker + AI resume review & job matching. Privacy-first, your DB, no external data sharing | **No** — manual tracker for jobs you already found | No |
| [itsmedhawal/career-ops-india](https://github.com/itsmedhawal/career-ops-india) | **10** | 3 | MIT | (commit date not surfaced; ~106 commits) | Fork of career-ops adapted for India — see §2 | Yes (adds Naukri/iimjobs/Cutshort/Foundit) | **YES** |
| [poferraz/career-ops](https://github.com/poferraz/career-ops) | **7** | 0 | MIT | v1.0.2, 23 Mar 2026 | Coaching skill ("NO SLOP. JUST STRATEGY"): resume/cover/LinkedIn/interview/negotiation. Motivational-Interviewing front-end + anti-slop gate. **NOT a job searcher.** | **No** | No |

### Honourable mentions (surfaced in search, not individually star-verified — see UNVERIFIED)
- **olyaiy/resume-lm** — open-source AI resume *builder* (Next.js). Builder, not searcher.
- **vectornguyen76/resume-ranking**, **haroon-sajid/resume-screening-app** — recruiter-side LLM resume *ranking* (LangChain/LangGraph/Llama), i.e. screening candidates, not finding jobs.
- **Naukri scraper repos** — `pawan941394/Naukri-Web-Scrapper-`, `Hyperion101010/naukri-scraper`, `Rockposedon/WebScraping`, `rajnathsah/naukriscraper` etc. These are bare data-dump scrapers (CSV/Excel of listings), **no scoring, no resume matching, no India-aware ranking**. They prove Naukri *is* scrapeable but offer none of the intelligence layer.

**Read-across:** The two giants (career-ops 51k, Resume-Matcher 27k) are CLI-agnostic / local and high quality — but **neither covers India**. Resume-Matcher's maintainer is Indian, yet the tool has zero job aggregation and zero India boards. ApplyPilot and AIHawk bring real automation but are spray-and-pray and Western. The only India-aware repos are a 10-star fork and a set of dumb scrapers.

---

## 2. career-ops: the original, the forks, and the "poferraz" confusion

**Important correction to the brief's premise.** The brief asked to assess "the poferraz/career-ops fork." Verified live: **poferraz/career-ops is NOT a fork of career-ops.** It is a separate, original 7-star MIT coaching skill ("NO SLOP. JUST STRATEGY") — its README never references santifer/career-ops, and it does not appear anywhere in santifer/career-ops's fork network. It does resume/interview/negotiation coaching; it does **not** search jobs. So it is not a competitor to our rebuild at all — it's a coaching adjacent.

**The real original** is **[santifer/career-ops](https://github.com/santifer/career-ops)** (Santiago) — 51.3k stars, 10.4k forks, MIT, v1.8.0 (15 May 2026). Built by the author to run his own search (assessed 740+ listings, generated 100+ resumes, landed a Head of Applied AI role). CLI-agnostic: Claude Code, Gemini CLI, Codex, OpenCode, Qwen, Copilot. Stack: JS 63% / Go 28% / Shell / HTML. Human-in-the-loop by design — recommends, never auto-submits.

### Notable forks (from the live forks page)

| Fork | Stars | What changed vs original |
|---|---|---|
| [BobbyWang0120/career-ops](https://github.com/BobbyWang0120/career-ops) | ~95 | Most-starred fork (divergence not individually verified) |
| [AKCodez/career-ops](https://github.com/AKCodez/career-ops) | ~35 | Modest fork |
| **[itsmedhawal/career-ops-india](https://github.com/itsmedhawal/career-ops-india)** | ~10 | **India adaptation — see below** |
| ncoprod/career-ops | ~10 | Modest fork |
| kai-is-scaling, akshaykumar94, DottsGit, others | 4–9 | Minor |

### career-ops-india (itsmedhawal) — the closest thing to our concept that exists today
What the fork changed vs the original career-ops (read from the fork README):
- **Archetypes:** 6 Western roles → **7 India archetypes** (AI/ML, GenAI, Data Science, consulting)
- **Compensation model:** USD/EUR → **CTC / LPA, in-hand estimate, bond penalties**
- **Ghost-job detection:** added a **Ghost Likelihood Score (GLS) 0–100** across 9 signals (repost frequency, JD boilerplate ratio, layoff news, …)
- **Boards:** scanner expanded to **Naukri, iimjobs, Cutshort, Foundit, ~40 Indian companies** alongside 73+ global
- **Intern Mode:** new `/career-ops intern` — PPO probability, stipend benchmarks by city
- Invites Hindi contributions.

**Why it doesn't close the gap:** 10 stars, solo, maintenance cadence undocumented, inherits career-ops's reliance on a paid coding-CLI agent doing the scanning, and — critically — it bolts India boards onto a Western evaluation architecture rather than being built around Naukri's structured data (Resdex fields: CTC, notice period, experience bands). It validates the demand and the design moves (CTC-native scoring, ghost detection, intern mode) we should adopt — but it is not a durable product.

---

## 3. Named commercial / hosted tools

> Pricing and traction below come from product pages + third-party reviews aggregated via WebSearch, NOT from a single canonical live pricing page per tool. Figures are directional — see UNVERIFIED.

| Tool | Type | Price (approx, 2026) | What it does well | What it lacks | India | Learn from it |
|---|---|---|---|---|---|---|
| **LazyApply** | Browser-ext auto-applier | $99/yr Basic (15/day) → $999/yr Ultimate (1,500/day) | Lowest entry price; high-volume LinkedIn/Indeed/ZipRecruiter Easy-Apply; saves hours of clicking | Quality/reliability complaints; **Trustpilot ~2.4/5, 56% 1-star**; wrong form submissions, account-flag risk; no free trial; no real matching | Works on Indeed/LinkedIn globally; not India-tuned | Volume without judgment burns trust → our wedge is *fewer, better*, ethical |
| **LoopCV** | Hosted auto-apply | Free tier; €9.99/mo Standard → €29.99/mo Pro (≈₹453+/mo) | Scans 30+ boards daily, matches CV, can auto-submit or review-first; has a free forever tier | Greece/EU-centric; users report huge "matched" vs tiny "applied" gap; **Trustpilot ~3.9/5** | EU-strong, **weak India coverage** | Review-before-apply mode is the right default; "matched ≫ applied" gap is the #1 trust-killer to avoid |
| **Sonara** | Hosted AI apply | (peak ~$49/mo, ~10 apps/wk) | — | **Effectively dead in 2026** — site 403/timeouts, no updates, no data export, no shutdown notice | No | Cautionary tale: closed SaaS = users stranded; **our local/self-hosted model is the antidote** |
| **Massive (usemassive.com)** | AI co-pilot apply | Free tier + paid; 3-mo min commitment | Profile → AI surfaces matches → guided tailor & apply | "Co-pilot not autopilot"; **Trustpilot ~2.1/5**; false visa-required flags; slow UI; web-only | Not India-tuned | Honest "co-pilot" framing is more defensible than autopilot hype |
| **Jobscan** | ATS resume scanner | Free (5 scans/mo); ~$49.95/mo; ~$29.98/mo quarterly | Best-in-class ATS match report (75%+ target), 95%+ parser accuracy (Taleo/Workday/Greenhouse), ATS detection, one-click GPT-4 optimize | **Optimizes for the bot, not the human**; can't tell must-have vs nice-to-have; no job search/aggregation | Generic ATS; Naukri/Resdex not a first-class target | Match-rate UX is loved; but keyword-matching ≠ holistic fit → our LLM-holistic scoring is the differentiator |
| **Tal.ai** (talplatform.ai) | Recruiter-side talent intel | 14-day free trial | Semantic NL search over 800M+ profiles, 41 ATS / 21 CRM syncs | **Recruiter tool, not a job-seeker tool** — wrong side of the market | Global | NL/semantic search over a structured talent graph is the inverse of what we do for seekers |
| **JobHire.AI** | Hosted bulk apply | from ~$19/week (up to 100 apps) | Bulk apply + resume optimization | Spray model; closed SaaS | Not India-tuned | Same spray critique as LazyApply |

**Category read:** The commercial auto-appliers cluster at **2.1–2.4 Trustpilot** because volume-spray produces garbage applications and account bans. The ATS scanners (Jobscan) are loved but only fix keywords for a single JD. Nobody in this tier is local/free, India-native, or ethical-by-design.

---

## 4. India-native job platforms & startups (AI-matching assessed)

These are hosted web/app platforms (closed SaaS), assessed for AI-matching strength.

| Platform | What it is | AI matching | Job-seeker price | Strength | Lacks (for our user) |
|---|---|---|---|---|---|
| **[RedRob AI](https://redrob.io/)** | "India's AI for the next billion." Unified jobs + research + productivity; **made-in-India LLMs** | **% match score per listing**; 15M+ jobs ranked; aggregates across **50+ platforms**; **30+ Indian languages** (Hindi/Tamil/Telugu/Marathi…); claims 790M+ profiles, 20M+ postings, 6 yrs Indian data | Not stated on homepage (likely freemium) | The most serious India-native AI-match play; multilingual; huge India data moat; match-score UX | **Hosted web SaaS only** — no CLI, not open-source, not local/self-hosted; data leaves the user's machine; search/discovery, not auto-apply; resume builder "coming soon" |
| **Naukri (Resdex / FastForward / Relevance Score)** | India's #1 job board | ML recommendations; **Relevance Score on 6 params** (skills, designation, experience, salary, location, education); FastForward resume score (keyword + completeness + recency) | Free seeker; paid premium | **The structured-data goldmine** — CTC, notice period, experience bands, location, skills, all normalized in Resdex | Recruiter-biased; black-box scoring; no holistic LLM reasoning exposed to seeker; walled garden; no local/offline |
| **Instahyre** | Curated startup/premium hiring | "Instamatch" — only shows matched roles; learns from "not interested"; claims 5× response, recruiter accuracy "matching best human recruiters" | Free seeker | Strong precision matching; premium roles | Closed SaaS; recruiter-pull model; no resume-driven holistic score for the seeker; no local |
| **Cutshort** | Tech-talent network (4M+ devs) | AI+gamification+trusted-network matching of JD↔resume | Free seeker | Best for tech/dev roles in India; app-based | Tech-only; closed; no CLI/local; black-box |
| **Apna** | Largest India platform, 50M+ verified | AI-driven matching; blue/grey-collar + entry-level | Free seeker | Massive reach incl. Bharat/blue-collar (delivery, retail, telecalling) | Not for mid/senior white-collar; closed app; no resume-holistic scoring |
| **Hirect India** | Direct chat with founders/HMs | Chat-first, fast for startups | Free seeker | Speed; cuts apply-and-wait | Not a matcher; closed; no AI scoring layer |

**India read:** RedRob is the one genuinely ambitious AI-match + multilingual India play — but it's **closed, hosted, web-only, and your data leaves your machine.** Naukri owns the **structured data** (the thing that makes India scoring tractable) but exposes only a black-box keyword-ish Relevance Score, recruiter-biased, no holistic LLM reasoning, no local option. Instahyre/Cutshort/Apna are good vertical matchers but all closed SaaS with opaque scoring.

---

## 5. GAP ANALYSIS — what NO existing tool does well for the Indian job seeker

Scoring every tool above against the five attributes our rebuild would combine:

| Tool | India-native (Naukri structured data) | Holistic **LLM** scoring (not keyword-match) | CLI-agnostic / local | Free / self-hosted (data stays on machine) | No-spray ethics (fewer, better; review-first) |
|---|:--:|:--:|:--:|:--:|:--:|
| santifer/career-ops | ✗ | ✓ | ✓ | ✓ | ✓ |
| srbhr/Resume-Matcher | ✗ | ✓ (1 JD only) | partial (web app) | ✓ | n/a (no search) |
| ApplyPilot | ✗ | ✓ (1–10) | ✓ (CLI) | ✓ | ✗ (auto-spray) |
| AIHawk | ✗ | ✓ | ✓ | ✓ | ✗ (archived + spray) |
| JustHireMe | ✗ | optional | ✓ (local) | ✓ | ✓ |
| career-ops-india | **✓** | ✓ | ✓ | ✓ | ✓ |
| RedRob | **✓** | ✓ | ✗ (hosted) | ✗ (cloud) | ✓ (search, not spray) |
| Naukri | **✓✓ (owns data)** | ✗ (keyword/relevance) | ✗ | ✗ | n/a |
| Instahyre/Cutshort/Apna | ✓ | partial (black-box) | ✗ | ✗ | ✓ |
| LazyApply/LoopCV/Massive | ✗ | partial | ✗ | ✗ | ✗ |
| Jobscan | ✗ | ✗ (keyword) | ✗ | ✗ | n/a |

**The single biggest gap:** *No tool combines (a) Naukri-grade Indian structured data with (b) holistic LLM fit-scoring, in (c) a CLI-agnostic, (d) local/free/self-hosted package, under (e) a no-spray ethic.* The two open-source giants (career-ops, Resume-Matcher) nail c/d/e but are blind to India. RedRob nails a/b and is multilingual but is closed, cloud, web-only — your resume and search history leave your machine. Naukri owns the data (a) but its scoring is a recruiter-biased black box and there is no local/CLI/holistic path. The **only** project in the whole landscape that ticks a–e is **career-ops-india — a 10-star solo fork** with no productisation, bolting India boards onto a Western eval engine rather than being architected around Resdex fields.

**Concrete openings the rebuild should own:**
1. **Resdex-native scoring.** Score on the fields India actually uses — **CTC/LPA, in-hand, notice period, bond penalties, experience bands, location** — not Western salary/keyword heuristics. (career-ops-india proved the model; nobody productised it.)
2. **Holistic LLM fit, not ATS keyword-match.** Jobscan/Naukri optimise for the bot; deliver a *why-this-fits* LLM judgment a seeker can trust.
3. **Ghost-job / scam detection tuned for India** (career-ops-india's GLS is the template; Naukri repost-spam is rampant).
4. **Local-first, free, self-hosted — data never leaves the machine.** This is the trust wedge against RedRob/Instahyre (cloud) and the Sonara failure mode (stranded users).
5. **No-spray ethics as a feature.** The entire commercial auto-apply tier sits at 2.1–2.4 Trustpilot precisely because spray destroys trust and triggers bans. "Fewer, better, you-approve-before-apply" is both ethical and the better product.
6. **CLI-agnostic** (career-ops's reach across Claude Code / Gemini / Codex / Cursor) — but **without** career-ops's dependency on a paid coding agent to do the scanning; our own scraper + scorer should run standalone.
7. **Intern / fresher mode** (PPO probability, city-wise stipend benchmarks) — a uniquely Indian need only career-ops-india has touched.

---

## 6. UNVERIFIED / COULD NOT CONFIRM

Read directly off the live page (HIGH confidence): all star/fork/license/last-activity figures in §1 and the §2 forks table — santifer/career-ops (51.3k), srbhr/Resume-Matcher (27.3k), feder-cr/AIHawk (29.9k, archived 17 May 2026), ApplyPilot (1.1k), JustHireMe (2.0k), jobsync (609), career-ops-india (10), poferraz/career-ops (7), and the fork-page stars (BobbyWang0120 ~95, AKCodez ~35, etc.).

Could NOT confirm against a single canonical live page (sourced from WebSearch aggregation of product pages + third-party review blogs — treat as approximate):
- **All commercial pricing** — LazyApply ($99–$999/yr), LoopCV (€9.99/€29.99/mo, ₹453), Jobscan ($49.95 / $29.98 quarterly), Massive (tiers + 3-mo min), JobHire.AI ($19/wk), Sonara (~$49/mo peak). **UNVERIFIED (approx)** — pricing pages not individually WebFetched.
- **All Trustpilot ratings** — LazyApply 2.4, LoopCV 3.9, Massive 2.1. From review aggregators, not fetched from Trustpilot live. **UNVERIFIED (approx).**
- **Sonara "dead" status** — multiple 2026 articles report site 403/timeouts and no shutdown notice; not independently confirmed by fetching sonara.ai live. **UNVERIFIED.**
- **RedRob data-moat claims** — "790M+ profiles, 20M+ postings, 15M+ jobs, 50+ platforms, 30+ languages, 6 yrs data" are RedRob's own marketing from its site; not third-party audited. RedRob job-seeker **pricing** not stated on homepage. **UNVERIFIED (vendor claim).**
- **Naukri/Instahyre/Cutshort/Apna AI-matching specifics** (Relevance Score 6 params, Instamatch 5× response, Apna 50M+) — from vendor pages / review sites, not audited. **UNVERIFIED (vendor claim).**
- **career-ops-india last-commit date** — repo shows ~106 commits and "recent" activity but the exact last-commit date was not surfaced on the fetched page. **UNVERIFIED.**
- **Honourable-mention repos** (resume-lm, resume-ranking, resume-screening-app, the Naukri scrapers) — described from search snippets; **star counts NOT individually fetched. UNVERIFIED.**
- **career-ops fork divergence** for BobbyWang0120/AKCodez/ncoprod — star counts read live, but what each actually changed vs the original was NOT inspected. **UNVERIFIED.**
- Two distinct early reports on AIHawk timeline (Feb 2024 service suspension vs Nov 2024 last commit vs 17 May 2026 archival) — the **17 May 2026 archived** flag is read live off the repo and is HIGH confidence; the earlier dates are from search and are secondary.
