"""Cold-start doctor — deterministic environment + config check.

Mirrors career-ops's `doctor.mjs --json`: on the first message the agent (or
the app) runs this to see which AI CLIs are installed and which config files
exist, then decides whether onboarding is needed BEFORE any discovery/scoring
runs. It makes no network calls and reads no secrets — purely a local inventory.

  python -m jobfinder doctor          # human-readable checklist
  python -m jobfinder doctor --json   # machine-readable (for the agent / scripts)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import yaml

from . import cli_adapter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that MUST exist before discovery/scoring may run. For each logical slot
# we accept any of the candidate paths (first found wins).
REQUIRED = {
    "resume": ["resume.md", "resume.txt", "resume.pdf", "resume.docx"],
    "profile": [os.path.join("config", "profile.yml")],
    "sources": [os.path.join("config", "sources.yml")],
    "run": [os.path.join("config", "run.yml")],
}
# Recommended but NOT blocking — onboarding Step 5 produces this.
RECOMMENDED = {
    "narrative_profile": [os.path.join("config", "_profile.md")],
}


def _first_existing(candidates: list[str]) -> str | None:
    for rel in candidates:
        if os.path.exists(os.path.join(ROOT, rel)):
            return rel
    return None


def _profile_ready(rel_path: str) -> bool:
    """A profile.yml counts as 'present' only if it's non-empty, non-placeholder,
    and carries the required [GATE] fields — so a seeded-but-unfilled template
    still blocks evaluate/scan (onboarding must actually write it from answers)."""
    try:
        d = yaml.safe_load(open(os.path.join(ROOT, rel_path), encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(d, dict) or not d:
        return False
    if (d.get("candidate") or {}).get("full_name") in (None, "", "Your Name"):
        return False
    if not (d.get("seniority") or {}).get("honest_ceiling"):
        return False
    # target_roles is OPTIONAL — the rubric scores function fit against `function.*`
    # + the résumé, not target_roles (grep: prompts/ never reference it). A profile
    # with empty target_roles is still ready; onboarding just couldn't derive them.
    if not (d.get("location") or {}).get("base_city"):
        return False
    return True


def detect_ollama() -> dict:
    """Is Ollama installed, and which local models are pulled? (free/offline path)"""
    if not shutil.which("ollama"):
        return {"installed": False, "models": []}
    models: list[str] = []
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        for line in out.stdout.splitlines()[1:]:  # skip header row
            if line.strip():
                models.append(line.split()[0])
    except Exception:  # noqa: BLE001 — ollama present but not responding is non-fatal
        pass
    return {"installed": True, "models": models}


def check() -> dict:
    """Return a full, deterministic snapshot of setup readiness."""
    clis = cli_adapter.detect_clis()
    ollama = detect_ollama()

    files: dict[str, str | None] = {}
    missing_required: list[str] = []
    for key, cands in REQUIRED.items():
        found = _first_existing(cands)
        files[key] = found
        if not found:
            missing_required.append(key)
        elif key == "profile" and not _profile_ready(found):
            # exists but empty / still the placeholder template / missing [GATE] fields
            missing_required.append(key)

    missing_recommended: list[str] = []
    for key, cands in RECOMMENDED.items():
        found = _first_existing(cands)
        files[key] = found
        if not found:
            missing_recommended.append(key)

    has_cli = bool(clis) or bool(ollama.get("models"))
    return {
        "clis": clis,
        "clis_present": [c["id"] for c in clis],
        "ollama": ollama,
        # Scoring runs in-session, so model quality matters. The agent relays this on first run.
        "model_advice": ("Scoring is done in-session by your model — model quality matters. "
                         "If you're on a small/default model (GitHub Copilot 'Auto', gpt-5-mini/"
                         "nano, Haiku-tier), switch to a capable one (Copilot: pick GPT-5 or "
                         "Claude Sonnet/Opus, not 'Auto') before scoring for reliable verdicts."),
        "files": files,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "has_cli": has_cli,
        # ready to run end-to-end: a CLI exists and all required files are present
        "ready": has_cli and not missing_required,
        # onboarding is needed if a required file is missing or no CLI at all
        "needs_onboarding": bool(missing_required) or not has_cli,
        # career-ops-compatible aliases (same gate, their field names)
        "onboardingNeeded": bool(missing_required) or not has_cli,
        "missing": missing_required,
    }


def _human(rep: dict) -> str:
    lines = ["job-finder doctor — setup check", ""]
    lines.append("AI CLIs detected (scoring runs through one you already have):")
    if rep["clis_present"]:
        for c in rep["clis"]:
            tag = " [local-capable]" if c.get("local_capable") else ""
            lines.append(f"  ✓ {c['id']}{tag} — {c.get('note','')}")
    else:
        lines.append("  ✗ none found")
    oll = rep["ollama"]
    if oll["installed"]:
        ms = ", ".join(oll["models"][:6]) or "(no models pulled)"
        lines.append(f"  ✓ ollama (local/free) — models: {ms}")
    lines.append("")
    lines.append("⚠ Model tip: scoring runs in-session, so use a CAPABLE model.")
    lines.append("  On GitHub Copilot pick GPT-5 or Claude (Sonnet/Opus) — not 'Auto'/gpt-5-mini.")
    lines.append("")
    lines.append("Config & resume files:")
    label = {
        "resume": "resume (resume.md or a path you pass)",
        "profile": "config/profile.yml",
        "sources": "config/sources.yml",
        "run": "config/run.yml",
        "narrative_profile": "config/_profile.md (recommended)",
    }
    for key in ("resume", "profile", "sources", "run", "narrative_profile"):
        found = rep["files"].get(key)
        mark = "✓" if found else ("•" if key == "narrative_profile" else "✗")
        where = f" → {found}" if found else ""
        lines.append(f"  {mark} {label[key]}{where}")
    lines.append("")
    if rep["ready"]:
        lines.append("Status: READY. You can run discovery + scoring.")
    elif not rep["has_cli"]:
        lines.append("Status: NOT READY — no AI CLI found. Install one (claude/gemini/…) "
                     "or pull an Ollama model, then re-run.")
    else:
        miss = ", ".join(rep["missing_required"])
        lines.append(f"Status: NEEDS ONBOARDING — missing: {miss}. "
                     "Run onboarding before discovery/scoring.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    rep = check()
    if "--json" in argv:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(_human(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
