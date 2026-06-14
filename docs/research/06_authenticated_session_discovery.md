# 06 — Authenticated-Session & Discovery Methods for LinkedIn / Indeed / Naukri (Permanent Reference)

> **Purpose:** Answer the core product question — *what is the most legitimate, reliable, low-friction way to give an Indian job-seeker listings from LinkedIn, Indeed, and Naukri, and how have others already solved it?* — and deliver an honest differentiation verdict.
>
> **Method:** Every GitHub fact below was checked against the **live GitHub API** (`gh api` / `gh pr` / `gh issue`) on **2026-06-10**. Every legal/commercial fact was checked against a **live web source** the same day; URLs are inline. A deep-research workflow was also run; its adversarial-verification pass failed mid-run on a session rate-limit (every claim came back `0-0`, i.e. *verifiers could not execute* — **not** genuine refutation), so its legal claims were **re-verified by hand here** and are cited to primary legal sources. Anything still unverified is flagged **`[UNVERIFIED]`**.

---

## ⭐ RECOMMENDATION (read this first)

**Build discovery as a boring, legitimate, layered stack — and stop treating "access to LinkedIn/Indeed/Naukri" as the differentiator, because it isn't one.**

Recommended discovery stack, in priority order (this is also, almost exactly, the stack career-ops is independently converging on):

1. **Layer 1 — Zero-token ATS scan** (Greenhouse / Ashby / Lever / Workable public JSON APIs). Highest legitimacy, highest reliability, zero friction. Misses Naukri-native and recruiter-posted jobs.
2. **Layer 2 — Google Jobs via SerpAPI/Serper** (FitFirst already uses this). You query *Google*, not the platform — clean legitimacy. Indexes LinkedIn + many boards; **weak for Naukri**, contested for Indeed.
3. **Layer 3 — Apify BYO-token, *cookieless* actors** for the India gap (Naukri, Foundit, LinkedIn-exclusive). Cookieless actors hit **public guest APIs** → no login, no account-ban risk. Gated behind a user-supplied token, off by default.
4. **Layer 4 — The user's OWN authenticated session, NO stealth** (manual login, human-paced, visible footprint). A *user-initiated, off-by-default, power-user* feature — never the backbone. This is the single most ToS-sensitive layer and its legitimacy is genuinely contested.
5. **OFF-LIMITS — stealth / anti-bot evasion** (Patchright, CDP fingerprint spoofing, rotating proxies to defeat detection). This is the line every defensible project refuses to cross. Do not cross it.

**Official LinkedIn/Indeed job-search APIs are not an option** — the doors are closed (see Part 4F). That is *why* everyone is forced into the layers above.

---

## 🎯 THE DIFFERENTIATION VERDICT (the honest answer, up front)

**Your premise is out of date, and the correction changes the strategy.**

The brief assumes career-ops *rejected* LinkedIn scraping (issue "#238") and therefore the authenticated-user-session model is an open wedge FitFirst can own. **That is not what the live repo shows.** As of 2026-06-10:

- **#238 is an OPEN feature *request*** ("Persistent portal sessions with auto-login") — not a rejected PR. It *proposes* exactly the user-session model you want to build, for LinkedIn **and Naukri and Indeed**. [Live ↗](https://github.com/santifer/career-ops/issues/238)
- **An actual authenticated-LinkedIn-scanner implementation is in flight and OPEN** — PR #379, 2,206 additions, 32 files. The maintainer explicitly said *"not closing… on the roadmap (#230 + #238)… this isn't superseded… we move forward."* [Live ↗](https://github.com/santifer/career-ops/pull/379)
- **An Apify-LinkedIn-token scanner is also proposed and OPEN** — issue #791 (2026-06-05), the *same BYO-token model FitFirst already uses*. [Live ↗](https://github.com/santifer/career-ops/issues/791)
- What career-ops **actually rejected** was **stealth** — issue #237 (replace Playwright with Patchright for anti-bot evasion), closed **NOT_PLANNED**. [Live ↗](https://github.com/santifer/career-ops/issues/237)

So the discovery-method wedge you hoped for is **not open** — career-ops is moving into it right now, by both routes you were considering (authenticated session *and* Apify token). And the one thing they refuse to do (stealth) is the one thing **you also must not do**.

**Therefore:**

- **Discovery method is NOT a defensible differentiator for FitFirst.** JobSpy (3.6k★), Apify, and Google Jobs already commoditise it; career-ops is adding the authenticated-session and Apify-token paths you imagined. There is no secret legitimate channel they're missing.
- **The real, durable wedge is unchanged from [Doc 04](04_competitive_landscape.md) / [Doc 05](05_build_plan_and_decisions.md): India-native *scoring* (Resdex/CTC/notice-period/India ghost-job detection) + *productization for non-coders*.** career-ops requires a paid coding CLI; that is a genuine adoption wall for mass Indian seekers. FitFirst's differentiation is *"we score India jobs better and package it for people who don't live in a terminal,"* riding on a **commodity** discovery layer.
- **The honest strategic fork:**
  - If your value proposition is *discovery* → **contribute India sources + a Naukri provider to career-ops** (issues #230/#238/#791 are literally open invitations). Rebuilding to win on discovery is duplicating work that the 51k-star incumbent is already shipping.
  - If your value proposition is *India-native scoring + a non-coder product* → **rebuilding is justified**, but be clear-eyed that the discovery layer is plumbing you should make as boring and legitimate as possible (and could even borrow from career-ops's MIT code).

**Naukri is the one genuine India-specific hard problem nobody has solved** (Part 2). career-ops lists it (#238) but has no implementation; its India fork *configures* Naukri but does **not** access it (Part 2). If FitFirst wants a discovery-flavored wedge at all, *"the first tool that actually, legitimately pulls structured Naukri listings"* is the only candidate — and the only legitimate routes to it are Apify (paid, BYO-token) or the user's own logged-in Naukri session (fragile, ToS-gray). Neither is a moat.

---

## PART 1 — Who already built this, and HOW

### 1.1 Summary table (all metadata verified live via GitHub API, 2026-06-10)

| Repo | ★ | License | Last push | Lang | How it accesses LinkedIn/Indeed/Naukri | 429 / bot-detection | 2026 status |
|---|--:|---|---|---|---|---|---|
| [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) | 3,604 | MIT | 2026-02-18 | Python | **Public guest endpoints, no login** + optional proxies. Modules for `linkedin`, `indeed`, `glassdoor`, `google`, `ziprecruiter`, `bayt`, `bdjobs`, **`naukri`** all confirmed present in tree | README: "All of the job board sites are aggressive with blocking." LinkedIn rate-limits ~10th page/IP → "proxies are a must." Indeed = "best scraper currently with no rate limiting." | **Live**, dominant tool. Last push ~4 mo ago |
| [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) | 2,234 | Apache-2.0 | **2026-06-09** | Python | **The user's OWN logged-in browser session.** Manual login window; persistent profile at `~/.linkedin-mcp/profile/`; uses **Patchright** (stealth Chromium) at `~/.linkedin-mcp/patchright-browsers` | User solves captcha manually; may need mobile-app login confirm. Single serialized session (lock; concurrent calls queue) | **Live & very active** (pushed yesterday). The reference user-session tool — but *with* stealth |
| [spinlud/py-linkedin-jobs-scraper](https://github.com/spinlud/py-linkedin-jobs-scraper) | 482 | — | 2025-03-14 | Python | **Anonymous by default**, OR **the user's own `li_at` cookie** (`LI_AT_COOKIE` env var, copied from their logged-in browser) | README ⚠: "anonymous session strategy is **no longer maintained**." Rate-limit guidance: ≤1 worker authenticated, `slow_mo` ≥1.3 anon / 0.5 auth | **Stale** (>1 yr), 37 open issues. Anonymous path decaying |
| [spinlud/linkedin-jobs-scraper](https://github.com/spinlud/linkedin-jobs-scraper) | 178 | — | 2025-03-14 | TS | Same as above (TS port) | Same | Stale |
| [Hyperion101010/naukri-scraper](https://github.com/Hyperion101010/naukri-scraper) | 17 | — | 2023-05-23 | Python | `requests` against Naukri | n/a | Likely broken (3 yr) |
| [rameezarshad/naukri-api](https://github.com/rameezarshad/naukri-api) | 23 | — | 2018-01-22 | Python | Old Naukri endpoint | n/a | Dead (8 yr) |
| [navchandar/Naukri](https://github.com/navchandar/Naukri) | 80 | — | **2026-06-04** | Python | Selenium in the user's session — **updates the user's own Naukri profile** (not a listing scraper) | Runs as the logged-in user | **Live & active** |
| [Prateek-Wayne/naukri-resume-action](https://github.com/Prateek-Wayne/naukri-resume-action) | 21 | — | **2026-06-08** | TS | GitHub Action — **auto-updates user's Naukri profile** for visibility (not a scraper) | Runs as the user | **Live & active** |
| [GoliathReaper/JobSailor](https://github.com/GoliathReaper/JobSailor) | 25 | — | 2024-06-23 | Python | Selenium **auto-apply** to Naukri in the user's session | Runs as the user | Semi-stale |
| Standalone Indeed scrapers (rynobax 56★ '22, kanugurajesh 15★ '23, …) | <60 | mixed | 2014–2023 | mixed | DOM/`requests` scraping of Indeed | — | Mostly **abandoned**; JobSpy ate this category |

> **The single biggest Part-1 pattern:** the most-starred, *most recently maintained* Naukri repos ([navchandar/Naukri](https://github.com/navchandar/Naukri), [Prateek-Wayne](https://github.com/Prateek-Wayne/naukri-resume-action)) are **profile-updaters and auto-appliers that run inside the user's own logged-in session** — *not* listing scrapers. The actual Naukri *listing* scrapers are all old (2018, 2023) and low-star. Translation: **anonymous Naukri listing-scraping has effectively been abandoned as unmaintainable; what survives on Naukri is automation of the user's own account.** That is a strong real-world signal about what's durable.

### 1.2 JobSpy — the canonical "how others did it" (read in full)

[speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) is the dominant multi-board scraper (3,604★, MIT). From its [README](https://github.com/speedyapply/JobSpy/blob/main/README.md) (verified):

- **Access method:** public/guest endpoints, **no login**, concurrent across boards; "Proxies support to bypass blocking." It does **not** use the user's session — it scrapes anonymously and leans on proxies.
- **Boards:** `linkedin, indeed, glassdoor, google, zip_recruiter, bayt, bdjobs, naukri`. The `jobspy/naukri/` module is **present in the source tree** (verified) — so the leading scraper *does* claim Naukri support via a guest endpoint.
- **India:** Indeed supports `country_indeed='India'` (India is in the supported-country table).
- **Bot-detection, in their own words:**
  - *"Indeed is the best scraper currently with no rate limiting."*
  - *"LinkedIn is the most restrictive and usually rate limits around the 10th page with one ip. Proxies are a must basically."*
  - On HTTP 429: *"you have been blocked by the job board site for sending too many requests. All of the job board sites are aggressive with blocking."* Mitigation = wait between scrapes + rotate proxies.
- **Ecosystem** (shows the pattern's reach): [rainmanjam/jobspy-api](https://github.com/rainmanjam/jobspy-api) (Dockerized, 370★), [borgius/jobspy-mcp-server](https://github.com/borgius/jobspy-mcp-server) (73★), [qpwm06/QuickApply](https://github.com/qpwm06/QuickApply) (JobSpy + Codex, 103★).

**Honest read:** JobSpy proves the anonymous-guest-API + proxy model *works and scales across boards including Naukri* — but its own docs concede LinkedIn 429s fast and "all sites are aggressive with blocking." This is precisely the fragility/ToS profile FitFirst is trying to avoid. It is **not** a user-session model; it is industrial anonymous scraping that depends on proxies (i.e. mild evasion).

### 1.3 linkedin-mcp-server — the reference *user-session* model

[stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) (2,234★, Apache-2.0, pushed **2026-06-09** — actively maintained). From its [README](https://github.com/stickerdaniel/linkedin-mcp-server) (verified):

- *"An MCP server that lets AI assistants like Claude read LinkedIn data **through your own logged-in browser session.**"* — profiles, companies, **jobs**, messages.
- **Auth:** opens a real LinkedIn login window on first use; `--login` saves a **persistent browser profile** (`~/.linkedin-mcp/profile/`). Credentials are never stored — only the session.
- **Stealth:** runs on **Patchright** (the undetectable Playwright fork). This is the crucial caveat — it *does* employ anti-detection.
- **Captcha:** solved manually by the user; may require LinkedIn mobile-app confirmation.
- **Concurrency:** one session, serialized (a lock; requests queue) — i.e. naturally low-volume.
- Carries an explicit trademark/non-affiliation **disclaimer**.

**This is the closest existing thing to "drive the user's logged-in session,"** it's popular, and it's actively maintained in 2026 — but it sits on the *stealth* side of the line (Patchright), which is the side career-ops deliberately refused (Part 4E).

---

## PART 2 — Indian-context tools

### 2.1 career-ops-india (itsmedhawal) — did it actually solve Naukri? **No.**

Metadata (verified live): [itsmedhawal/career-ops-india](https://github.com/itsmedhawal/career-ops-india) — **10★, 3 forks, MIT, JavaScript, fork of `santifer/career-ops`, created 2026-04-11, last push 2026-04-27.** (So it has been **dormant ~6 weeks** as of 2026-06-10.)

**I read its actual scanner code.** Findings:

- **`scan.mjs` only fetches Greenhouse, Ashby, and Lever APIs** — inline parsers for exactly those three; header comment: *"Fetches Greenhouse, Ashby, and Lever APIs directly… Zero Claude API tokens — pure HTTP + JSON."* There is **no `providers/` directory** and **no Naukri / LinkedIn / Indeed / Foundit / Cutshort / iimjobs handler** anywhere in executable code. (Verified by reading the file + the full repo tree.)
- **How "Naukri/LinkedIn/Indeed/Foundit/Cutshort/iimjobs" actually appear:** only as **LLM-driven WebSearch `site:` query strings** in `templates/portals.example.yml`, e.g. `query: 'site:naukri.com "machine learning" OR "AI engineer" … Bangalore OR Mumbai'`, and similar for `site:linkedin.com/jobs`, `site:iimjobs.com`, `site:cutshort.io`, `site:foundit.in`, `site:wellfound.com`.
- **`modes/scan.md` (in Spanish, inherited) defines a 3-tier discovery model:**
  - **Nivel 1 — Playwright** on each tracked company's `careers_url` (the "principal/most reliable" method) — i.e. company career pages, not the job boards.
  - **Nivel 2 — Greenhouse API** (complementary, fast).
  - **Nivel 3 — WebSearch `site:` queries** ("broad discovery"), with an explicit warning that *"results may be stale (Google caches for weeks/months)"* and a mandatory Playwright **liveness re-check** of every Nivel-3 URL before use.

**Verdict on the brief's question:** career-ops-india **configured** Naukri/LinkedIn/etc. as search-engine `site:` queries and leaned on the host CLI's LLM to run WebSearch + Playwright-verify the links. It did **not** build any Naukri (or LinkedIn/Indeed) data access — no API, no structured fields, no session. It **inherited career-ops's ATS-only scanner verbatim** and bolted India boards on at the *prompt/config* layer. This confirms and sharpens [Doc 04 §2](04_competitive_landscape.md): it *validated demand* for India sources but *solved nothing technically* on Naukri.

### 2.2 The Indian open-source aggregator space is essentially empty

A live GitHub sweep (`india jobs`, `indian jobs scraper`, `jobs telegram bot`, etc.) returned **only noise** below career-ops-india: single-digit-star personal dashboards, static "job adda" sites, and abandoned experiments. There is **no maintained, multi-source Indian open-source job aggregator** that pulls Naukri + LinkedIn + Indeed together. The 10★ career-ops-india fork is the high-water mark — and it doesn't actually access Naukri. **This is the clearest evidence that the India-aggregation space is genuinely open at the *product* level — even if the discovery *method* is commodity.**

### 2.3 Telegram / WhatsApp job channels

Telegram job channels are large in India, but the open-source tooling around them is thin and low-quality (the GitHub sweep found only 0–2★ generic "jobs telegram bot" repos, none India-Naukri-specific). Telegram channels are **human-curated reposts** — high recall for fresher/IT-services roles, low structure, high spam/ghost-job rate. **`[UNVERIFIED]`** as a *reliable structured* source; usable only as a supplementary, heavily-filtered feed. No credible repo proves a clean pipeline here.

---

## PART 3 — The indirect-coverage angle (can we cover LinkedIn/Indeed jobs without touching them?)

### 3.1 Google Jobs via SerpAPI / Serper — partial yes, weak on Naukri

- **What it is:** [SerpAPI's Google Jobs API](https://serpapi.com/google-jobs-api) scrapes the Google Jobs panel and returns structured JSON (title, company, location, posted date, description, apply links) **"across every board Google indexes (LinkedIn, Indeed, Lever, ZipRecruiter, Workday, and more) in one response,"** **deduplicated by Google.** ([SerpAPI blog](https://serpapi.com/blog/scrape-google-jobs-to-easily-make-job-lists-using-serpapi/))
- **LinkedIn:** multiple 2026 sources say LinkedIn **does** participate in Google for Jobs (Google aggregates from "Indeed, LinkedIn, ZipRecruiter, Glassdoor, Monster, CareerBuilder"). ([fantastic.jobs](https://fantastic.jobs/article/best-job-scrapers), recruiting/SEO blogs.) **`[PARTIALLY VERIFIED]`** — asserted by SEO/recruiting blogs and SerpAPI marketing, not a definitive Google statement; depth (whether *all* LinkedIn jobs surface) is unknown.
- **Indeed:** participation is **genuinely contested**. Indeed has historically *not* fed Google for Jobs; current sources did not confirm Indeed's status either way. **`[UNVERIFIED]` — treat Indeed-via-Google-Jobs as unreliable.**
- **Naukri:** **weak.** Google for Jobs requires a strict `JobPosting` structured-data schema; Naukri does not reliably emit it, so Naukri coverage through Google Jobs is thin. For Naukri you need a dedicated path (Apify — below).
- **Cost shape:** pay **per query**, not per record (search-quota economics) — high-volume gets expensive faster than per-record providers. ([SerpAPI](https://serpapi.com/google-jobs-api))

**Net:** Google Jobs (which FitFirst already uses) is a legitimate, low-friction way to indirectly capture *LinkedIn* and ATS listings — but it under-covers Naukri and is shaky on Indeed.

### 3.2 Company ATS (Greenhouse / Ashby / Lever / Workday) — the legit backbone, but one-directional

- ATS platforms **natively push job feeds INTO LinkedIn, Indeed, and Glassdoor out of the box.** Greenhouse offers free native integrations with LinkedIn, Indeed, Monster, ZipRecruiter; Lever pushes to LinkedIn and Indeed. ([Greenhouse × LinkedIn](https://business.linkedin.com/talent-solutions/linkedin-hiring-integrations/greenhouse)) So a large share of jobs visible on LinkedIn/Indeed *originated* in an ATS and can be read from the ATS's **public JSON API** — zero token, fully legal.
- **The asymmetry that matters:** the ATS→LinkedIn feed is **one-directional**. Scanning ATS captures jobs that *flow out to* LinkedIn/Indeed, but **misses LinkedIn-/Naukri-exclusive postings** — recruiter-posted roles, staffing-agency listings, and the enormous Indian SME/IT-services volume that lives natively on Naukri and never touches a Western ATS.
- **Overlap percentage:** **`[UNVERIFIED]`** — no public source gives a hard cross-posting %. Directionally, ATS-native cross-posting to LinkedIn/Indeed is *standard practice*, but the India-relevant fraction is unknown and likely *lower* than in the US (Indian SMEs skew Naukri-native, not Greenhouse).

### 3.3 Apify "All Jobs Scraper" — the best single indirect route for India

The [Apify All Jobs Scraper](https://apify.com/agentx/all-jobs-scraper) aggregates, in one run, listings from **Indeed, LinkedIn, Glassdoor, ZipRecruiter, JobStreet, Glints, StepStone, Naukri, Foundit, Bayt, Reed, Totaljobs, … Talent.com** — i.e. it **explicitly includes Naukri and Foundit.** Combined with cookieless LinkedIn actors that hit the **public guest API** (no auth, no ban risk — Part 4), Apify is the **most complete India-coverage indirect route**, at the cost of a BYO-token and per-run fees (economics detailed in [Doc 02](02_apify_discovery_study.md)). career-ops's own #791 proposes exactly this for LinkedIn.

### 3.4 RSS / mirrors

Some ATS and niche boards expose RSS; large boards (LinkedIn/Indeed/Naukri) largely do **not** offer useful public job-search RSS in 2026. Aggregator "mirror" sites that republish LinkedIn/Indeed exist but are themselves scrapers of uncertain legality and freshness. **`[UNVERIFIED]`** as a primary source; not recommended as a backbone.

**Part 3 conclusion:** You can cover *a meaningful share* of "the jobs that are also on LinkedIn/Indeed" without touching them — via **ATS APIs (Layer 1) + Google Jobs (Layer 2)** — but you **cannot fully cover Naukri-native or LinkedIn-exclusive postings** indirectly. The only ways to close that India gap are **Apify (paid, BYO-token)** or the **user's own logged-in session** (Part 4).

---

## PART 4 — User-session / extension model: legitimacy & viability

### 4A. Why the extension model (Simplify / Teal / Huntr / Jobscan) is accepted

From vendor docs (verified): browser extensions like [Simplify Copilot](https://simplify.jobs/copilot), [Huntr](https://help.huntr.co/en/articles/9859408-the-huntr-chrome-extension), and [Teal](https://www.tealhq.com/tool/job-search-chrome-extension) work by **reading the form on the page the user is currently viewing and autofilling it from the user's OWN profile data stored in the extension.** Per the search of vendor help docs: *"The extensions use your own saved profile data to fill forms — they don't access your LinkedIn session data directly for autofill purposes."*

**Why that's defensible** (the principle to copy):
1. **The user is present and acting** — the extension augments a page the human already opened; it does not bulk-harvest in the background.
2. **It reads what the user can already see**, and writes data the user already owns.
3. **No mass extraction / no resale** — it's a personal-productivity overlay, not a data pipeline.
4. **It runs in the user's own browser, as the user** — the platform sees a normal logged-in human session.

(**Caveat:** the *auto-apply* extensions that cross from "autofill" into "submit hundreds of applications" *do* trigger enforcement — e.g. [applyarc's 2026 test](https://applyarc.com/blog/linkedin-job-scraper-tools) found several LinkedIn automation tools got flagged, and a cottage industry of "safer Simplify alternatives" exists. The defensible line is **assist, don't automate-at-volume**.) **Jobscan** is primarily an ATS resume-match scanner whose extension reads the JD on the page you're viewing to compare to your resume — it does **not** aggregate jobs ([Doc 04 §3](04_competitive_landscape.md)).

### 4B. Can an agentic CLI / Playwright drive the user's EXISTING logged-in Chrome profile?

**Technically yes** — both reference implementations do it:
- [linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server): `launchPersistentContext` on a saved profile; manual login once.
- career-ops PR #379: `chromium.launchPersistentContext('~/.scan-auth/<portal>/profile/')`, `--login` flow, randomized human-like delays.

**ToS risk vs anonymous scraping:** acting *as the authenticated user, in their own browser, at human pace, with no stealth* is the **least legally exposed** form of automation (it most resembles a person browsing) — **but it is still automation, and LinkedIn/Naukri ToS restrict automated access regardless of whose account it is.** It is *lower* risk than anonymous proxy-scraping, not *zero* risk. The honest framing: this is **gray, user-consented, and account-bounded** — the user risks *their own* account, knowingly, not a third party's data.

### 4C. hiQ v. LinkedIn — current legal status (verified, multi-source)

The deep-research workflow's "refuted" verdict here was a **false signal** (verifiers hit a rate-limit). Re-verified by hand against primary legal sources:

- The famous wins were **preliminary**: the **9th Circuit (twice, incl. Apr 2022) held the CFAA's "without authorization" clause likely does *not* bar scraping of *publicly accessible* LinkedIn data** (data not behind a login). ([Justia, 9th Cir. 2022](https://law.justia.com/cases/federal/appellate-courts/ca9/17-16783/17-16783-2022-04-18.html); [RopesDataPhiles](https://www.ropesdataphiles.com/2022/04/ninth-circuit-affirms-preliminary-injunction-in-hiq-labs-inc-v-linkedin-corporation-reasoning-that-cfaa-is-unlikely-to-bar-access-to-public-linkedin-data/))
- **But hiQ ultimately *lost*.** Nov 2022 summary judgment found hiQ **breached LinkedIn's User Agreement** (automated scraping + creating fake accounts). ([Morgan Lewis](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators); [zwillgen](https://www.zwillgen.com/alternative-data/hiq-v-linkedin-wrapped-up-web-scraping-lessons-learned/))
- **Dec 6, 2022 consent judgment:** **$500,000 against hiQ** for (1) breach of contract, (2) **CFAA violation "based on hiQ's direct access to password-protected pages on LinkedIn's platforms using fake accounts,"** (3) California unauthorized-access law, (4) trespass to chattels + misappropriation, (5) spoliation sanctions — plus a **permanent injunction to stop all scraping and destroy all scraped data, source code, and algorithms.** ([Privacy World](https://www.privacyworld.blog/2022/12/linkedins-data-scraping-battle-with-hiq-labs-ends-with-proposed-judgment/); [Proskauer](https://www.proskauer.com/blog/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case))

**The two lines this draws for FitFirst:**
1. **Public data:** scraping *publicly visible* pages is *weaker* under the CFAA — but a party bound by the ToS can **still be sued for breach of contract.** "Public ≠ free to scrape."
2. **Authenticated / fake-account access:** accessing *password-protected* pages (especially via fabricated accounts) is where **CFAA liability attached.** → A FitFirst feature that logs into LinkedIn — even as the *real* user — sits on the **authenticated** side of that line. Using the user's *own genuine* account (not fake accounts) avoids hiQ's worst fact, but does **not** make it ToS-clean.

### 4D. India: DPDP Act 2023, IT Act — Naukri (verified)

- **DPDP Act §3(c)(ii)** exempts from the Act personal data *"made or caused to be made publicly available"* by the data principal, or by someone under a **legal obligation** to publish it. On its face, this could exempt scraping public profile/job data. ([Law.asia](https://law.asia/india-data-scraping-regulation/); [IAPP](https://iapp.org/news/a/scraping-public-data-in-india-innovation-enabler-or-privacy-threat-))
- **But the government's stated position contradicts the statute:** In **August 2024**, MoS for Electronics & IT **Jitin Prasada told the Rajya Sabha** that scraping of public user data **IS covered by the IT Act, IT Rules, and DPDPA and requires consent**, transparency, and respect for individual rights. ([IAPP](https://iapp.org/news/a/scraping-public-data-in-india-innovation-enabler-or-privacy-threat-); [NLS Forum](https://forum.nls.ac.in/ijlt-blog-post/publicly-available-data-privacy-rights-the-debate-over-web-scraping/))
- **IT Act 2000 §43 (+ §66)** penalises unauthorised downloading/copying/extraction from a computer system without the owner's permission and gives compensation — a statutory hook for platforms (Naukri/LinkedIn) whose ToS forbid scraping. **`[PARTIALLY VERIFIED]`** (asserted by Indian legal commentary; no India court has squarely ruled on ToS/robots.txt enforceability — itself a noted open question).

**India net:** the legal position on scraping public data is **unsettled and trending toward consent-required** per the government's stance, even where the statute's text suggests an exemption. **Naukri's own ToS prohibit automated access.** For an India-first product, the safest posture is: **don't scrape Naukri server-side; if Naukri must be touched, do it inside the user's own session, with their consent, at human volume — or via a paid intermediary (Apify) that bears the access.**

### 4E. The "request cap before bot-detection" question — honest answer

There is **no published safe threshold.** What's actually documented:
- **JobSpy:** LinkedIn "rate limits around the **10th page** with one IP" (~250 jobs/IP) → proxies needed; Indeed "no rate limiting"; "all sites are aggressive with blocking." ([README](https://github.com/speedyapply/JobSpy/blob/main/README.md))
- **spinlud:** authenticated mode → use **≤1 worker**, `slow_mo` ≥0.5; anonymous → `slow_mo` ≥1.3; *"the right value depends on LinkedIn's rate-limiting, which varies over time."*
- **linkedin-mcp-server:** naturally low-volume — **one serialized session**, requests queued.
- **career-ops PR #379:** randomized `delay_between_pages_ms: [3000, 8000]` and `delay_between_searches_ms: [5000, 15000]`, plus `max_results_per_search` caps.

**Conclusion:** the only honestly "safe" volume is **low, human-paced, single-session, single-IP** (the user's own). Anything that needs proxies or many workers has already crossed from "behaving like a user" into "evading detection." There is no magic number; the safe regime is *behavioral*, not numeric.

### 4F. Official APIs — the doors are closed (verified)

- **LinkedIn Jobs API** is a **posting API, not a search API** — it lets *approved ATS/enterprise partners* post jobs and sync applicants. *"LinkedIn is currently not accepting new partnerships for the Job Posting API"*; access is **invitation-only, incorporated companies only, not individual developers.** It does **not** let you query/export LinkedIn's job listings. ([Microsoft Learn](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2026-03); [Clura 2026](https://clura.ai/blog/linkedin-api); [Scrapfly](https://scrapfly.io/blog/posts/guide-to-linkedin-api-and-alternatives))
- **Indeed Publisher Jobs API** (the old "Get Job" / "Job Search" endpoints suitable for search) is **deprecated and not available for new integrations**; Indeed now exposes partner/employer APIs (Job Sync, Sponsored Jobs) for *posting/advertising*, not job search. ([Indeed dev docs — Get Job (Deprecated)](https://developer.indeed.com/docs/publisher-jobs/get-job); [Indeed Partner Docs](https://docs.indeed.com/))
- **Naukri:** no public job-search API for third parties.

→ **The official, fully-legitimate channel does not exist for any of the three.** This is the structural reason every project is pushed into ATS/Google-Jobs/Apify/session methods.

### 4G. career-ops's actual position (the misconception, corrected in full)

What the brief calls *"career-ops's rejected LinkedIn scraping (#238)… no anti-bot evasion, standard Playwright, a recruiter can see who's knocking."* Here is the verified live record:

| Item | What it actually is | State (2026-06-10) |
|---|---|---|
| [Issue #238](https://github.com/santifer/career-ops/issues/238) | benzntech's **feature *request*** for persistent authenticated sessions (LinkedIn, **Naukri**, Indeed, Instahyre, Wellfound) via Patchright persistent profiles, manual login, credentials never stored | **OPEN** (created 2026-04-12) |
| [PR #379](https://github.com/santifer/career-ops/pull/379) | DSnoNintendo's **actual implementation** — `scan-auth.mjs`, Playwright persistent context, LinkedIn scanner, randomized delays, `--disable-blink-features=AutomationControlled`. 2,206 additions, 32 files | **OPEN**; maintainer: *"not closing… on the roadmap (#230 + #238)… this isn't superseded… we move forward"* |
| [Issue #515](https://github.com/santifer/career-ops/issues/515) | The **RFC** the maintainer required before merging #379 — full auth-scan architecture, profile storage under `~/.scan-auth/`, DATA_CONTRACT mapping | **OPEN** (created 2026-04-28) |
| [Issue #237](https://github.com/santifer/career-ops/issues/237) | Proposal to **replace Playwright with Patchright** (stealth/anti-bot) | **CLOSED — NOT_PLANNED** (2026-05-22) |
| [Issue #791](https://github.com/santifer/career-ops/issues/791) | Proposal to add an **Apify LinkedIn Jobs Scraper** as "Level 4," gated behind `APIFY_TOKEN`, ~100 scrapes/mo free tier | **OPEN** (created 2026-06-05) |
| [CONTRIBUTING.md](https://github.com/santifer/career-ops/blob/main/CONTRIBUTING.md) | *"PRs that scrape platforms prohibiting automated access (LinkedIn, etc.). **We actively reject these** to respect third-party ToS."* | Current policy |

**Reading the apparent contradiction honestly:** CONTRIBUTING.md says "reject LinkedIn scraping," yet the maintainer is *keeping the authenticated-LinkedIn PR open and on the roadmap.* The line career-ops is drawing — still being formalized via the #515 RFC — is:

- **REJECTED:** stealth / anti-bot **evasion** (Patchright #237), and *anonymous* scraping of platforms that forbid it (CONTRIBUTING.md). The maintainer's words on #237: *"switching to Patchright would change a foundational dependency for a marginal anti-detection gain… The browser path is reserved for SPA boards where authenticated sessions are the bigger lever."*
- **ON THE ROADMAP:** the **user's own authenticated session**, manual login, human-paced, **no stealth runtime**, footprint visible — treated as categorically different from "scraping."
- **Note the genuine internal dissent:** contributor @syahmiharith argued #379 *should not* merge to core (LinkedIn ToS restricts automation *regardless of auth*; it's fragile; it's a maintenance/risk burden) and proposed it live as a third-party plugin instead. The maintainer overrode that and kept it on the roadmap. **So career-ops's line here is contested and not yet settled** — which is exactly why it's in RFC.

**What this teaches FitFirst about the defensible line:** the durable distinction is **evasion vs. consented-self-access**. Don't disguise a bot to defeat detection (Patchright/CDP/proxy-rotation = the rejected side). *Acting as the authenticated user, with consent, at human pace, leaving a normal footprint* is the most-defensible automation — and even then, a serious contributor will tell you it's still ToS-gray. "A recruiter can see who's knocking" is the right instinct: **legitimacy comes from visibility and consent, not from hiding.**

---

## PART 5 — Ranked options + honest verdict

### 5.1 Ranking by (legitimacy × reliability × low-friction × India coverage)

Scale: ●●● strong · ●● moderate · ○ weak.

| Rank | Method | Legitimacy | Reliability | Low-friction | India coverage | Proven by |
|---|---|:--:|:--:|:--:|:--:|---|
| **1** | **Zero-token ATS scan** (Greenhouse/Ashby/Lever/Workable) | ●●● public APIs | ●●● stable JSON | ●●● no token/login | ●● Indian startups yes; **Naukri-native no** | career-ops, career-ops-india, JobSpy |
| **2** | **Google Jobs (SerpAPI/Serper)** | ●●● querying Google | ●●● | ●●● 1 key (already used) | ●● LinkedIn-via-Google ok; **Naukri weak**, Indeed contested | FitFirst today; SerpAPI |
| **3** | **Apify BYO-token, cookieless actors** (public guest API) | ●● public data, no account risk | ●● actor-dependent | ●● signup + token | ●●● **All Jobs Scraper incl. Naukri/Foundit** | [Doc 02](02_apify_discovery_study.md); career-ops #791 |
| **4** | **User's OWN authenticated session, no stealth** | ●● contested (user-consented, ToS-gray) | ○ DOM-fragile, ~10pp/IP on LinkedIn | ● user must log in | ●●● sees exactly what the user sees, incl. logged-in-only | career-ops #379; linkedin-mcp-server*; spinlud `li_at` |
| **5** | **Anonymous scraping + proxies** | ○ ToS-violating, evasion | ● breaks/429s | ●● | ●●● | JobSpy |
| **6** | **User session WITH stealth** (Patchright/CDP) | ○ active evasion = the rejected line | ●● capable | ● | ●●● | linkedin-mcp-server |
| **7** | **Official APIs** (LinkedIn Jobs / Indeed Publisher) | ●●● in principle | — | — | — | **Closed** — not available (Part 4F) |

\* linkedin-mcp-server proves the *session* mechanics but uses Patchright (so it's really a #4/#6 hybrid).

### 5.2 The most defensible LinkedIn + Indeed + Naukri coverage without fragile scraping / ToS violation / evasion / heavy friction

**A layered stack, in this order — #1 + #2 as the backbone, #3 for the India gap, #4 only as an off-by-default power-user option, #5/#6 never:**

1. **ATS zero-token (Layer 1)** for everything that flows out of Greenhouse/Ashby/Lever — captures the clean, legal majority of structured Western-ATS + Indian-startup roles.
2. **Google Jobs (Layer 2)** to indirectly pick up LinkedIn-surfaced and other-board listings via Google's deduplicated index — already in FitFirst.
3. **Apify BYO-token, cookieless (Layer 3)** to close the **Naukri / Foundit / LinkedIn-exclusive** gap that Layers 1–2 miss — gated behind a user-supplied token, off by default, the platform-access risk borne by Apify.
4. **User's-own-session read, no stealth (Layer 4)** — *optional, explicit, user-initiated*, for the power user who wants their logged-in LinkedIn/Naukri feed pulled in. Framed exactly as career-ops frames it: manual login, human pace, visible footprint, "you are accessing what you can already see, on your own account, at your own risk." **Never the default; never server-side; never with stealth.**

This stack has **no anonymous scraping, no proxy evasion, no fake accounts, no stealth runtime** — i.e. it stays entirely on the defensible side of both hiQ (no fake-account authenticated access) and career-ops's line (no Patchright). Its honest weakness is the same one everyone has: **Naukri-native coverage is only fully reachable via paid Apify or the user's own session.**

### 5.3 The honest differentiation verdict — restated, not flinched

**Is there a real product here, or should you contribute India features to career-ops?**

- **On discovery method: there is NO defensible wedge, and rebuilding to win on it is a mistake.** The method is commodity (JobSpy, Apify, Google Jobs), and **career-ops is actively shipping the two exact ideas you thought were yours** — authenticated user-session scanning (#379/#238/#515, on the roadmap) and Apify-token LinkedIn (#791). Issues #230/#238/#791 are open invitations. If discovery is your thesis, **the high-leverage move is to contribute an India provider set + a Naukri path to career-ops, not to rebuild a parallel scanner.**

- **On product: there IS a real wedge — but it is NOT discovery.** It is the combination career-ops structurally does **not** do and its India fork only gestured at:
  1. **India-native structured scoring** — score on Resdex/CTC/LPA/in-hand/notice-period/experience-bands, not Western salary heuristics ([Doc 04 §6](04_competitive_landscape.md), [Doc 05](05_build_plan_and_decisions.md)).
  2. **India-tuned ghost-job/scam detection** (Naukri repost-spam is rampant; career-ops-india's GLS is the template).
  3. **Productization for non-coders** — career-ops *requires a paid coding CLI*; that is a hard adoption wall for mass Indian seekers. A self-hosted, no-CLI, free, local product is a genuine packaging differentiator.

- **The one discovery-flavored wedge that survives scrutiny:** *"the first tool that legitimately delivers structured **Naukri** listings to an India seeker"* — because (a) nobody open-source has done it (Part 2), (b) career-ops only *lists* Naukri in a wish-list issue with no implementation, and (c) the only legitimate routes (Apify BYO-token; user's own Naukri session, no stealth) are ones you can package better for an Indian audience than a Western coding-CLI tool will. **This is a thin, defensible-but-not-moat wedge** — worth doing, not worth betting the company on as your *sole* differentiator.

**Bottom line:** Build FitFirst if and only if your bet is **India-native scoring + non-coder productization**, with discovery as a deliberately boring, legitimate, layered commodity (Layers 1–3, plus an optional user-session Layer 4). If your bet was *discovery access itself*, the honest move is to **contribute to career-ops** — you'd be rebuilding what the incumbent is already shipping, minus the 51k-star community and the just-formalized #515 legitimacy framework. **Don't differentiate on the pipe; differentiate on the judgment and the package.**

---

## Sources verified (live, 2026-06-10)

**GitHub primary sources (read via `gh api` / `gh pr` / `gh issue` — code/metadata, not marketing):**
- career-ops: [#238](https://github.com/santifer/career-ops/issues/238), [PR #379](https://github.com/santifer/career-ops/pull/379) (+ full human comment thread), [#515](https://github.com/santifer/career-ops/issues/515), [#237](https://github.com/santifer/career-ops/issues/237) (+ closing rationale), [#230](https://github.com/santifer/career-ops/issues/230), [#791](https://github.com/santifer/career-ops/issues/791), [CONTRIBUTING.md](https://github.com/santifer/career-ops/blob/main/CONTRIBUTING.md)
- [career-ops-india](https://github.com/itsmedhawal/career-ops-india): repo metadata, full tree, `scan.mjs`, `modes/scan.md`, `templates/portals.example.yml`
- [JobSpy](https://github.com/speedyapply/JobSpy): metadata, source tree (incl. `jobspy/naukri/`), README
- [linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server): metadata, README
- [spinlud/py-linkedin-jobs-scraper](https://github.com/spinlud/py-linkedin-jobs-scraper): metadata, README; plus Naukri/Indeed scraper survey via `gh search repos`

**Legal (web, re-verified by hand after the workflow's verifier rate-limited out):**
- hiQ v. LinkedIn: [Privacy World](https://www.privacyworld.blog/2022/12/linkedins-data-scraping-battle-with-hiq-labs-ends-with-proposed-judgment/) · [Morgan Lewis](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators) · [zwillgen](https://www.zwillgen.com/alternative-data/hiq-v-linkedin-wrapped-up-web-scraping-lessons-learned/) · [Proskauer](https://www.proskauer.com/blog/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case) · [9th Cir. via Justia](https://law.justia.com/cases/federal/appellate-courts/ca9/17-16783/17-16783-2022-04-18.html)
- India DPDP/IT Act: [IAPP](https://iapp.org/news/a/scraping-public-data-in-india-innovation-enabler-or-privacy-threat-) · [Law.asia](https://law.asia/india-data-scraping-regulation/) · [NLS Forum](https://forum.nls.ac.in/ijlt-blog-post/publicly-available-data-privacy-rights-the-debate-over-web-scraping/)

**APIs / commercial / indirect (web):**
- [LinkedIn Job Posting API (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2026-03) · [Clura 2026](https://clura.ai/blog/linkedin-api) · [Scrapfly](https://scrapfly.io/blog/posts/guide-to-linkedin-api-and-alternatives)
- [Indeed Get Job (Deprecated)](https://developer.indeed.com/docs/publisher-jobs/get-job) · [Indeed Partner Docs](https://docs.indeed.com/)
- [SerpAPI Google Jobs API](https://serpapi.com/google-jobs-api) · [SerpAPI blog](https://serpapi.com/blog/scrape-google-jobs-to-easily-make-job-lists-using-serpapi/) · [fantastic.jobs scraper roundup](https://fantastic.jobs/article/best-job-scrapers)
- [Apify All Jobs Scraper](https://apify.com/agentx/all-jobs-scraper) · [Apify LinkedIn scrapers roundup](https://use-apify.com/docs/best-apify-actors/best-linkedin-scrapers)
- Extensions: [Simplify Copilot](https://simplify.jobs/copilot) · [Huntr extension](https://help.huntr.co/en/articles/9859408-the-huntr-chrome-extension) · [Teal extension](https://www.tealhq.com/tool/job-search-chrome-extension) · [applyarc scraper test](https://applyarc.com/blog/linkedin-job-scraper-tools)
- ATS↔LinkedIn: [Greenhouse × LinkedIn integration](https://business.linkedin.com/talent-solutions/linkedin-hiring-integrations/greenhouse)

## Flagged `[UNVERIFIED]` / `[PARTIAL]`
- **LinkedIn participation in Google for Jobs** — asserted by SEO/recruiting blogs + SerpAPI, not a definitive Google statement; depth unknown. **`[PARTIAL]`**
- **Indeed participation in Google for Jobs** — contested; sources did not confirm. Treat as unreliable. **`[UNVERIFIED]`**
- **ATS→LinkedIn/Indeed cross-posting %** — directionally standard practice; no hard public number, India fraction likely lower. **`[UNVERIFIED]`**
- **IT Act §43/§66 as a scraping hook** — Indian legal commentary; no India court has ruled on ToS/robots.txt enforceability. **`[PARTIAL]`**
- **Telegram/WhatsApp job channels** — large but no credible OSS pipeline; spam/ghost-heavy. **`[UNVERIFIED]`** as a structured source.
- **JobSpy Naukri module live-working status** — module exists in tree + README claims support; not run-tested here (last repo push 2026-02-18). **`[PARTIAL]`**
- **career-ops-india last-commit recency** — last push 2026-04-27 (dormant ~6 wks); cadence undocumented. Verified date, uncertain future.
- **Deep-research workflow verification** — its adversarial pass failed on a session rate-limit (all `0-0`); those verdicts are **void**, and the legal claims were re-verified independently above.
