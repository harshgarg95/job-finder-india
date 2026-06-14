# 03 — CLI & API Economics: The CLI-Agnostic Landscape for an India-Focused AI Job-Search Tool

**Purpose.** This is a permanent reference document for a ground-up rebuild of an India-focused, **CLI-agnostic** AI job-search tool. The tool will ship with **no default AI provider** — the user picks their own CLI (Claude Code, Gemini CLI, Codex, etc.) and the tool drives it in headless mode to score jobs against a resume. This document maps the CLI/model landscape and what "free" really means for each.

**Date of research:** 2026-06-09. Every pricing number, free-tier limit, and date below was fetched live from an official or primary source on this date. Where a fact could only be found in third-party reporting, it is explicitly flagged. Pricing, free tiers, and rate limits change constantly — **treat every number as a snapshot, re-verify before relying on it.**

**Methodology / verification rule.** No number is stated from memory. Each claim cites the exact URL it came from. Two date-sensitive changes were given special scrutiny (the June 15 2026 Anthropic Agent SDK credit change and the June 18 2026 Gemini CLI → Antigravity migration) and both were confirmed against **official first-party sources** (Anthropic Help Center and Google Developers Blog / official GitHub discussion, respectively).

---

## Sources verified (every URL fetched on 2026-06-09)

**Anthropic / Claude Code**
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan — OFFICIAL Anthropic Help Center: the June 15 2026 Agent SDK credit change (authoritative)
- https://code.claude.com/docs/en/headless — OFFICIAL Claude Code docs: `claude -p` headless mode (redirect target of docs.anthropic.com/en/docs/claude-code/headless)
- https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan — OFFICIAL: Claude Code on Pro/Max (interactive usage)

**Google / Gemini CLI / Antigravity**
- https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ — OFFICIAL Google Developers Blog: Gemini CLI → Antigravity CLI transition
- https://github.com/google-gemini/gemini-cli/discussions/27274 — OFFICIAL repo discussion: transition details
- https://github.com/google-gemini/gemini-cli — OFFICIAL Gemini CLI README: free-tier quotas + `-p` headless
- https://geminicli.com/docs/resources/quota-and-pricing/ — Gemini CLI docs site: quota/pricing table
- https://github.com/google-gemini/gemini-cli/discussions/24166 — community discussion on local/Ollama support (no maintainer commitment visible)
- https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/ — OFFICIAL: Antigravity launch (model support, free preview)
- https://cloud.google.com/blog/topics/developers-practitioners/choosing-antigravity-or-gemini-cli — OFFICIAL Google Cloud blog: Antigravity vs Gemini CLI

**OpenAI / Codex CLI**
- https://developers.openai.com/codex/cli/ — OFFICIAL: Codex CLI, `codex exec` non-interactive
- https://developers.openai.com/codex/config-advanced — OFFICIAL: `--oss` local models (Ollama / LM Studio), `model_providers` config
- https://developers.openai.com/codex/pricing — OFFICIAL: per-plan usage limits
- (help.openai.com/en/articles/11369540 returned HTTP 403 to the fetcher; content corroborated via OpenAI search index)

**Alibaba / Qwen Code**
- https://github.com/QwenLM/qwen-code — OFFICIAL repo: `-p` headless, multi-provider, local Ollama/vLLM
- https://github.com/QwenLM/qwen-code/issues/3203 — OFFICIAL repo issue: "Qwen OAuth Free Tier Policy Adjustment" (free tier reduced then discontinued)

**OpenCode (SST)**
- https://github.com/sst/opencode — OFFICIAL repo
- https://opencode.ai/docs/ — OFFICIAL docs: provider-agnostic
- https://opencode.ai/docs/cli/ — OFFICIAL docs: `opencode run` / `opencode serve` headless, `--format json`

**GitHub Copilot CLI**
- https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli — OFFICIAL: `-p`/`--prompt` headless, `--allow-tool`, `--model`
- https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/ — OFFICIAL: June 1 2026 AI Credits switch
- https://github.blog/changelog/2026-04-20-changes-to-github-copilot-plans-for-individuals/ — OFFICIAL changelog: Apr 20 2026 individual-plan changes
- https://docs.github.com/en/copilot/get-started/plans — OFFICIAL: plan prices

**Aider**
- https://github.com/Aider-AI/aider — OFFICIAL repo: Apache-2.0, BYO-key
- https://aider.chat/docs/llms.html — OFFICIAL docs: providers incl. Ollama
- https://aider.chat/docs/scripting.html — OFFICIAL docs: `-m`/`--message` scripting + Python API

**Cursor CLI**
- https://cursor.com/docs/cli/headless — OFFICIAL: `-p`/`--print`, `--output-format`, `--force`/`--yolo`
- (cursor.com/pricing, cursor.com/docs/cli/using — corroborating, via search index)

**Amazon Q Developer CLI**
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-tiers.html — OFFICIAL: Free vs Pro tiers, CLI availability
- https://aws.amazon.com/q/developer/pricing/ — OFFICIAL: 50 agentic requests/mo free, $19/user Pro

**Moonshot / Kimi CLI**
- https://github.com/MoonshotAI/kimi-cli — OFFICIAL repo (evolving into MoonshotAI/kimi-code)
- https://moonshotai.github.io/kimi-cli/en/reference/kimi-command.html — OFFICIAL docs: `-p`/`--prompt`, `--print`, `--quiet`, `-m`, `kimi acp`
- https://moonshotai.github.io/kimi-cli/en/guides/getting-started.html — OFFICIAL docs: OAuth / API-key auth
- https://moonshotai.github.io/Kimi-K2/ — OFFICIAL: Kimi K2 models, Modified MIT license

---

## 1. Claude Code (Anthropic)

**What it is.** Anthropic's first-party coding agent CLI. Interactive in the terminal, plus a non-interactive "headless" mode that is the Agent SDK exposed via the CLI.

**(a) Free-tier reality.** There is **no free tier**. Claude Code runs either on a paid Claude subscription (Pro / Max 5x / Max 20x) or on a pay-as-you-go API key. A **credit card / paid plan is required.** Interactive Claude Code on a Pro/Max plan draws from the normal subscription usage limits (source: https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan).

**(b) Headless / scriptable mode — YES, this is the key mode for our tool.** The flag is **`claude -p` (alias `--print`)**. It reads stdin, prints to stdout, and supports `--output-format text|json|stream-json`, `--json-schema` for structured output, `--allowedTools`, `--append-system-prompt`, `--continue`/`--resume`, and a `--bare` mode for deterministic CI runs (source: https://code.claude.com/docs/en/headless). Example, verbatim from the docs:
```bash
cat build-error.txt | claude -p 'concisely explain the root cause of this build error' > output.txt
```
For job scoring, `claude -p "<resume + job>" --output-format json --json-schema '{...}'` returns a structured score in the `structured_output` field. This is an excellent fit for our headless scoring use case.

**(c) Imminent change — CONFIRMED, June 15 2026 (official).** Source: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan. Verbatim: *"Starting June 15, 2026, Claude Agent SDK and `claude -p` usage no longer counts toward your Claude plan's usage limits."* Specifics:
- **What moves to the new pool:** Agent SDK (Python/TS), `claude -p` non-interactive mode, Claude Code GitHub Actions, and third-party apps authenticated via the Agent SDK.
- **New monthly Agent SDK credit (metered at full API list prices, no rollover):** Pro **$20**, Max 5x **$100**, Max 20x **$200**, Team Standard seat **$20**, Team Premium seat **$100**, Enterprise usage-based **$20**, Enterprise seat-based Premium **$200**.
- **On depletion:** *"additional Agent SDK usage flows to usage credits at standard API rates—but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes."*
- **Unchanged (stays on subscription):** interactive Claude Code in the terminal, Claude Cowork, and Claude.ai chat.
- **API-key users:** *"nothing changes. Pay-as-you-go billing continues, and you don't receive an Agent SDK monthly credit."*
- **Action required:** one-time claim — *"You claim your credit through your Claude account once. After that, it refreshes automatically each cycle."*

> **Implication for our tool:** Because our tool drives `claude -p` headlessly, **a subscription user's job-scoring runs will draw from the small separate Agent SDK credit pool (e.g. $20/mo on Pro), NOT their main subscription** — and at full API rates. This makes Claude Code via subscription a *bounded* free-ish allowance, not unlimited. API-key users are unaffected (normal pay-as-you-go). The docs themselves carry this notice inline on the headless page.

**(d) BYO / local model.** Claude Code is Anthropic-model-only for its hosted use, but the CLI can route to **Amazon Bedrock, Google Vertex, and Microsoft Foundry** using provider credentials (referenced in the headless `--bare` docs). **No local Ollama support** — it is not a BYO-any-model client.

---

## 2. Gemini CLI (Google)

**What it is.** Google's open-source (Apache-2.0) terminal coding agent. **Being sunset in favor of Antigravity CLI (see §7).**

**(a) Free-tier reality — currently generous.** Logging in with a personal Google account gives **60 requests/min and 1,000 requests/day**, **no API key and no credit card** required (source: https://github.com/google-gemini/gemini-cli README). The model is chosen across the Gemini family by the CLI; the current README references **"Gemini 3 models"** with a 1M-token context (note: model naming has moved on — `gemini-3-pro-preview` was discontinued 2026-03-26 in favor of `gemini-3.1-pro-preview`, per Google Cloud release notes). Alternative free paths from the quota page (https://geminicli.com/docs/resources/quota-and-pricing/): unpaid Gemini API key = **250 requests/user/day (Flash only)**; Vertex AI Express = 90 days before billing. Paid: Google AI Pro = 1,500/day, Ultra = 2,000/day.

> **This 1,000 req/day free tier is the single most generous "no-card" allowance of any first-party CLI here — but it is being shut off on June 18 2026 (see (c)).**

**(b) Headless / scriptable mode — YES.** The flag is **`gemini -p "<prompt>"`** with `--output-format json` and `--output-format stream-json` for structured/streamed output (source: README). Example, verbatim: `gemini -p "Explain the architecture of this codebase"`. `-m gemini-2.5-flash` selects a model. Good fit for headless scoring.

**(c) Imminent change — CONFIRMED, June 18 2026 (official).** Sources: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ and https://github.com/google-gemini/gemini-cli/discussions/27274. Verbatim from the blog: *"On June 18, 2026, Gemini CLI and Gemini Code Assist IDE extensions will stop serving requests"* for free and Google AI Pro/Ultra users. Details:
- **Announced:** May 19, 2026.
- **Who loses service June 18 2026:** free tier, Google AI Pro, Google AI Ultra, and individual Gemini Code Assist (free/Pro/Ultra). Gemini Code Assist for GitHub: no new installs after that date, service stops shortly after.
- **Who keeps it:** **Enterprise** customers via Gemini Code Assist Standard/Enterprise license or paid Gemini API keys — *"access continues with paid Gemini API keys."*
- **The repo stays open source:** *"The project remains available to the community as an Apache 2.0 licensed repository with no changes."* (i.e. the binary keeps working with your **own paid Gemini API key**, but the **free OAuth 1,000/day entitlement is what ends**.)
- **Replacement:** Antigravity CLI — a Go rewrite (see §7).

> **Implication:** After 2026-06-18, "Gemini CLI as a free scorer" effectively dies for individuals. The open-source binary survives only if the user supplies a paid API key (or the 250/day unpaid Flash key). The free-as-in-1000/day path moves to Antigravity's much smaller compute cap.

**(d) BYO / local model — NO (officially).** The official Gemini CLI supports **only Google Gemini models** plus a limited on-device path (LiteRT-LM); it does **not** officially support Ollama / LM Studio / generic OpenAI-compatible endpoints. Community has repeatedly requested it (e.g. https://github.com/google-gemini/gemini-cli/discussions/24166, issue #5938) and there are community forks that add it (**LLxprt Code**, **Easy LLM CLI**), but those are not first-party. *(Flag: one secondary source claims Google "closed all discussions/PRs" for multi-model support; I could not confirm that exact statement from a single maintainer comment — what IS verifiable is that the official README/docs list no local-provider support.)*

---

## 3. Codex CLI (OpenAI)

**What it is.** OpenAI's open-source (Rust) terminal coding agent.

**(a) Free-tier reality.** Codex is included across **Free, Go, Plus, Pro, Business, Edu, Enterprise** ChatGPT plans (source: https://developers.openai.com/codex/pricing). The **Free plan** lists Codex as available for "quick coding tasks" but **does not publish a specific number** for its allowance. Paid limits are published per 5-hour window, e.g. **Plus: ~15–80 local messages / 5 hr** (model-dependent: GPT-5.4 20–100, GPT-5.4-mini 60–350, GPT-5.3-Codex 30–150); **Pro 5x: 80–400**, **Pro 20x: 300–1,600** (GPT-5.5). *"The usage limits for local messages and cloud tasks share a five-hour window. Additional weekly limits may apply."* Sign-in is **ChatGPT account or API key**. (Card needed: a paid ChatGPT plan or API billing is required for meaningful use; the Free plan exists but its exact cap is unpublished — see UNVERIFIED.)

**(b) Headless / scriptable mode — YES.** The subcommand is **`codex exec`** — *"Automate repeatable workflows by scripting Codex with the `exec` command"* (source: https://developers.openai.com/codex/cli/). There is also a Codex SDK, an App Server, and a GitHub Action for programmatic use. Good fit for headless scoring.

**(c) Imminent change.** None specific to Codex CLI verified as of 2026-06-09. (Model lineup has advanced to the GPT-5.4 / GPT-5.5 / GPT-5.x-Codex family per the pricing page; this is ongoing iteration, not a discrete breaking change.)

**(d) BYO / local model — YES.** Codex supports local/open-source providers via the **`--oss` flag** (source: https://developers.openai.com/codex/config-advanced). `oss_provider` defaults the backend; **Ollama** and **LM Studio** are built-in. Config example, verbatim from docs:
```toml
oss_provider = "ollama"   # or "lmstudio"
[model_providers.local_ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
```
Custom OpenAI-compatible endpoints supported via `[model_providers.*]` with `base_url` + `env_key`. **This makes Codex CLI a viable fully-offline / fully-free scorer when pointed at a local model.**

---

## 4. Qwen Code (Alibaba / Qwen)

**What it is.** Open-source terminal coding agent optimized for Qwen models (a Gemini-CLI-lineage fork).

**(a) Free-tier reality — the free OAuth tier was DISCONTINUED.** Source: https://github.com/QwenLM/qwen-code/issues/3203 ("Qwen OAuth Free Tier Policy Adjustment", official repo). The free Qwen OAuth tier was **1,000 requests/day**, then **reduced to 100 requests/day on 2026-04-13**, then the **free OAuth entry point was closed on 2026-04-15**. To keep using Qwen Code you now bring a paid key: **Alibaba Cloud ModelStudio Coding Plan, OpenRouter, or Fireworks AI** (a card / paid key is now required for the hosted Qwen path). *(Note: the prompt's hypothesized "2,000 requests/day" free tier is not what the official issue states — it was 1,000/day before the cuts.)*

**(b) Headless / scriptable mode — YES.** **`qwen -p '<prompt>'`** runs non-interactively for scripts/CI (source: repo README).

**(c) Imminent change.** The free-tier discontinuation (Apr 13–15 2026) already happened. No further discrete change verified. Models referenced in the README include Qwen3-Coder variants (480A35, 30BA3B) plus newer Qwen3.x-Plus releases.

**(d) BYO / local model — YES.** Supports **OpenAI / Anthropic / Gemini-compatible APIs**, plus Alibaba Cloud / OpenRouter / Fireworks, and **local models via Ollama and vLLM** with *"no API key or cloud account needed"* (source: repo README). **Viable fully-offline scorer with a local Qwen model.**

---

## 5. OpenCode (the open-source CLI, by SST)

**What it is.** A provider-agnostic, open-source terminal coding agent (https://github.com/sst/opencode; docs at opencode.ai). *(Note: the repo has been hosted under both `sst/opencode` and an `anomalyco/opencode` org name in different snapshots; opencode.ai is the canonical project site. Star count and exact org are in flux — treat as the same project.)*

**(a) Free-tier reality.** **OpenCode itself is free and open source.** It has **no built-in model allowance** — it is BYO. Cost = whatever your chosen provider charges. With a free/local model it is $0; there is a curated "OpenCode Zen" list of tested models. No credit card required for the tool; a card is only needed if you choose a paid provider.

**(b) Headless / scriptable mode — YES, strong.** Source: https://opencode.ai/docs/cli/.
- **`opencode run "<message>"`** — one-shot, no TUI (e.g. `opencode run "Explain the use of context in Go"`).
- **`opencode serve`** — headless HTTP API server for programmatic access.
- **`--format json`** for raw JSON event output; `--model provider/model`, `--session [id]`, `--attach [url]`.
Excellent fit for headless scoring and for a long-running server the tool can call.

**(c) Imminent change.** None verified.

**(d) BYO / local model — YES.** *"With OpenCode you can use any LLM provider by configuring their API keys"* (https://opencode.ai/docs/). Provider-agnostic across Anthropic/OpenAI/Google/OpenRouter and **local models** (via the models.dev catalog / OpenAI-compatible endpoints). **Viable fully-offline scorer.**

---

## 6. GitHub Copilot CLI

**What it is.** GitHub's terminal interface to Copilot (Linux/macOS/Windows).

**(a) Free-tier reality.** **Copilot Free** exists with **no credit card** and includes (pre-existing public number) **2,000 code completions/month** plus a monthly allotment of GitHub AI Credits and access to a selection of models. **As of June 1 2026, all plans moved to usage-based billing** — premium request units (PRUs) were **replaced by GitHub AI Credits** (source: https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/). Verbatim: *"Code completions and Next Edit suggestions remain included in all plans and do not consume AI Credits."* Paid: **Pro $10/mo (incl. $10 AI Credits)**, **Pro+ $39/mo (incl. $39 AI Credits)**, Business $19/seat, Enterprise $39/seat (source: https://docs.github.com/en/copilot/get-started/plans). Note: as of the Apr 20 2026 changelog, **new self-serve signups for Pro/Pro+/Student were paused** and **Opus was removed from Pro** (kept on Pro+).

**(b) Headless / scriptable mode — YES.** Source: https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli. *"To use the CLI programmatically, include the `-p` or `--prompt` command-line option."* Supports piping and `--allow-tool`; `--model` / `/model` switches models. Verbatim example: `copilot -p "Show me this week's commits and summarize them" --allow-tool='shell(git)'`. Good fit for headless scoring (chat/agentic use **does** consume AI Credits, unlike completions).

**(c) Imminent change — the usage-based-billing switch (June 1 2026) already landed.** Ongoing: paused signups + model-availability changes (Apr 20 2026). No further discrete future date verified.

**(d) BYO / local model — NO.** Copilot CLI uses GitHub-hosted models only; no Ollama / local support.

---

## 7. Antigravity CLI (Google) — and its relationship to Gemini CLI

**What it is.** Google **Antigravity** is an "agentic development platform" (an agent-first IDE + Agent Manager + integrated browser), launched **2025-11-20** (source: https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/). The **Antigravity CLI** is its terminal UI — *"the most lightweight way to invoke, monitor, and interact with Antigravity agents, directly from your terminal,"* sharing the same agent harness/settings as the Antigravity 2.0 desktop app (source: https://cloud.google.com/blog/topics/developers-practitioners/choosing-antigravity-or-gemini-cli).

**Relationship to Gemini CLI:** Antigravity CLI is the **official successor** to Gemini CLI for individuals. Per the transition blog (§2c), Gemini CLI stops serving free/Pro/Ultra requests on **2026-06-18** and Google directs those users to Antigravity CLI (a closed-source Go rewrite carrying over Skills, Hooks, Subagents, and Extensions-as-plugins). The Gemini CLI Apache-2.0 repo remains, but the **free entitlement migrates to Antigravity**.

**(a) Free-tier reality.** *"Available today in public preview, at no cost for individuals"* (official). Paid options: **$20/mo Google AI Pro**, **$100/mo Google AI Ultra** (lighter tier), **$200/mo Google AI Ultra** (top tier; reduced from $250). **The exact free-tier compute/request cap is NOT published in an official page I could fetch** — Antigravity uses a **weekly compute-based cap** rather than Gemini CLI's flat 1,000/day, and **multiple third-party reports place the free tier near ~20 requests/day with weekly cooldowns** (e.g. xda-developers, agentpedia). **FLAGGED as community-reported, not officially confirmed** (the antigravity.google pricing/blog pages are JavaScript-rendered and returned no readable numbers to the fetcher). Credit card not required for the free public preview (no official statement found either way; flagged).

**(b) Headless / scriptable mode.** The Antigravity CLI is primarily a **TUI** for driving agents; an **Antigravity SDK** exists (antigravity.google/blog/introducing-google-antigravity-sdk) for programmatic use. Google's own comparison positions **Gemini CLI** as the tool to *"use … if you want a terminal CLI or need headless execution,"* implying Antigravity CLI's non-interactive story is **less mature / not a drop-in `-p` replacement at launch.** **FLAGGED:** I could not fetch an official Antigravity CLI flag reference (docs are JS-rendered); a confirmed headless one-shot flag is **UNVERIFIED**.

**(c) Imminent change.** Antigravity IS the change — it absorbs Gemini CLI's individual users on **2026-06-18** (confirmed, §2c). Antigravity itself is in public preview and its quotas have reportedly been cut since the Nov 2025 launch (community-reported).

**(d) BYO / local model.** **Model optionality across Google + third-party hosted models:** *"generous rate limits on Gemini 3 Pro, and full support for Anthropic's Claude Sonnet 4.5 and OpenAI's GPT-OSS"* (official launch blog). This is a notable multi-model story — but these are **hosted** models within Antigravity, **not local Ollama**. No local/offline model support verified.

---

## 8. Aider

**What it is.** A popular open-source (**Apache-2.0**) AI pair-programming CLI (https://github.com/Aider-AI/aider). Free and open source; **BYO API key** — no built-in model allowance.

**(a) Free-tier reality.** The tool is free; cost = your chosen model. **No credit card needed for the tool**; only if you use a paid model. Aider's docs note free routes exist (e.g. OpenRouter free models with daily limits). With a local model: $0.

**(b) Headless / scriptable mode — YES, excellent.** Source: https://aider.chat/docs/scripting.html. **`aider --message "<msg>"` (alias `-m`)** = *"Specify a single message to send … process reply then exit"*; **`--message-file` / `-f`** for file input. Also a Python `Coder` API (explicitly "not officially supported, may change"). Verbatim example: `aider --message "make a script that prints hello" hello.js`. Strong fit for batch/headless scoring.

**(c) Imminent change.** None verified.

**(d) BYO / local model — YES.** Connects to *"almost any LLM, including local models"* — OpenAI, Anthropic, Gemini, Groq, DeepSeek, **Ollama**, and any OpenAI-compatible endpoint (https://aider.chat/docs/llms.html). **Viable fully-offline scorer.**

---

## 9. Cursor CLI

**What it is.** The terminal/headless agent from Cursor (the AI IDE), for CI and automation.

**(a) Free-tier reality.** **No meaningful free tier for the CLI/SDK.** Cursor billing is token-based; individual paid plans include **at least $20/mo of API usage** (Cursor Pro), with overage pay-as-you-go; Teams Standard $40/user, Premium $120/user (via cursor.com/pricing, search-corroborated). **A paid plan / API key (`CURSOR_API_KEY`) is effectively required** — the CLI expects `CURSOR_API_KEY` exported for scripts (source: https://cursor.com/docs/cli/headless). (Card needed: yes for non-trivial use.)

**(b) Headless / scriptable mode — YES, strong.** Source: https://cursor.com/docs/cli/headless. **`-p` / `--print`** for non-interactive; **`--output-format text|json|stream-json`** (+ `--stream-partial-output`); **`--force` / `--yolo`** to allow file edits in scripts. Verbatim example: `agent -p --force --output-format text "Review recent changes for quality, bugs, security, and best practices"`. Plus a TypeScript Cursor SDK. Excellent fit for headless scoring.

**(c) Imminent change.** None verified.

**(d) BYO / local model.** **Not documented / not supported for local** in the headless docs (no `--oss`/Ollama config found). Cursor routes to its own hosted model pool. **No local Ollama support verified.**

---

## 10. Amazon Q Developer CLI

**What it is.** AWS's terminal coding agent (`q`), powered by Amazon Bedrock; CLI autocompletions + agentic chat in the terminal.

**(a) Free-tier reality — a genuine perpetual free tier, no card.** Source: https://aws.amazon.com/q/developer/pricing/ + https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-tiers.html. **Free tier = 50 agentic requests/month** (Q&A + agentic coding), **access to "latest Claude models,"** usable in IDE **and CLI**, plus 1,000 lines/month of Java upgrades. The Free tier works with a **personal AWS Builder ID** (no AWS account / no credit card needed) and **the CLI is explicitly available on Free tier via Builder ID** (per the tiers table). **Pro tier = $19/user/month** with higher limits. *(Both IDE and CLI agentic requests count toward the 50/mo.)*

**(b) Headless / scriptable mode.** The CLI (`q chat`) is agentic and terminal-native. **FLAGGED:** I did **not** fetch an official page confirming a one-shot non-interactive flag (e.g. `q chat --no-interactive` / piping). Headless scriptability for our tool is **UNVERIFIED** and needs confirmation against the official CLI reference before relying on it.

**(c) Imminent change.** None verified.

**(d) BYO / local model — NO.** Amazon Q is powered by Bedrock-hosted foundation models (currently "latest Claude models") augmented with AWS content; **no local/Ollama or arbitrary BYO model.**

---

## 11. Kimi CLI (Moonshot)

**What it is.** Moonshot AI's open-source terminal coding agent (https://github.com/MoonshotAI/kimi-cli), built around the **Kimi K2** model series (open-source, **Modified MIT** license — K2 / K2.5 / K2.6 per https://moonshotai.github.io/Kimi-K2/). **Note:** the `kimi-cli` repo is *"evolving into Kimi Code CLI"* (MoonshotAI/kimi-code) and will be wound down — track both.

**(a) Free-tier reality.** Auth is **Kimi Code OAuth (browser) or an API key** (source: https://moonshotai.github.io/kimi-cli/en/guides/getting-started.html). The Moonshot platform is **pay-as-you-go**, OpenAI/Anthropic-compatible. **No specific free request allowance is documented** in the pages I fetched. **FLAGGED:** whether the OAuth login grants any free quota is **UNVERIFIED**; assume a paid key may be needed. (The model **weights are free/open** under Modified MIT, so a *self-hosted* Kimi K2 is free — see (d).)

**(b) Headless / scriptable mode — YES, strong.** Source: https://moonshotai.github.io/kimi-cli/en/reference/kimi-command.html. **`--prompt TEXT` / `-p`** (= *"Pass user prompt, doesn't enter interactive mode"*), **`--command` / `-c`** (alias), **`--print`** (non-interactive), **`--quiet`** (= `--print --output-format text --final-message-only`), **`--model` / `-m`** to pick a model, and **`kimi acp`** for an Agent-Client-Protocol server (IDE integration / multi-session). Excellent fit for headless scoring (`kimi -p "..." --quiet`).

**(c) Imminent change.** The `kimi-cli` → `kimi-code` migration is in progress (no hard cutoff date published that I could verify). Track the successor repo.

**(d) BYO / local model — partial / via OpenAI-compatible.** Kimi CLI's API path is OpenAI/Anthropic-compatible, and the **K2 weights are open (Modified MIT)**, so a user can self-host Kimi K2 (e.g. via vLLM) and point the CLI at it. **FLAGGED:** an explicit official `base_url` / local-endpoint config example was **not** in the pages I fetched (the reference page didn't detail base-URL override); local use is plausible via OpenAI-compatible config but the exact mechanism is **UNVERIFIED**.

---

## Comparison table

| CLI | Free tier (no-card reality) | Card needed? | Headless mode (flag) | BYO / local model | Imminent change (verified) |
|---|---|---|---|---|---|
| **Claude Code** | None | **Yes** (sub or API) | **YES** `claude -p` (json/stream/schema) | Bedrock/Vertex/Foundry; **no local** | **June 15 2026**: `claude -p`/Agent SDK move to separate credit ($20 Pro…), full API rates ✅ |
| **Gemini CLI** | **1,000 req/day** (Google OAuth) — *ends Jun 18* | No (OAuth) | **YES** `gemini -p` (json/stream) | **No local** (Gemini-only; LiteRT-LM partial) | **June 18 2026**: free/Pro/Ultra cut off; repo stays OSS, needs paid key ✅ |
| **Codex CLI** | Free plan exists, cap unpublished | Mostly (Plus/Pro or API) | **YES** `codex exec` | **YES** `--oss` (Ollama/LM Studio) | None discrete (model lineup iterating) |
| **Qwen Code** | **Discontinued** (was 1,000→100→0, Apr 13–15 2026) | **Yes now** (paid key) | **YES** `qwen -p` | **YES** Ollama/vLLM + OpenAI-compat | Free OAuth ended Apr 15 2026 ✅ |
| **OpenCode** | Tool free; BYO model | No (only if paid provider) | **YES** `opencode run` / `serve`, `--format json` | **YES** any provider + local | None |
| **GitHub Copilot CLI** | **Free plan** (2,000 completions/mo + AI credits), no card | No (Free) / Yes (Pro) | **YES** `copilot -p`/`--prompt` | **No local** | **June 1 2026**: PRUs → AI Credits (usage-based) ✅; signups paused Apr 20 |
| **Antigravity CLI** | Public preview "no cost" (cap ~weekly; *~20/day community-reported*) | Not stated (flagged) | **Unverified** (TUI-first; SDK exists) | Hosted multi-model (Gemini/Claude/GPT-OSS); **no local** | IS the successor to Gemini CLI (Jun 18 2026) ✅ |
| **Aider** | Tool free (Apache-2.0); BYO model | No (only if paid model) | **YES** `aider -m`/`--message`, `-f` | **YES** Ollama + any OpenAI-compat | None |
| **Cursor CLI** | No real free tier | **Yes** (`CURSOR_API_KEY`/plan) | **YES** `-p`/`--print` (json/stream, `--force`) | **No local** (hosted pool) | None |
| **Amazon Q Dev CLI** | **50 agentic req/mo** (Builder ID, no card) | No (Free) / Yes ($19 Pro) | **Unverified** (flagged) | **No local** (Bedrock-hosted) | None |
| **Kimi CLI** | OSS tool; free quota unverified | Likely (paid key) | **YES** `kimi -p`/`--quiet` | Partial: self-host K2 (MIT) via OpenAI-compat (flagged) | `kimi-cli`→`kimi-code` migration (no date) |

✅ = change confirmed against an official first-party source.

---

## Conclusion & design implications

### Best CLIs for cost-free users (no credit card, real free allowance, headless-capable)
Ranked by current no-card free capacity + headless fit:
1. **Gemini CLI** — by far the largest no-card allowance (**1,000 req/day**, `gemini -p`), **but it expires for individuals on 2026-06-18.** Best free option *today*, a dead end *next week*.
2. **GitHub Copilot CLI** — **Free plan, no card**, `copilot -p` headless; chat/agentic use consumes a monthly AI-Credit allotment (completions are free but aren't what we need for scoring). Durable.
3. **Amazon Q Developer CLI** — **50 agentic requests/mo, no card** (Builder ID), backed by "latest Claude models." Small but genuinely free and durable; **headless one-shot flag unverified** (risk).
4. **Local-model route via Codex `--oss`, OpenCode, Aider, or self-hosted Qwen/Kimi** — **the only path to truly unlimited, $0, offline, private scoring.** No card ever, data never leaves the machine (which matches this product's "data never leaves the user's machine" promise). Requires the user to run Ollama/vLLM locally.

### Best CLIs for quality (when the user is willing to pay)
- **Claude Code** (`claude -p`, structured `--json-schema` output) — top-tier scoring quality and the cleanest structured-output story; on subscription it's now metered against the small Agent SDK credit pool (≥$20/mo Pro) at full API rates, or pay-as-you-go via API key.
- **Codex CLI** (`codex exec`, GPT-5.x-Codex family) — strong quality, flexible (also does local via `--oss`).
- **Cursor CLI** (`-p`, hosted frontier models) — strong, but no real free tier and no local option.
- **Antigravity** — multi-model (Gemini 3.x Pro / Claude Sonnet 4.5 / GPT-OSS), but headless maturity is unproven and free caps are tiny/uncertain.

### Confirmed design implication: the tool MUST be default-less / CLI-agnostic
The evidence above makes a hard dependency on any single provider **unsafe by construction**:
- **Free tiers shift constantly and without much notice.** In a ~2-month window we have three first-party free-tier upheavals: **Qwen** killed its free OAuth tier (Apr 13–15 2026), **GitHub Copilot** switched everyone to usage-based AI Credits (Jun 1 2026), and **Google** is terminating Gemini CLI's free individual access (Jun 18 2026). **Anthropic** is carving `claude -p` out of subscription limits into a separate metered credit (Jun 15 2026).
- **No single provider is safe to hard-depend on.** The most generous free option (Gemini CLI, 1,000/day) is being shut off days from now; the most quality-forward (Claude Code) is getting more expensive for headless/subscription use; the cheapest "real free" (Amazon Q, 50/mo) is tiny and its headless mode is unverified.
- **Therefore:** the rebuild should treat "which CLI/model scores the job" as **user-selected configuration with NO baked-in default.** Detect installed CLIs, let the user choose, and drive whichever they pick via its documented headless flag (`claude -p`, `gemini -p`, `codex exec`, `qwen -p`, `opencode run`, `copilot -p`, `aider -m`, `agent -p`, `kimi -p`). This insulates the product from any one vendor's pricing/free-tier move and lets each user optimize for *their* cost/quality point.

### CLIs that support local Ollama models (fully-free, offline, private scoring)
For users who want **$0, no card, no data leaving the machine** (directly on-brand for this India-focused, self-hosted, privacy-first product):
- ✅ **Codex CLI** — `--oss` → Ollama / LM Studio (official, with config example).
- ✅ **Qwen Code** — Ollama + vLLM, "no API key or cloud account needed" (official README).
- ✅ **OpenCode** — any provider incl. local via OpenAI-compatible endpoints (official).
- ✅ **Aider** — Ollama + any OpenAI-compatible local endpoint (official).
- ◑ **Kimi CLI** — self-host the open-weight K2 (Modified MIT) via an OpenAI-compatible endpoint; exact base-URL config unverified (flagged).
- ❌ **Not local-capable:** Claude Code (hosted Anthropic/Bedrock/Vertex only), Gemini CLI (Gemini-only, officially no Ollama), GitHub Copilot CLI, Cursor CLI, Amazon Q (Bedrock-hosted), Antigravity (hosted multi-model, no local).

**Recommended default-less posture:** ship adapters for the headless flag of each CLI above; **steer privacy/cost-sensitive Indian users toward the local-Ollama-capable set (Codex `--oss`, Qwen, OpenCode, Aider)** for a genuinely free, offline scorer, while supporting the hosted CLIs for users who prioritize quality and already pay for a plan.

---

## UNVERIFIED / COULD NOT CONFIRM

The two June 2026 changes the brief flagged — **both CONFIRMED against official first-party sources:**
- ✅ **Anthropic Agent SDK / `claude -p` credit change — CONFIRMED.** Effective **June 15 2026**, per the official Anthropic Help Center article (https://support.claude.com/en/articles/15036540-...) and echoed inline in the official Claude Code headless docs. Credit amounts, no-rollover, depletion behavior, and the API-key carve-out are all quoted from that page.
- ✅ **Gemini CLI → Antigravity CLI migration — CONFIRMED.** Announced **May 19 2026**, service ends **June 18 2026** for free/Pro/Ultra individuals, per the official Google Developers Blog (https://developers.googleblog.com/an-important-update-...) and official repo discussion #27274. The Apache-2.0 repo persists; enterprise keeps access.

**Items I could NOT confirm against an official page (flagged in-line above):**
1. **Antigravity free-tier exact cap.** Official pages state "no cost for individuals (public preview)" but the **specific number** (a weekly compute cap; **~20 requests/day** is **community-reported only**, e.g. xda-developers, agentpedia.codes). The antigravity.google pricing/blog pages are JS-rendered and returned no machine-readable numbers. **Needs:** the live Antigravity pricing/quota page rendered, or an official quota doc.
2. **Antigravity CLI headless flag.** No official one-shot/non-interactive flag confirmed; Google's own comparison implies Gemini CLI (not Antigravity CLI) is the headless tool at launch. An Antigravity SDK exists. **Needs:** the official Antigravity CLI reference (antigravity.google/docs/cli-reference), which I could not render.
3. **Codex Free-plan exact allowance.** The pricing page lists Codex on the Free plan but publishes **no number** for it (paid tiers are quantified). **Needs:** an official Free-tier message/quota figure.
4. **Amazon Q CLI headless one-shot flag.** Free tier (50 agentic req/mo) and CLI availability are confirmed, but I did **not** verify an official non-interactive/scriptable flag for `q chat` (e.g. piping / `--no-interactive`). **Needs:** the official Q CLI command reference.
5. **Kimi CLI free quota & local-endpoint config.** Auth (OAuth/API key) and headless flags (`-p`, `--quiet`) are confirmed; **whether OAuth grants a free allowance** and the **exact base-URL/local-model config** were not in the fetched pages. Self-hosting K2 is possible (open weights) but the CLI config mechanism is unconfirmed. **Needs:** Kimi CLI config-files docs + Moonshot platform free-tier page.
6. **Gemini CLI "Google closed all multi-model PRs" claim.** A secondary source asserts Google closed local-model discussions/PRs. I confirmed the **official README/docs list no local-provider support**, but could **not** confirm that specific "closed everything" statement from a maintainer comment. Treat the *absence* of official local support as the verified fact; the "actively rejected" framing is unconfirmed.
7. **Credit-card requirements** for some free tiers (Codex Free, Antigravity preview, Kimi OAuth) are **not explicitly stated** on official pages; absence of a card requirement is inferred from the sign-in flow, not confirmed in writing.
8. **OpenCode repo identity** (`sst/opencode` vs `anomalyco/opencode`) and star counts varied between snapshots; opencode.ai is canonical, but the exact GitHub org/ownership at time of reading is **not pinned**.

*All figures are a 2026-06-09 snapshot. Re-verify any free-tier number or date before depending on it — the four changes clustered in April–June 2026 demonstrate how fast this moves.*
