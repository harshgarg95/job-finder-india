"""CLI-agnostic scoring adapter.

job-finder holds NO model API key. Scoring is done by whatever agentic AI CLI
the user already has, driven in headless (one-shot) mode. This module:

  1. detects which CLIs are installed (`detect_clis`),
  2. drives the chosen one to score a prompt and returns parsed JSON
     (`score`)  — the `score(prompt) -> dict` contract from the build plan.

Why default-less: the economics research (docs/research/03) found four
first-party free-tier upheavals in ~2 months. Hard-depending on any one CLI is
unsafe by construction, so the user picks; we adapt.

The rubric prompt instructs the model to print exactly one JSON object. We
capture stdout and extract that object — this works uniformly across CLIs whose
text output differs. If nothing parseable comes back, we raise (never invent a
score).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CliAdapter:
    id: str
    bin: str
    # argv (excluding the prompt) for a headless one-shot run.
    args: tuple[str, ...]
    # how the prompt is delivered: "stdin" or "arg"
    delivery: str = "stdin"
    # human note about cost/quality, surfaced in `detect`
    note: str = ""
    # extra environment variables needed for a non-interactive run (k, v) pairs
    env: tuple[tuple[str, str], ...] = ()


# Headless invocations verified from each CLI's official docs (docs/research/03).
ADAPTERS: dict[str, CliAdapter] = {
    "claude":   CliAdapter("claude",   "claude",   ("-p",),            "stdin", "Anthropic; top structured-output quality (paid)"),
    "gemini":   CliAdapter("gemini",   "gemini",   ("-p",),            "arg",   "Google; free OAuth tier ends Jun-18-2026 for individuals",
                           env=(("GEMINI_CLI_TRUST_WORKSPACE", "true"),)),  # required for headless runs
    "codex":    CliAdapter("codex",    "codex",    ("exec",),          "arg",   "OpenAI; supports local Ollama via `--oss` (free/offline)"),
    "qwen":     CliAdapter("qwen",     "qwen",     ("-p",),            "arg",   "Alibaba; supports local Ollama/vLLM (free/offline)"),
    "opencode": CliAdapter("opencode", "opencode", ("run",),           "arg",   "SST; provider-agnostic incl. local (free/offline)"),
    "aider":    CliAdapter("aider",    "aider",    ("--message",),     "arg",   "Apache-2.0; BYO incl. local Ollama (free/offline)"),
    "copilot":  CliAdapter("copilot",  "copilot",  ("-p",),            "arg",   "GitHub; usage-based AI credits"),
    "cursor":   CliAdapter("cursor",   "agent",    ("-p",),            "arg",   "Cursor; hosted models, paid"),
    "kimi":     CliAdapter("kimi",     "kimi",     ("-p", "--quiet"),  "arg",   "Moonshot; self-host K2 possible"),
}

# Local-capable set we steer privacy/cost-sensitive users toward (docs/research/03 §CLIs-with-local).
LOCAL_CAPABLE = {"codex", "qwen", "opencode", "aider", "kimi"}


def detect_clis() -> list[dict]:
    """Return installed CLIs (those whose binary is on PATH), richest first."""
    found = []
    for a in ADAPTERS.values():
        if shutil.which(a.bin):
            found.append({"id": a.id, "bin": a.bin, "local_capable": a.id in LOCAL_CAPABLE, "note": a.note})
    return found


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first balanced top-level JSON object out of CLI stdout."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break  # malformed; try the next "{"
        start = text.find("{", start + 1)
    return None


# Errors that mean "this CLI is unavailable right now — try the next one."
_FAILOVER_HINTS = ("quota", "rate limit", "rate-limit", "ratelimit", "429",
                   "exhausted", "resource_exhausted", "unauthor", "forbidden",
                   "401", "403", "credit", "billing", "not on path", "no ai cli")


def _is_failover_error(msg: str) -> bool:
    m = (msg or "").lower()
    return any(h in m for h in _FAILOVER_HINTS)


def _score_one(prompt: str, cli: str, *, timeout: int,
               runner: Optional[Callable[[list[str], str], str]]) -> dict:
    """Drive ONE CLI and return parsed JSON. Raises on any failure."""
    adapter = ADAPTERS.get(cli)
    if adapter is None:
        raise RuntimeError(f"Unknown CLI '{cli}'. Known: {', '.join(ADAPTERS)}")
    if runner is None and not shutil.which(adapter.bin):
        raise RuntimeError(f"CLI '{cli}' not on PATH.")

    argv = [adapter.bin, *adapter.args]
    # Delivery is per-CLI: arg-delivery CLIs (e.g. gemini -p) REQUIRE the prompt
    # as an argument — they error if it's only on stdin. They handle large args
    # fine for our prompt sizes; the rare oversize case errors and fails over.
    if adapter.delivery == "arg":
        argv.append(prompt)
        stdin_text = ""
    else:
        stdin_text = prompt

    if runner is not None:
        out = runner(argv, stdin_text)
    else:
        run_env = {**os.environ, **dict(adapter.env)} if adapter.env else None
        proc = subprocess.run(argv, input=stdin_text, capture_output=True,
                              text=True, timeout=timeout, env=run_env)
        if proc.returncode != 0:
            raise RuntimeError(f"CLI '{cli}' exited {proc.returncode}: {proc.stderr[:400]}")
        out = proc.stdout

    parsed = _extract_json(out)
    if parsed is None:
        raise RuntimeError(f"CLI '{cli}' returned no parseable JSON: {out[:300]}")
    return parsed


def _failover_order(cli: Optional[str]) -> list[str]:
    """Ordered CLIs to try: explicit/preferred first, then installed fallbacks."""
    order: list[str] = []
    for c in (cli, os.environ.get("JOBFINDER_CLI")):
        if c and c not in order:
            order.append(c)
    env_fb = os.environ.get("JOBFINDER_CLI_FALLBACK", "")
    fallbacks = [c.strip() for c in env_fb.split(",") if c.strip()] or \
                [d["id"] for d in detect_clis()]
    for c in fallbacks:
        if c not in order:
            order.append(c)
    return order


def score(
    prompt: str,
    cli: Optional[str] = None,
    *,
    timeout: int = 300,
    runner: Optional[Callable[[list[str], str], str]] = None,
    on_failover: Optional[Callable[[str, str, str], None]] = None,
) -> dict:
    """Score `prompt`, automatically failing over across installed CLIs.

    Tries the preferred CLI ($JOBFINDER_CLI or `cli`), then installed fallbacks
    (or $JOBFINDER_CLI_FALLBACK). On a quota/rate/auth error (e.g. gemini's
    TerminalQuotaError), moves to the next CLI instead of failing the run.
    `on_failover(from_cli, to_cli, reason)` is called when it switches. Raises
    only if EVERY candidate fails.
    """
    order = _failover_order(cli)
    if not order:
        raise RuntimeError("No AI CLI found. Install one of: " + ", ".join(ADAPTERS))

    errors = []
    for i, c in enumerate(order):
        try:
            result = _score_one(prompt, c, timeout=timeout, runner=runner)
            result.setdefault("_scored_by", c)
            return result
        except Exception as e:  # noqa: BLE001 — any failure → try next CLI
            errors.append(f"{c}: {e}")
            nxt = order[i + 1] if i + 1 < len(order) else None
            # Only fail over for availability errors (quota/auth/missing); a real
            # parse error from an available CLI still moves on, but we record it.
            if nxt and on_failover:
                on_failover(c, nxt, str(e)[:160])
            continue
    raise RuntimeError("All CLIs failed:\n  " + "\n  ".join(errors))
