# Job Finder India

**The job-search tool that tells you the truth about fit.**

Most "AI job match" tools are optimists. They are built to get you to apply —
so a 70%-there role becomes a "4.7/5, great match, here's how to frame your
gaps." That wastes your time and the recruiter's.

Job Finder India is the opposite. It scores a job against your resume on a full
**0–5** scale and **says "no" when it's a no.** A gap in years, function, or
domain is a *disqualifier*, not "something to frame around." Every score cites
the exact resume line and the exact job requirement behind it, so you can check
the reasoning yourself. The goal is **fewer, better applications** — the ones
you'd actually get.

It is free, open source, and runs entirely on your machine. **Your resume and
your search history never leave your computer**, and the app holds **no AI API
key** — scoring runs through whatever AI CLI you already use.

> Built for the Indian market first: scores on CTC/LPA, notice period, and
> experience bands, and reaches India-native boards (Naukri) the Western tools
> ignore.

---

## How it's different

| | Keyword scanners (Jobscan, Naukri Relevance) | Optimistic AI matchers | **Job Finder India** |
|---|:--:|:--:|:--:|
| Holistic LLM judgment (not keyword count) | ✗ | ✓ | ✓ |
| **Says "don't apply" when it's a no** | n/a | ✗ (spins gaps) | ✓ |
| Gaps treated as disqualifiers | ✗ | ✗ | ✓ |
| Every score cites resume line + JD line | ✗ | rarely | ✓ |
| Runs locally, data never leaves machine | ✗ | ✗ | ✓ |
| No AI API key held by the app (use your own CLI) | ✗ | ✗ | ✓ |
| India-native (CTC, notice, Naukri) | partial | ✗ | ✓ |
| Learns from your "wouldn't apply" corrections | ✗ | ✗ | ✓ (feedback loop) |

---

## How scoring works (no API key, by design)

Scoring is a **markdown rubric** in [`prompts/`](prompts/) executed by an AI CLI
**you** already have — Claude Code, Gemini CLI, Codex, Qwen, OpenCode, Aider,
and others. job-finder detects your CLI and drives it in headless mode; the
rubric does the judging.

This is deliberate. The free tiers of these tools shifted four times in two
months (see [docs/research/03](docs/research/03_cli_and_api_economics.md)), so
binding the product to one provider would be fragile. Default-less is the only
durable posture — and it means **no scoring key lives in this app.** For a
genuinely $0, offline, private setup, point a local-capable CLI (Codex `--oss`,
Qwen, OpenCode, or Aider) at a local Ollama model.

```
resume + profile ──▶ DISCOVERY ──▶ dedup + pre-filter ──▶ HONEST SCORING ──▶ ranked top-N
                     (your jobs)                          (your AI CLI runs    (+ citations,
                                                           prompts/_rubric.md)  "apply / don't")
```

## Discovery — layered and legitimate

Discovery is plumbing, kept boring and legitimate. **No stealth, no bot-evasion,
no anonymous proxy scraping** — ever. Channels, in priority order (all feed one
dedup → India/keyword filter → cap-40 prescreen funnel):

1. **Public ATS scan (always-on floor, free, zero key).** Reads the public JSON
   APIs of Greenhouse / Ashby / Lever / Workable / Workday / SmartRecruiters for a
   curated list of India-relevant companies. Clean, reliable, never gated.
2. **Adzuna (co-primary India-native, free tier).** The official Adzuna API
   (`country=in`) — documented, ToS-clean, no scraping. Free app id/key from
   developer.adzuna.com. This is the default India-native channel.
3. **JSearch (supplement, gap-fill).** OpenWeb Ninja's Google-for-Jobs index
   (LinkedIn / Naukri / Indeed surfaced). It overlaps Adzuna, so it is spent
   **only when Adzuna comes back thin** — conserving its scarcer free tier
   (~200 req/month). RapidAPI or the OpenWeb Ninja direct portal.
4. **Google Jobs (optional, off).** Same Google-for-Jobs data as JSearch, via your
   own SerpAPI/Serper key. Off by default (redundant with JSearch).
5. **Apify deep mode (opt-in, off by default).** The FULL-JD Naukri/LinkedIn/Indeed
   scrape, for when you want depth over breadth. BYO Apify token; runs bill to your
   account; you accept the board's ToS directly. If credits run out (or a
   quota/timeout hits) it **auto-pauses**, says so, and the run continues on the
   free channels — it never hard-fails; the next run's cheap probe auto-resumes it.

**Free-tier safety.** Adzuna and JSearch each have a per-run request cap and a
persisted monthly counter (`config/run.yml` → `discovery`). When a monthly free
tier is exhausted — or an API returns a 429 — that channel pauses and discovery
degrades to the ATS floor + others. A new calendar month resets it. Every run
labels each job with its source channel and prints the remaining monthly quota.

If a channel returns nothing, job-finder says so plainly. It never fabricates a
result and never silently degrades.

## Run it inside your own AI CLI (prompt-pack — primary mode)

Open this repo in the AI CLI you already use (**Claude Code / Codex / OpenCode /
Qwen / Antigravity** — legacy Gemini → Antigravity). **What to type:** once it's open,
just say **`find me jobs`** (or `get started` on a first run). That's the whole interface.
The CLI reads [`AGENTS.md`](AGENTS.md) (canonical) + [`modes/`](modes/) — entry via
the skill router [`.agents/skills/job-finder-india/SKILL.md`](.agents/skills/job-finder-india/SKILL.md) —
and drives the flow: a deterministic cold-start check, conversational onboarding
(it **asks for your résumé and writes the files for you** — you never hand-create them),
then it calls small Python tools for the plumbing and **scores the bounded set
in-session with its own model** — no API key held by the app, no headless token.

> **Use a capable model.** Scoring happens *in-session*, so the model you pick is the
> scorer. On **GitHub Copilot, choose GPT-5 or Claude (Sonnet/Opus) — not "Auto"** (which
> may route to `gpt-5-mini`). Avoid small/default tiers (`gpt-5-mini`/`nano`, Haiku-tier):
> they give less reliable verdicts and can lose the multi-step flow. `doctor` prints this tip too.
(Architecture, UX, and flow mirror [career-ops](https://github.com/santifer/career-ops);
the India scoring rubric, prescreen cap, and Apify spend-safety are ours.)

```
your CLI ──reads──► AGENTS.md + modes/{onboarding,evaluate,scan}.md
        ──calls──►  python -m jobfinder doctor|discover|prescreen|enrich|tracker   (deterministic tools)
        ──does───►  the honest scoring itself, in-session (prompts/_rubric.md is the law)
```
Tools: `doctor --json` (gate) · `discover --json` · `prescreen --json` (the volume cap) ·
`enrich <job_id>` · `tracker --add -` · `live <job_id>` (posting still active? — adopted
from career-ops). Outputs: `data/results/top.md` (fit-first) + `data/tracker.md`.

> **Status — multi-LLM: verified.** The pack is CLI-agnostic (Bash + files) and has run
> the full flow in-session on **Claude** and **GitHub Copilot** (a non-Claude model —
> doctor → discover → prescreen → in-session scoring with citation-backed JSON, seniority/
> function gates held). `opencode` / `codex` / `qwen` run interactively once authed;
> Antigravity is a desktop app. Confirm on your CLI by opening it here and saying *"find
> me jobs."* (Headless runs need each CLI's auto-approve flag — e.g. Copilot's
> `--allow-all-tools`.)

## Standalone / CI (headless fallback)

```bash
git clone https://github.com/harshgarg95/job-finder-india && cd job-finder-india
pip install -r requirements.txt
python -m jobfinder doctor                 # setup check
python -m jobfinder onboard                # guided setup
python -m jobfinder --resume resume.md --cli claude   # headless top-N (CI/batch; needs setup-token)
```

Either way you get a ranked top-N with, for each job: an honest 0–5 score, an
apply/don't-apply call, and the resume-line ↔ JD-requirement citations behind it.

**Volume safety by design.** Before any LLM call, a deterministic prescreen
(title / seniority / function / hard-constraints) cuts the candidate set to a
bounded few dozen — capped by `config/run.yml` → `prescreen.max_llm_jobs`. Every
run prints the funnel (`raw → candidates → prescreened → scored`) and, for hosted
CLIs, the per-call cost. A run can never balloon into thousands of calls.

## The feedback loop (the part that gets smarter)

job-finder learns from your corrections — no statistical ML, just files. When you
tell it a result was wrong, that correction **persists and retunes future
scoring**: rejected jobs are suppressed, and your corrections replay into the
scorer as binding lessons. (career-ops's own issue #35 notes nobody built this.)

```bash
python -m jobfinder dashboard      # local tracker UI at http://127.0.0.1:8755
```

The dashboard (Python stdlib, **local-only**) shows your **APPLY / STRETCH**
shortlist (DON'T-APPLY roles are hidden behind a "show filtered" toggle for
auditing). Each role has two one-click calls, saved to `data/feedback.md` and
applied on the next run:
- **✓ Applied** — you applied → tracked application, **not re-recommended**.
- **✗ Wouldn't apply** — pick a reason (wrong location / level / function /
  domain / comp too low, or "just passing") → suppresses it and retunes scoring.

Changed your mind? Every call has a **change/undo** — the latest choice per job
wins. Each scored role also shows a deterministic **auto-checked skills** line
(from the local skills taxonomy) next to the LLM's qualifications breakdown. Prefer the terminal?
`python -m jobfinder feedback --job <id> --action wrong_location --note "Bengaluru"`.

Two scoring-robustness details worth knowing:
- **Full-JD scoring.** A matching title isn't a matching candidate. job-finder
  deep-fetches the *full* posting (with a headless-browser fallback for JavaScript
  career pages) so it scores the real requirements — including the buried "needs
  8 yrs X / a CS degree / hands-on Y" lines that get applicants auto-rejected.
- **Conservative scoring.** Each job is scored several times and the *most
  conservative* result is kept — an honest tool errs toward "skip" over wasting
  your application on a false match.

## Privacy & ethics

- **Local-first.** Everything runs on your machine. See [DATA_CONTRACT.md](DATA_CONTRACT.md).
- **No auto-apply, ever.** job-finder recommends; you decide and act. It never
  clicks Submit.
- **No spray-and-pray.** It is a filter, not a firehose.
- **No invented experience.** A high score is earned by evidence in your resume,
  never assembled by reframing.

## Credits & prior art

Job Finder India stands openly on good prior art and reimplements its patterns from
scratch (no copied files):

- **[career-ops](https://github.com/santifer/career-ops)** (MIT) — the
  CLI-agnostic markdown-prompt scoring model, the rubric-with-citations idea,
  and the User-Layer/System-Layer data contract are inspired by career-ops.
  job-finder deliberately *inverts* its optimistic scoring: where career-ops
  coaches you to apply, job-finder is built to tell you the honest "no."
- **[Apify](https://apify.com)** — the optional BYO-token discovery layer for
  India boards. Credit to the actor authors we point users to (`epicscrapers`,
  `memo23`, `harvestapi`, `misceres`).

These are independent projects; Job Finder India is not affiliated with or endorsed by
them. Their names belong to them.

## License

[MIT](LICENSE) © 2026 Harsh Garg.
