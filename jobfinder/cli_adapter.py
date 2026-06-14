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


# Headless invocations verified from each CLI's official docs (docs/research/03).
ADAPTERS: dict[str, CliAdapter] = {
    "claude":   CliAdapter("claude",   "claude",   ("-p",),            "stdin", "Anthropic; top structured-output quality (paid)"),
    "gemini":   CliAdapter("gemini",   "gemini",   ("-p",),            "arg",   "Google; free OAuth tier ended Jun-18-2026 for individuals"),
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


def score(
    prompt: str,
    cli: Optional[str] = None,
    *,
    timeout: int = 300,
    runner: Optional[Callable[[list[str], str], str]] = None,
) -> dict:
    """Run `prompt` through the chosen CLI and return parsed JSON.

    `cli`: adapter id; if None, uses $JOBFINDER_CLI or the first detected one.
    `runner`: injectable for tests (argv, stdin_text) -> stdout_text.
    Raises RuntimeError if no CLI is available or the output is unparseable.
    """
    if cli is None:
        cli = os.environ.get("JOBFINDER_CLI")
    if cli is None:
        detected = detect_clis()
        if not detected:
            raise RuntimeError(
                "No AI CLI found. Install one of: "
                + ", ".join(ADAPTERS) + " (or set $JOBFINDER_CLI)."
            )
        cli = detected[0]["id"]

    adapter = ADAPTERS.get(cli)
    if adapter is None:
        raise RuntimeError(f"Unknown CLI '{cli}'. Known: {', '.join(ADAPTERS)}")
    if runner is None and not shutil.which(adapter.bin):
        raise RuntimeError(f"CLI '{cli}' selected but binary '{adapter.bin}' is not on PATH.")

    argv = [adapter.bin, *adapter.args]
    stdin_text = ""
    if adapter.delivery == "arg":
        argv.append(prompt)
    else:
        stdin_text = prompt

    if runner is not None:
        out = runner(argv, stdin_text)
    else:
        proc = subprocess.run(
            argv, input=stdin_text, capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(f"CLI '{cli}' exited {proc.returncode}: {proc.stderr[:500]}")
        out = proc.stdout

    parsed = _extract_json(out)
    if parsed is None:
        raise RuntimeError(
            f"CLI '{cli}' did not return parseable JSON. First 500 chars:\n{out[:500]}"
        )
    return parsed
