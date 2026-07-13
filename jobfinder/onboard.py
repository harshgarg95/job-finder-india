"""Conversational onboarding — first-run setup.

Mirrors career-ops's onboarding: do NOT run discovery/scoring until the basics
exist. The deterministic state comes from doctor.check(); this module supplies
(a) never-overwrite writers for the User-Layer files, and (b) a guided 5-step
flow for a standalone user. When run inside an AI CLI, the agent conducts the
same five steps conversationally and calls these writers.

User-Layer safety: every writer here refuses to overwrite an existing user file
unless force=True. Templates (System Layer) are only ever COPIED into place.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil

import yaml

from . import cli_adapter, doctor
from .resume import load_resume

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (template, live) pairs — live files are User Layer, never clobbered.
_SEED_PAIRS = [
    ("config/profile.example.yml", "config/profile.yml"),
    ("config/sources.example.yml", "config/sources.yml"),
    ("config/run.example.yml", "config/run.yml"),
    ("config/_profile.example.md", "config/_profile.md"),
]


def seed_config_files(force: bool = False) -> list[str]:
    """Create any missing live config files from their shipped templates."""
    created = []
    for ex, live in _SEED_PAIRS:
        exp, livep = os.path.join(ROOT, ex), os.path.join(ROOT, live)
        if os.path.exists(exp) and (force or not os.path.exists(livep)):
            shutil.copyfile(exp, livep)
            created.append(live)
    return created


def import_resume(src: str, force: bool = False) -> str:
    """Parse a resume from any supported format and write canonical resume.md.
    Refuses to overwrite an existing resume.md unless force=True."""
    dest = os.path.join(ROOT, "resume.md")
    if os.path.exists(dest) and not force:
        return dest
    text = load_resume(os.path.expanduser(src))
    if not text or len(text.strip()) < 50:
        raise ValueError(f"parsed resume from {src!r} looks empty ({len(text or '')} chars)")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return dest


def write_profile_md(text: str, force: bool = False) -> str:
    dest = os.path.join(ROOT, "config", "_profile.md")
    if os.path.exists(dest) and not force:
        return dest
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    return dest


def set_run_cli(cli: str) -> None:
    """Persist the user's chosen scoring CLI into config/run.yml (scoring.cli)."""
    p = os.path.join(ROOT, "config", "run.yml")
    data = {}
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    data.setdefault("scoring", {})["cli"] = cli
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _input(prompt: str, default: str = "") -> str:
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v or default


def _interactive() -> int:
    print("── job-finder onboarding ──\n")
    rep = doctor.check()

    # Step 1 — choose LLM (detected only, no default).
    print("Step 1 — Choose your AI CLI. Scoring runs through one you already have.")
    print("         (local = free & private; a subscription CLI uses your own login.)")
    options = list(rep["clis_present"])
    if rep["ollama"]["models"]:
        options.append("ollama")
    if not options:
        print("  No AI CLI detected. Install claude/gemini/codex/qwen/opencode or pull an "
              "Ollama model, then re-run.")
        return 1
    for i, c in enumerate(options, 1):
        local = " — local, free/private" if (c == "ollama" or c in cli_adapter.LOCAL_CAPABLE) else ""
        print(f"   {i}. {c}{local}")
    choice = _input("  Pick a number or name: ")
    chosen = None
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        chosen = options[int(choice) - 1]
    elif choice in options:
        chosen = choice
    if chosen and chosen != "ollama":
        set_run_cli(chosen)
        print(f"  → saved scoring CLI = {chosen} (config/run.yml)")
    elif chosen == "ollama":
        print("  → point a local-capable CLI (codex --oss / qwen / opencode) at your Ollama model.")

    # Step 2 — login + health check (explicit; don't assume logged in).
    print("\nStep 2 — Log in to your chosen CLI. We reuse YOUR login; we never touch your key.")
    print("  • claude: run `claude login`. If a stray ANTHROPIC_API_KEY is set, UNSET it — it")
    print("    overrides your subscription. For headless scoring also run `claude setup-token`.")
    if chosen and _input("  Run a one-call health check now? [y/N]: ").lower().startswith("y"):
        hc = cli_adapter.health_check(chosen if chosen != "ollama" else None)
        if hc["ok"]:
            print(f"   ✓ {hc['cli']} authenticated"
                  + (f" (cost ${hc['cost_usd']})" if hc.get("cost_usd") else ""))
        else:
            print(f"   ✗ {hc['cli']} failed: {hc['error']}")
            print("     Fix login (see above) and re-run the health check before scoring.")

    # Step 3 — resume + profile.
    print("\nStep 3 — Resume + profile.")
    seeded = seed_config_files()
    if seeded:
        print(f"  seeded missing config: {', '.join(seeded)}")
    rpath = _input("  Path to your resume (.pdf/.docx/.md/.txt), blank to paste: ")
    if rpath:
        try:
            print(f"  → wrote {import_resume(rpath)}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! could not import resume: {e}")
    else:
        print("  Paste your resume; finish with a single line: EOF")
        buf = []
        while True:
            try:
                ln = input()
            except EOFError:
                break
            if ln.strip() == "EOF":
                break
            buf.append(ln)
        if buf and not os.path.exists(os.path.join(ROOT, "resume.md")):
            with open(os.path.join(ROOT, "resume.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(buf).strip() + "\n")
            print("  → wrote resume.md")
    print("  Now edit config/profile.yml — the [GATE] fields (seniority, function in/out-of-scope,")
    print("  comp floor, location, hard_constraints) are how the scorer says an honest 'no'.")

    # Step 4 — sources.
    print("\nStep 4 — Sources. The free public-ATS scan is ON by default. Apify (Naukri/LinkedIn/")
    print("  Indeed) is optional: put APIFY_TOKEN in .env and set apify.enabled: true in")
    print("  config/sources.yml — or skip it. It auto-pauses if your credits run out.")

    # Step 5 — get-to-know-you.
    print("\nStep 5 — A few notes make scoring sharper: superpower, what excites/drains you,")
    print("  deal-breakers, top achievement, portfolio links → config/_profile.md.")

    print("\nDone. Run `python -m jobfinder doctor` to confirm you're READY, then")
    print("`python -m jobfinder --resume <path>` for your first honest top-N.")
    return 0


def cmd(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder onboard")
    ap.add_argument("--seed", action="store_true", help="create missing config files from templates")
    ap.add_argument("--resume-from", help="import a resume file into resume.md")
    ap.add_argument("--health-check", nargs="?", const="", metavar="CLI",
                    help="run a one-call CLI auth/health check (optionally name the CLI)")
    ap.add_argument("--force", action="store_true", help="allow overwriting existing user files")
    a = ap.parse_args(argv)

    did = False
    if a.seed:
        created = seed_config_files(force=a.force)
        print("seeded: " + (", ".join(created) if created else "(all present)"))
        did = True
    if a.resume_from:
        print(f"resume -> {import_resume(a.resume_from, force=a.force)}")
        did = True
    if a.health_check is not None:
        print(json.dumps(cli_adapter.health_check(a.health_check or None), ensure_ascii=False))
        did = True
    return 0 if did else _interactive()
