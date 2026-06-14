# Apify as a Job-Discovery Data Source — Reference Study

**Purpose:** Permanent reference for a ground-up rebuild of an India-focused, CLI-agnostic AI job-search tool. Evaluates Apify as the job-discovery data layer for LinkedIn, Indeed, and Naukri.

**Date compiled:** 2026-06-09
**Verification method:** Every fact below was fetched from a live Apify docs page, a live `apify.com/store` actor page, or a primary legal source. Prices and output-field schemas change frequently — each load-bearing fact carries its source URL inline. Anything that could not be confirmed against a primary source is listed in the final "UNVERIFIED / COULD NOT CONFIRM" section.

> **Pricing volatility warning:** Apify actor prices and the platform credit allocation are set by Apify and by individual (mostly community) developers and can change without notice. Re-verify per-result prices and the Free-plan credit amount on the live pages before relying on the cost model in Section 3.

---

## Sources verified (every URL fetched + what it gave us)

| # | URL | What it confirmed |
|---|-----|-------------------|
| S1 | https://apify.com/pricing | Plan tiers ($0 Free / $29 Starter / $199 Scale / $999 Business / Enterprise custom); Free plan "$5 to spend", "No credit card required", 8 GB max Actor RAM, 25 max concurrent runs; CU price $0.20 (Free/Starter), $0.16 (Scale), $0.13 (Business); residential proxy $8/GB; data transfer $0.20/GB; dataset storage rates. |
| S2 | https://docs.apify.com/api/v2/act-run-sync-get-dataset-items-post | The `run-sync-get-dataset-items` endpoint: `POST https://api.apify.com/v2/acts/:actorId/run-sync-get-dataset-items`; POST body becomes the actor INPUT; query params `timeout`, `memory`, `format`, `limit`, `offset`, `fields`; returns dataset items array (201) with `X-Apify-Pagination-*` headers. |
| S3 | https://docs.apify.com/api/v2 | Auth: token as `token` query param OR `Authorization: Bearer <token>` header; header method explicitly marked "(Recommended)" because URLs leak into history/logs. |
| S4 | https://docs.apify.com/platform/actors/running/usage-and-resources | CU definition: 1024 MB allocated memory for 1 hour = 1 CU (Memory[MB] × Duration[h] / 1024). |
| S5 | https://docs.apify.com/platform/actors/running/actors-in-store | Three store pricing models: Pay Per Event, Pay Per Usage, Rental. Key line: "Rental fees are subtracted automatically from your prepaid platform usage, similarly to compute units." |
| S6 | https://apify.com/curious_coder/linkedin-jobs-scraper | LinkedIn actor: $1.00 / 1,000 results; community-maintained; ~97K users / ~14K MAU; 4.4★ (99 reviews); last modified ~7 days ago. Output fields captured (salary as array of strings; no structured experience). |
| S7 | https://apify.com/harvestapi/linkedin-job-search | LinkedIn "No Cookies" actor: $1 / 1k jobs, pay-per-event; community (HarvestAPI); ~6.5K users / ~793 MAU; 3.6★ (16 reviews); last modified ~2 days ago. **Structured salary object** (text, min, max, currency, payPeriod, compensationType). No cookies/account needed. |
| S8 | https://apify.com/misceres/indeed-scraper | Indeed actor: from $3.00 / 1,000 listings; **Maintained by Apify**; ~24K users / ~2.2K MAU; 3.3★ (59 reviews); last modified ~5 days ago. Salary = free text; no structured experience. |
| S9 | https://apify.com/curious_coder/indeed-scraper | Indeed actor: ~$0.73 / 1k jobs usage **on top of $20/mo rental**; community; ~3.7K users / ~126 MAU; 4.8★ (47 reviews); last modified ~2 months ago. **Structured salary object** (min, max, type, currencyCode). |
| S10 | https://apify.com/memo23/naukri-scraper | Naukri actor: from $0.60 / 1,000 results (Free tier rate $0.0015/result; Bronze+ $0.99/1k = $0.001/result); community (Muhamed Didovic); ~1.4K users / ~409 MAU; 3.0★ (11 reviews); last modified ~3 days ago. **Structured `minimumExperience`/`maximumExperience` + Naukrigulf `Compensation.MinCtc/MaxCtc`.** |
| S11 | https://apify.com/makework36/naukri-scraper | Naukri actor: $3.50 / 1K (search) / $9.50 / 1K (with fetchDetails); tiered down to $0.65/1K; community (deusex machine); ~25 users / ~8 MAU; 3.0★ (1 review); last modified ~13 days ago. **Structured `experienceMin`/`experienceMax` + `salaryMin`/`salaryMax`/`salaryCurrency`/`salaryUsdEstimate`** (parses "6-15 Lacs PA"). |
| S12 | https://apify.com/epicscrapers/naukri-scraper | Naukri actor: from $1.00 / 1,000 results; community (Epic Scrapers); ~77 users; 4.5★ (2 reviews); last modified ~1 month ago. **Structured `minimumExperience`/`maximumExperience` + `salaryDetail{minimumSalary, maximumSalary, currency}`** — exact field names the brief asked us to hunt for. |
| S13 | https://blog.apify.com/is-web-scraping-legal/ | Apify's official stance: "Web scraping is legal if you scrape data that is publicly available on the internet"; personal data still governed by GDPR/CCPA/CPRA regardless of public visibility; browsewrap vs clickwrap ToS enforceability; cites hiQ v. LinkedIn anti-monopoly reasoning. |
| S14 | https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn (via search aggregation of Morgan Lewis / Proskauer / Justia) | hiQ v. LinkedIn final status: Dec 6 2022 stipulated consent judgment — $500K against hiQ, hiQ liable for trespass to chattels + misappropriation, permanent injunction barring hiQ from scraping LinkedIn. April 2022 9th Cir. reaffirmed CFAA "without authorization" does not cover public sites, but breach-of-contract claims on ToS survive. |

---

## SECTION 1 — THE API

### 1.1 The `run-sync-get-dataset-items` endpoint  *(S2)*

This is the single-call endpoint that runs an actor, waits for it to finish, and returns the scraped rows directly in the HTTP response — no separate "start run → poll → fetch dataset" dance. Ideal for a synchronous job-search request path.

```
POST https://api.apify.com/v2/acts/<actor>/run-sync-get-dataset-items
```

- `<actor>` is the actor ID or handle. In a handle, the `/` separator is URL-encoded as `~`, e.g. `curious_coder~linkedin-jobs-scraper`. (The docs accept the `acts` path segment; `actors` also resolves. The canonical docs path shown is `/v2/acts/:actorId/...`.)
- **Method:** `POST`.
- **Response:** `201` with a JSON array of dataset items. Pagination metadata is returned in headers `X-Apify-Pagination-Offset`, `X-Apify-Pagination-Limit`, `X-Apify-Pagination-Count`, `X-Apify-Pagination-Total`.

**Request body = the actor INPUT.** The entire POST payload (with its `Content-Type`, usually `application/json`) is passed straight into the actor as its `INPUT` object. So the body *is* the actor-specific input JSON (search query, location, max results, etc.) — its shape is defined by each actor (see Section 2 schemas).

**Useful query parameters** *(S2)*:

| Param | Type | Meaning |
|-------|------|---------|
| `token` | string | API token (auth — see below) |
| `timeout` | number | Max run time in **seconds** |
| `memory` | number | Memory limit in **MB** (min 128) |
| `format` | string | `json`, `jsonl`, `csv`, `html`, `xlsx`, `xml`, `rss` |
| `limit` | number | Max number of items to return |
| `offset` | number | Items to skip from the start |
| `fields` | string | Comma-separated allowlist of fields to return |

### 1.2 Authentication  *(S3)*

Two equivalent methods:

1. **Query parameter** — append `?token=<APIFY_TOKEN>` to the request URL. Docs: "Add it as the `token` parameter to your request URL."
2. **Bearer header (Recommended)** — `Authorization: Bearer <APIFY_TOKEN>`. Docs explicitly: "Using your token in the request header is more secure than using it as a URL parameter because URLs are often stored in browser history and server logs."

**Design implication for our rebuild:** the user brings their own Apify token; send it as a `Bearer` header server-side, never in a URL the client could log. (See Section 4 for the user-token model.)

### 1.3 Example call shape

```
POST https://api.apify.com/v2/acts/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items?limit=100&timeout=120
Authorization: Bearer apify_api_xxxxxxxxxxxxxxxx
Content-Type: application/json

{
  "queries": ["software engineer India"],
  "location": "India",
  "rows": 100
}
```
*(The body keys are illustrative — each actor defines its own input field names. Confirm against the specific actor's Input schema before wiring it.)*

### 1.4 Pricing model  *(S1, S4, S5)*

**Compute Unit (CU)** *(S4)*: the base unit of platform compute. **1024 MB of allocated memory running for 1 hour = 1 CU** (formula: `Memory[MB] × Duration[hours] / 1024`). An actor using 4 GB for 30 minutes = `4096 × 0.5 / 1024 = 2 CU`.

**Price per CU** *(S1)*:

| Plan | $ / CU |
|------|--------|
| Free & Starter | **$0.20** |
| Scale | $0.16 |
| Business | $0.13 |

**Platform usage add-ons** *(S1)*:
- Residential proxy: **$8 / GB** (Free/Starter).
- External data transfer: **$0.20 / GB**.
- Dataset storage: ~$1.00 per 1,000 GB-hours; ~$0.0004 per 1,000 reads; ~$0.005 per 1,000 writes.

**Store actor pricing models** *(S5)* — set by the actor developer:
1. **Pay Per Result / Pay Per Event** — "you pay for specific events the Actor creator defines, such as generating a single result or starting the Actor." This is the headline "$X / 1,000 results" number on most actor pages. Most (not all) bundle platform usage into that price.
2. **Pay Per Usage** — you pay only the underlying platform usage (CUs + storage + proxy); no developer markup.
3. **Rental** — a flat monthly fee **plus** platform usage. Docs: "Rental fees are subtracted automatically from your prepaid platform usage, similarly to compute units."

**Critical for the cost model:** because rental and per-result charges are *drawn from the same prepaid platform-usage balance as CUs* (S5), the **$5 Free-plan credit can be spent on pay-per-result and rental actors**, not just raw compute. This is what makes the free tier usable for real job searches.

### 1.5 The $5/month "Free" plan  *(S1)*

Confirmed verbatim from the pricing page:
- Price: **$0/month**.
- **"No credit card required."**
- Includes **"$5 to spend in Apify Store or on your own Actors"** (prepaid platform-usage credit, refreshed monthly).
- **8 GB** maximum Actor RAM.
- **25** maximum concurrent runs.

So the $5 buys ~25 CU of raw compute (at $0.20/CU) *or*, more relevantly, ~5,000 LinkedIn job results at $1/1k, or ~8,300 Naukri results at $0.60/1k — see Section 3.

---

## SECTION 2 — BEST ACTORS (LinkedIn, Indeed, Naukri)

> Maintenance signal definitions: "last modified" and user/MAU/rating numbers are read from each actor's store header. Prefer actors updated < ~30 days ago with a meaningful MAU count. **Almost all job actors on Apify are community-maintained** — the one Apify-maintained exception found is the Indeed scraper (S8).

### 2.1 LinkedIn

| Actor | Handle | Price | Maintainer / freshness | Users / MAU / rating | Structured exp? | Structured salary? |
|-------|--------|-------|------------------------|----------------------|-----------------|--------------------|
| **LinkedIn Jobs Scraper** | `curious_coder/linkedin-jobs-scraper` (S6) | **$1.00 / 1,000 results** | Community; ~7 days ago | 97K / 14K / 4.4★ (99) | ✗ none | ✗ `salaryInfo` = array of strings, e.g. `["$17.00","$19.00"]` |
| **Advanced LinkedIn Job Search (No Cookies)** | `harvestapi/linkedin-job-search` (S7) | **$1 / 1k jobs** (pay-per-event) | Community (HarvestAPI); ~2 days ago | 6.5K / 793 / 3.6★ (16) | ✗ none | ✓ **structured** `salary{text, min, max, currency, payPeriod, compensationType}` |

**Recommendation (LinkedIn):** `curious_coder/linkedin-jobs-scraper` for maturity/scale (97K users, 4.4★), but it gives salary only as loose strings and no experience field. `harvestapi/linkedin-job-search` is the better *data-quality* pick — same $1/1k, no cookies/login required (account-safety win), and it returns a **structured salary object**. Lower adoption (6.5K users, 3.6★) is the trade-off. For an India tool, validate India coverage on a test run for whichever you pick.

**`curious_coder/linkedin-jobs-scraper` output fields (S6):** `id`, `link`, `title`, `companyName`, `companyLinkedinUrl`, `companyLogo`, `location`, `salaryInfo` (array of strings), `postedAt`, `benefits`, `descriptionHtml`, `applicantsCount`, `applyUrl`, `descriptionText`, `jobPosterName`, `jobPosterTitle`, `jobPosterPhoto`, `jobPosterProfileUrl`, `seniorityLevel`, `employmentType`, `jobFunction`, `industries`, `companyDescription`, `companyWebsite`, `companyEmployeesCount`.
*(Note: `seniorityLevel` is a LinkedIn enum like "Mid-Senior level" — useful as a coarse seniority signal, but it is **not** numeric years-of-experience.)*

**`harvestapi/linkedin-job-search` output fields (S7):** `id`, `title`, `linkedinUrl`, `jobState`, `postedDate`, `descriptionText`, `descriptionHtml`, `location{text, countryCode, country, state, city}`, `employmentType`, `workplaceType`, `workRemoteAllowed`, `easyApplyUrl`, `applyMethod`, `applicants`, `views`, **`salary{text, min, max, currency, payPeriod, compensationType}`**, `jobFunctions`, `benefits`, `benefitsDataSource`, `expireAt`, `new`, `closedAt`, `contentSource`, `company{id, universalName, linkedinUrl, name, logo, employeeCount, followerCount, description, locations, specialities, industries}`.

### 2.2 Indeed

| Actor | Handle | Price | Maintainer / freshness | Users / MAU / rating | Structured exp? | Structured salary? |
|-------|--------|-------|------------------------|----------------------|-----------------|--------------------|
| **Indeed Scraper** | `misceres/indeed-scraper` (S8) | **from $3.00 / 1,000 listings** | **Apify-maintained**; ~5 days ago | 24K / 2.2K / 3.3★ (59) | ✗ none | ✗ `salary` = free text (often null) |
| **Indeed Job Scraper** | `curious_coder/indeed-scraper` (S9) | **~$0.73 / 1k usage + $20/mo rental** | Community; ~2 months ago | 3.7K / 126 / 4.8★ (47) | ✗ (lives inside `attributes[]`) | ✓ **structured** `salary{min, max, type, currencyCode}` |

**Recommendation (Indeed):** `misceres/indeed-scraper` is the safest default — **the only Apify-first-party job actor found**, frequently updated, 24K users — but its `salary` is free text and there's no experience field. If structured salary matters more than first-party maintenance, `curious_coder/indeed-scraper` returns a clean `salary{min,max,type,currencyCode}` object, but it carries a **$20/month rental** on top of usage and was last updated ~2 months ago. At low volume the rental dominates cost (see Section 3), so `misceres` is the better economic fit for a 1–10 search/day tool.

**`misceres/indeed-scraper` output fields (S8):** `positionName`, `salary` (free text), `jobType`, `company`, `companyLogo`, `location`, `rating`, `reviewsCount`, `url`, `id`, `postedAt`, `scrapedAt`, `description`, `descriptionHTML`, `externalApplyLink`, `isExpired`.

**`curious_coder/indeed-scraper` output fields (S9):** `id`, `title`, **`salary{min, max, type, currencyCode}`**, `jobDescription`, `jobDescriptionHTML`, `originalApplyUrl`, `viewJobLink`, `companyDetails{name, rating, reviewCount, ceoName, …}`, `pubDate`, `expirationDate`, `expired`, `isRepost`, `newJob`, `urgentlyHiring`, `formattedLocation`, `jobLocationCity`, `jobLocationState`, `location`, `jobTypes`, `benefits`, `attributes`, `occupations`, `socialInsurance`, `language`, `trackingKey`, `jobSourceName`.

### 2.3 Naukri  *(the India-critical platform)*

This is where Apify is unexpectedly strong for an India tool: **three separate community actors return structured experience AND structured salary fields.** The brief specifically asked for `minimumExperience` / `maximumExperience` / `salaryDetail` — `epicscrapers/naukri-scraper` returns exactly those names.

| Actor | Handle | Price | Maintainer / freshness | Users / MAU / rating | Structured experience | Structured salary |
|-------|--------|-------|------------------------|----------------------|----------------------|-------------------|
| **Naukri Scraper** | `memo23/naukri-scraper` (S10) | **from $0.60 / 1,000** (Free $0.0015/result; Bronze+ $0.001) | Community (Muhamed Didovic); ~3 days ago | 1.4K / 409 / 3.0★ (11) | ✓ `minimumExperience`, `maximumExperience`, `experienceText` (+ Gulf `DesiredCandidate.Experience{MinExperience, MaxExperience}`) | ✓ Gulf rows `Compensation{MinCtc, MaxCtc, …}` |
| **Naukri Scraper 2026** | `makework36/naukri-scraper` (S11) | **$3.50 / 1K** search; **$9.50 / 1K** w/ details; →$0.65/1K tiered | Community (deusex machine); ~13 days ago | 25 / 8 / 3.0★ (1) | ✓ `experienceMin`, `experienceMax`, `experienceText`, `seniority` | ✓ `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryUsdEstimate` (parses "6-15 Lacs PA") |
| **Naukri Scraper** | `epicscrapers/naukri-scraper` (S12) | **from $1.00 / 1,000** | Community (Epic Scrapers); ~1 month ago | 77 / — / 4.5★ (2) | ✓ `minimumExperience`, `maximumExperience`, `experienceText` | ✓ `salaryDetail{minimumSalary, maximumSalary, currency}` |

**`memo23/naukri-scraper` — full output fields (S10):**

*Naukri (India) rows:* `jobId`, `title`, `shortDescription`, `description`, `staticUrl`, `companyId`, `groupId`, `staticCompanyName`, `companyDetail{name, websiteUrl, address, details, hiringFor, clientType}`, `companyPageUrl`, `clientLogo`, `industry`, `functionalArea`, `jobRole`, `roleCategory`, `locations`, **`minimumExperience`**, **`maximumExperience`**, **`experienceText`**, `employmentType`, `jobType`, `wfhType`, `keySkills`, `applyCount`, `viewCount`, `vacancy`, `createdDate`, `walkIn`, `consultant`, `microsite`, `ambitionBox{companyRating, reviewCount, ratingBreakdown, topReviews}`.

*Naukrigulf rows:* `JobId`, `Designation`, `Description`, `JdURL`, `IndustryType`, `FunctionalArea`, `Location`, `LogoUrl`, `Company{Id, Name, Profile}`, **`Compensation{MinCtc, MaxCtc, Country, CurrentCountry, Vacancies, IsCtcHidden, LatestPostedDate, jobMinCurrency, jobMaxCurrency, userMinCurrency, userMaxCurrency, salaryTimeBrand}`**, `DesiredCandidate{Experience{MinExperience, MaxExperience}, Education, Nationality, Gender, Category, Profile}`, `Contact`, `Other{Keywords, PostedDate, IsPremium, IsTopEmployer, IsWebJob, jobSource, currLabel, isFreeJob, isRecruiterActive, expiringSoon}`.

> ⚠️ Schema caveat for `memo23`: structured **salary** (`Compensation.MinCtc/MaxCtc`) was observed only on the **Naukrigulf** (Gulf) rows, not clearly on the India Naukri rows, whose primary numeric structured fields are experience (`minimumExperience`/`maximumExperience`). If India salary-as-numbers is a hard requirement, `makework36` or `epicscrapers` (which return India `salaryMin/Max` / `salaryDetail`) are the safer choices. **Run a live test before committing.**

**`makework36/naukri-scraper` — output fields (S11):** `jobId`, `jobUrl`, `title`, `companyName`, `companyUrl`, `companyLogoUrl`, `companyRating`, `companyReviewsCount`, `locationText`, `locations`, `workMode`, `address`, **`experienceText`, `experienceMin`, `experienceMax`, `seniority`**, **`salaryText`, `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryUsdEstimate`**, `skills`, `jobDescriptionPreview`, `jobDescription`, `jobDescriptionHtml`, `role`, `roleCategory`, `department`, `industry`, `employmentType`, `educationUG`, `educationPG`, `applicants`, `vacancy`, `applyByDate`, `postedRelative`, `postedDate`.

**`epicscrapers/naukri-scraper` — output fields (S12):** `title`, `companyName`, `jobDescription`, `placeholders`, `tagsAndSkills`, `jobId`, `jdURL`, `companyId`, `logoPath`, `createdDate`, `vacancy`, `ambitionBoxData`, `applyByTime`, **`experienceText`, `minimumExperience`, `maximumExperience`**, **`salaryDetail{minimumSalary, maximumSalary, currency}`**, `currency`.

**Recommendation (Naukri):**
- **Best price + active maintenance:** `memo23/naukri-scraper` ($0.60/1k, updated ~3 days ago, 409 MAU — the most-used of the three). Best for experience-based scoring; verify India salary parsing.
- **Best India structured salary out-of-the-box:** `makework36/naukri-scraper` (`salaryMin`/`salaryMax`/`salaryUsdEstimate` on India rows, parses Lakh strings) — but tiny adoption (25 users) and pricier at base ($3.50/1k search). Adoption/maintenance risk is real.
- **Cleanest field names matching the brief + best rating:** `epicscrapers/naukri-scraper` (`minimumExperience`/`maximumExperience`/`salaryDetail`, 4.5★) at $1/1k, but only 77 users and updated ~1 month ago.

**Plain answer to "does a structured Naukri actor exist?":** **Yes — multiple.** Naukri is well-served on Apify with structured experience and salary fields, which is rare and valuable for an India-focused product. The catch is that all are low-adoption community actors (the largest has ~1.4K users), so resilience to Naukri site changes is the main risk — pick one as primary and keep a second as fallback.

---

## SECTION 3 — REALISTIC MONTHLY COST

**Assumptions (stated explicitly):**
- **Results per search: 75** (mid-point of a reasonable 50–100; tune per platform).
- One "search" = one actor run returning 75 results from one platform. A real user query often hits **all three platforms**, so a "full search" = 3 runs = 225 results.
- Prices used (the cheapest viable structured-or-mature actor per platform, from Section 2):
  - LinkedIn `curious_coder` or `harvestapi`: **$1.00 / 1k** → $0.001/result.
  - Indeed `misceres` (Apify-maintained): **$3.00 / 1k** → $0.003/result.
  - Naukri `memo23`: **$0.60 / 1k** → $0.0006/result.
- Blended cost per result across the 3 platforms = (0.001 + 0.003 + 0.0006) / 3 = **$0.001533/result**.
- Month = 30 days.

### Per-result cost of one full 3-platform search (225 results)
- LinkedIn 75 × $0.001 = $0.075
- Indeed 75 × $0.003 = $0.225
- Naukri 75 × $0.0006 = $0.045
- **Total per full search = $0.345** (~$0.35)

### Monthly cost by search frequency

| Searches/day (full 3-platform) | Runs/mo | Results/mo | **Monthly $** | Fits in $5 free credit? |
|---|---|---|---|---|
| **1/day** | 90 | 6,750 | **~$10.35** | ✗ No (exceeds $5; ~$5.35 over) |
| **3/day** | 270 | 20,250 | **~$31.05** | ✗ No |
| **10/day** | 900 | 67,500 | **~$103.50** | ✗ No |

### If you scope to a single platform per search (75 results/run)

| Platform (price) | 1/day | 3/day | 10/day | 1/day fits $5? |
|---|---|---|---|---|
| LinkedIn $1/1k | $2.25/mo | $6.75/mo | $22.50/mo | ✓ Yes (1/day only) |
| Indeed $3/1k | $6.75/mo | $20.25/mo | $67.50/mo | ✗ No |
| Naukri $0.60/1k | $1.35/mo | $4.05/mo | $13.50/mo | ✓ Yes (1/day **and** ~3/day: 3/day = $4.05 < $5) |

**Reading the math:**
- The **$5 free credit covers roughly 3,250 blended results/month** (≈ $5 / $0.001533). That is enough for **~14 full 3-platform searches per month**, i.e. **about one full search every other day** — *not* one per day.
- **Single-platform Naukri** is the only configuration that comfortably lives inside free credits at meaningful frequency: **3 searches/day = $4.05/mo < $5.** LinkedIn-only fits at 1/day. Indeed is the cost driver at $3/1k.
- Any realistic "all-platforms, daily" usage (1/day = ~$10/mo) **exceeds the free tier** and lands the user on Starter ($29/mo) or pure pay-as-you-go beyond the $5.
- **Lever to stay free:** cap `limit` to 50 (not 75) and drop the pricey Indeed actor or swap Indeed to the cheaper structured option only when needed. 1 full search/day at 50 results, LinkedIn+Naukri only: (50×0.001 + 50×0.0006) × 30 = **$2.40/mo — fits in $5.**

> All figures assume the per-result price already bundles platform usage (true for pay-per-result actors). **Rental actors break this model** — e.g. `curious_coder/indeed-scraper` adds a flat **$20/month** that alone blows the $5 budget regardless of volume, so avoid rental actors for a free-tier product.

---

## SECTION 4 — ToS / LEGAL NOTES

### 4.1 User-token-driven scraping model (BYO-token)
The intended architecture — **each user supplies their own Apify API token** — has clean properties:
- **Billing & liability shift to the user.** The user's own Apify account is billed; the user agrees to Apify's ToS directly. Our tool is an orchestrator, not the scraping operator of record.
- **Send the token as `Authorization: Bearer` server-side** (S3), never in a URL or client-visible log (URLs leak into history/server logs per Apify's own warning).
- **Never persist the token** beyond the request, or store it encrypted at rest with explicit user consent. Treat it like a password.
- This model also sidesteps us having to run/maintain scrapers or proxies — Apify (and the actor developer) own the anti-bot arms race.

### 4.2 hiQ Labs v. LinkedIn — current status  *(verified S14)*
**Final state (as of this writing): the case is closed via a 2022 consent judgment that went *against* hiQ.**
- **April 18, 2022 (9th Cir.):** reaffirmed that the **CFAA's "without authorization" does not apply to public websites** — scraping public data is not a federal computer-fraud crime. This pro-scraping holding **still stands**.
- **December 6, 2022:** hiQ and LinkedIn filed a **stipulated consent judgment**: **$500,000** against hiQ, a finding of hiQ liability for **trespass to chattels** and **misappropriation** (California state-law torts), and a **permanent injunction** barring hiQ from scraping LinkedIn and requiring destruction of scraped data/derived code.
- **Net legal takeaway:** Scraping *public* data is not a CFAA violation, **but** (a) a site's Terms of Service can still be enforced as a **breach-of-contract** claim, and (b) **state-law torts** (trespass to chattels, misappropriation) remain live exposure — that combination is exactly what sank hiQ. The settlement set **no binding precedent**, so the area remains legally unsettled. *(Note: this is US law; it does not govern India or EU usage.)*

### 4.3 Apify's official stance  *(verified S13)*
- "**Web scraping is legal if you scrape data that is publicly available on the internet.**"
- **Personal data is still regulated even when public** — GDPR (EU/UK), CCPA/CPRA (California) can apply regardless of a profile being visible. Apify positions itself as infrastructure; **the user is the data controller/processor** for datasets they build.
- **ToS enforceability** turns on presentation: **browsewrap** (buried footer links) is often unenforceable; **clickwrap** (active "I agree") is enforceable. Under the EU DSM Directive, site owners must opt out of text/data mining via machine-readable signals (e.g. `robots.txt`).
- Apify cites **hiQ v. LinkedIn**'s anti-information-monopoly reasoning as support for the legality of scraping public data in the US.
- **EDPB Opinion 28/2024** (Dec 2024) tightened the analysis for scraping personal data to train/improve AI: legitimate interest is a possible basis only under a strict three-step test, and respecting `robots.txt`/`ai.txt` is a recommended mitigation.

### 4.4 Honest risk summary for an India-focused job tool
- **LinkedIn** is the highest-litigation-risk source; LinkedIn actively pursues scrapers and its ToS prohibits scraping. The **no-cookies** actors (e.g. `harvestapi`) reduce *account-ban* risk for the end user (no login session is used) but do **not** eliminate LinkedIn's contractual/ToS objection to scraping itself.
- **Indeed / Naukri** carry lower public-litigation profiles than LinkedIn, but each has its own ToS; Naukri (Info Edge) is an Indian entity, so **Indian IT Act / contract law and India's DPDP Act 2023** (personal-data protection) are the relevant frameworks, not GDPR/CFAA. **This study did not verify Naukri's specific ToS or Indian-law exposure** — flag for separate legal review (see UNVERIFIED).
- **Data minimization is your best defense:** scrape only the fields needed for matching (title, company, location, experience, salary, JD), avoid harvesting recruiter personal contact fields, don't retain longer than needed, and honor deletion requests. This aligns with both GDPR and DPDP principles.
- **BYO-token helps but is not a legal shield** — it moves first-line liability to the user, but a tool that *facilitates* ToS-violating scraping at scale could still draw scrutiny. Surface a clear disclaimer that users are responsible for complying with each platform's ToS and applicable law.

---

## UNVERIFIED / COULD NOT CONFIRM

The following could not be confirmed against a primary live source and should be treated as inferred or open:

1. **Free-credit-on-paid-actors — partially inferred.** The `usage-and-resources` and `actors-in-store` docs (S4, S5) confirm rental/per-result fees draw from the *same prepaid platform-usage balance* as CUs, which strongly implies the $5 free credit covers them. But **no single page stated verbatim "the $5 free credit can be spent on pay-per-result actors."** Treat the "$5 covers paid actors" claim in Sections 1.5/3 as a well-supported inference, not a direct quote.
2. **Whether per-result actor prices bundle platform usage in every case.** S5 says "most" pay-per-event actors include platform usage; some charge it separately. The Section 3 cost model assumes bundling. **For any specific actor, confirm on its pricing tab** whether CUs/proxy are extra — if not, real cost is higher than modeled.
3. **`memo23/naukri-scraper` India-row salary.** Structured `Compensation.MinCtc/MaxCtc` was observed on **Naukrigulf** rows; it was **not confirmed** that India Naukri rows carry numeric structured salary (their confirmed structured numerics are experience). Verify with a live India run before relying on Naukri salary-as-numbers from this actor.
4. **Exact `run-sync-get-dataset-items` path segment (`acts` vs `actors`).** Docs show `/v2/acts/:actorId/...`; Apify also resolves `/v2/actors/...`. The handle separator encoding (`/` → `~`) is from Apify convention and was **not re-screenshotted** on the endpoint page in this session — verify when implementing.
5. **All actor metrics are point-in-time.** User counts, MAU, ratings, "last modified" dates, and per-result prices for every actor (S6–S12) were read on 2026-06-09 and **will drift**. Re-verify before launch. In particular, community actors can be deprecated or change price unilaterally.
6. **Naukri / Indeed / India-specific ToS and DPDP Act 2023 exposure** — **not researched.** Section 4 covers US (hiQ/CFAA) and EU (GDPR) plus Apify's general stance; it does **not** establish the legality of scraping Naukri under Indian law. This needs dedicated India legal review.
7. **Indeed `curious_coder` "$0.73/1k"** is described on its page as a **historical-average usage estimate**, not a fixed price, and sits on top of a **$20/mo rental** — actual per-run cost varies with run efficiency. Treated as approximate.
8. **Search-result price discrepancies were resolved in favor of the live actor pages.** A third-party aggregator (use-apify.com) cited `curious_coder/linkedin-jobs-scraper` at "$3/1k"; the **live actor page (S6) showed $1.00/1k**, which is what this document uses. Other aggregator numbers were similarly superseded by direct page fetches where they conflicted.
