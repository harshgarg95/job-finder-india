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
