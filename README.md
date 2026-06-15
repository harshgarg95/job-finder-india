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
no anonymous proxy scraping** — ever. Channels, in priority order:

1. **Public ATS scan (default, free, zero key).** Reads the public JSON APIs of
   Greenhouse / Ashby / Lever / Workable for a curated list of India-relevant
   companies. Clean and reliable.
2. **Google Jobs (optional).** Indirect coverage of LinkedIn-surfaced and other
   board listings via Google's index. Bring your own SerpAPI/Serper key.
3. **Apify, BYO-token (optional, off by default).** Closes the India gap
   (Naukri) the first two channels miss. You supply your own Apify token; runs
   bill to your account; you accept the board's ToS directly.

If a channel returns nothing, job-finder says so plainly. It never fabricates a
result and never silently degrades.

## Quick start

```bash
git clone https://github.com/harshgarg95/job-finder-india
cd job-finder
pip install -r requirements.txt          # discovery + resume-parsing deps only

cp config/profile.example.yml config/profile.yml   # edit: your seniority, function, comp
# (optional) cp .env.example .env                   # only for Google Jobs / Apify channels

# Make sure you have ONE AI CLI installed (claude / gemini / codex / qwen / opencode / aider …)
python -m jobfinder --resume path/to/your_resume.pdf
```

You get a ranked top-N with, for each job: an honest 0–5 score, an
apply/don't-apply call, and the resume-line ↔ JD-requirement citations behind
it.

## The feedback loop (the part that gets smarter)

job-finder learns from your corrections — no statistical ML, just files. When you
tell it a result was wrong, that correction **persists and retunes future
scoring**: rejected jobs are suppressed, and your corrections replay into the
scorer as binding lessons. (career-ops's own issue #35 notes nobody built this.)

```bash
python -m jobfinder dashboard      # local tracker UI at http://127.0.0.1:8755
```

The dashboard (Python stdlib, **local-only**) shows your scored shortlist with the
verified JD link and one-click corrections — *Good match · Applied · Wouldn't
apply · Wrong location / level / function / domain*. Each click is saved to
`data/feedback.md` and applied on the next run. Prefer the terminal?
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
