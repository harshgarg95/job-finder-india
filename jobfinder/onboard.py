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
import sys

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


# ── Deterministic answers → resume.md + config/profile.yml (agent-callable) ──
# The agent (Copilot / Claude) asks the numbered questions, collects answers in
# chat, writes them to a JSON file, and calls `onboard --answers <file>`. Python
# writes the files — the agent never hand-authors YAML. Works with NO TTY.
MIN_RESUME_CHARS = 300
_CEILINGS = {"intern", "junior", "mid", "senior", "lead", "manager", "director"}
_WORK_MODES = {"remote", "hybrid", "onsite", "mix"}
# function.out_of_scope drives the wrong-function gate — a sensible default the
# agent is prompted to review/override after the write (see modes/onboarding.md).
_DEFAULT_OUT_OF_SCOPE = [
    "ML research engineer / deep modelling",
    "Senior data scientist (statistical modelling)",
    "Backend/platform software engineer (years of production coding)",
]
_DEFAULT_HARD_CONSTRAINTS = ["Must be India-based or fully remote (no relocation outside India)."]


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


def validate_answers(a: dict) -> list[str]:
    """Return a list of problems with the answers (empty = valid). Guards the
    REQUIRED [GATE] fields so we never write an empty/broken profile."""
    errs: list[str] = []

    def need(k):
        v = a.get(k)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            errs.append(f"missing required: {k}")
            return False
        return True

    need("full_name")
    need("base_city")
    if a.get("floor_ctc_lpa") is None or _num(a.get("floor_ctc_lpa")) is None:
        errs.append("missing/invalid number: floor_ctc_lpa")
    if need("target_roles") and not isinstance(a["target_roles"], list):
        errs.append("target_roles must be a list of role titles")
    for k in ("years_total", "years_in_function"):
        if _num(a.get(k)) is None:
            errs.append(f"missing/invalid number: {k}")
    if need("honest_ceiling") and str(a.get("honest_ceiling", "")).lower() not in _CEILINGS:
        errs.append(f"honest_ceiling must be one of {sorted(_CEILINGS)}")
    wm = str(a.get("work_mode", "")).lower()
    if wm not in _WORK_MODES:
        errs.append(f"work_mode must be one of {sorted(_WORK_MODES)}")
    elif wm in ("hybrid", "onsite", "mix") and not (a.get("onsite_cities") or []):
        errs.append(f"onsite_cities is required when work_mode is '{wm}'")
    return errs


def _answers_to_profile(a: dict) -> dict:
    """Map the flat answers onto the nested config/profile.yml schema. function.*
    is auto-derived from target_roles (the agent reviews out_of_scope afterward)."""
    base_city = a["base_city"].strip()
    city_only = base_city.split(",")[0].strip()
    roles = [str(r).strip() for r in a["target_roles"] if str(r).strip()]
    wm = str(a["work_mode"]).lower()
    onsite = [str(c).strip() for c in (a.get("onsite_cities") or []) if str(c).strip()]
    if wm == "onsite":
        remote_ok, hybrid_ok = False, False
    else:                                    # remote / hybrid / mix
        remote_ok, hybrid_ok = True, True
        onsite = onsite or [city_only]
    return {
        "candidate": {"full_name": a["full_name"].strip(), "location": base_city,
                      "email": (a.get("email") or "").strip()},
        "seniority": {"years_total": _num(a["years_total"]),
                      "years_in_function": _num(a["years_in_function"]),
                      "current_title": (a.get("current_title") or "").strip(),
                      "honest_ceiling": str(a["honest_ceiling"]).lower(),
                      "honest_ceiling_ic": str(a.get("honest_ceiling_ic") or "mid").lower()},
        "function": {"actual": a.get("function_actual")
                     or ("Delivery / implementation / program management across: " + ", ".join(roles[:3])),
                     "in_scope": a.get("function_in_scope") or list(roles),
                     "out_of_scope": a.get("function_out_of_scope") or list(_DEFAULT_OUT_OF_SCOPE)},
        "target_roles": {"primary": list(roles),
                         "archetypes": [{"name": r, "fit": "primary"} for r in roles]},
        "domains": {"strong": a.get("domains_strong") or [], "open_to": a.get("domains_open_to") or []},
        "compensation": {"current_ctc_lpa": _num(a.get("current_ctc_lpa")),
                         "target_ctc_lpa": _num(a.get("target_ctc_lpa")),
                         "floor_ctc_lpa": _num(a["floor_ctc_lpa"]),
                         "currency": (a.get("currency") or "INR")},
        "location": {"base_city": base_city, "remote_ok": remote_ok, "hybrid_ok": hybrid_ok,
                     "onsite_cities": onsite,
                     "willing_to_relocate": bool(a.get("willing_to_relocate", False)),
                     "notice_period_days": _num(a.get("notice_period_days")) or 60},
        "hard_constraints": a.get("hard_constraints") or list(_DEFAULT_HARD_CONSTRAINTS),
    }


def _profile_is_placeholder(dest: str) -> bool:
    """True if config/profile.yml is still the shipped template (safe to overwrite)."""
    try:
        d = yaml.safe_load(open(dest, encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return True
    return (d.get("candidate") or {}).get("full_name") in (None, "", "Your Name")


def write_profile_yaml(profile: dict, force: bool = False) -> str:
    dest = os.path.join(ROOT, "config", "profile.yml")
    if os.path.exists(dest) and not force and not _profile_is_placeholder(dest):
        raise FileExistsError("config/profile.yml already has a real profile — pass --force to overwrite")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write("# job-finder profile (User Layer — written by onboarding from your answers).\n"
                "# [GATE] fields feed the disqualifier checks in prompts/_rubric.md.\n\n")
        yaml.safe_dump(profile, f, sort_keys=False, allow_unicode=True)
    return dest


def write_from_answers(answers: dict, force: bool = False) -> dict:
    """Deterministically write resume.md (if given) + config/profile.yml from
    structured answers. Returns {"wrote": [...]} or {"error": "...", ...}."""
    errs = validate_answers(answers)
    if errs:
        return {"error": "answers failed validation", "problems": errs}

    wrote: list[str] = []
    dest_resume = os.path.join(ROOT, "resume.md")
    text = None
    if answers.get("resume_text"):
        text = answers["resume_text"]
    elif answers.get("resume_path"):
        try:
            text = load_resume(os.path.expanduser(answers["resume_path"]))
        except Exception as e:  # noqa: BLE001
            return {"error": f"could not read résumé from {answers['resume_path']!r}: {e}"}
    if text is not None:                     # résumé-parse guard: too-short = failure
        if len(text.strip()) < MIN_RESUME_CHARS:
            return {"error": f"résumé is empty or too short ({len(text.strip())} chars < "
                             f"{MIN_RESUME_CHARS}) — ask the user to paste the full résumé text"}
        if not os.path.exists(dest_resume) or force:
            with open(dest_resume, "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")
            wrote.append("resume.md")
    elif not os.path.exists(dest_resume):
        return {"error": "no résumé provided (resume_text or resume_path) and resume.md does not exist"}

    try:
        p = write_profile_yaml(_answers_to_profile(answers), force=force)
    except FileExistsError as e:
        return {"error": str(e)}
    wrote.append(os.path.relpath(p, ROOT))
    return {"wrote": wrote}


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
    # No-TTY refuse: an agent-spawned run has no keyboard, so do NOT silently
    # seed-and-collect-nothing. Point to the deterministic --answers path instead.
    if not sys.stdin.isatty():
        print("This interactive setup needs a real terminal (a keyboard).", file=sys.stderr)
        print("• Run it yourself:   python -m jobfinder onboard          (in YOUR terminal)", file=sys.stderr)
        print("• From an AI agent:  collect the answers, then call:\n"
              "                     python -m jobfinder onboard --answers <file.json>", file=sys.stderr)
        return 2

    print("── job-finder onboarding ──  (I'll write resume.md + config/profile.yml for you)\n")
    seed_config_files()
    a: dict = {}
    # ── résumé ──
    rpath = _input("Path to your résumé (.pdf/.docx/.md/.txt), or blank to paste: ")
    if rpath:
        a["resume_path"] = rpath
    else:
        print("Paste your résumé; finish with a single line: EOF")
        buf = []
        while True:
            try:
                ln = input()
            except EOFError:
                break
            if ln.strip() == "EOF":
                break
            buf.append(ln)
        a["resume_text"] = "\n".join(buf)
    # ── profile ──
    a["full_name"] = _input("Full name: ")
    a["email"] = _input("Email (optional): ")
    a["base_city"] = _input("Base city (e.g. 'Hyderabad, India'): ")
    a["target_roles"] = [s.strip() for s in _input("Target roles (comma-separated): ").split(",") if s.strip()]
    a["years_total"] = _num(_input("Years total experience: "))
    a["years_in_function"] = _num(_input("Years in your target function: "))
    a["honest_ceiling"] = _input("Honest ceiling (intern|junior|mid|senior|lead|manager|director): ")
    print("Work-mode:   1) Remote   2) Hybrid   3) On-site   4) Open to a mix")
    a["work_mode"] = {"1": "remote", "2": "hybrid", "3": "onsite", "4": "mix"}.get(_input("Pick the number: "), "mix")
    if a["work_mode"] in ("hybrid", "onsite", "mix"):
        a["onsite_cities"] = [s.strip() for s in _input("On-site city/cities (comma-separated): ").split(",") if s.strip()]
    a["willing_to_relocate"] = _input("Open to relocating? (y/N): ").lower().startswith("y")
    a["floor_ctc_lpa"] = _num(_input("Comp floor / walk-away (LPA): "))
    tgt = _num(_input("Target comp (LPA, optional): "))
    if tgt:
        a["target_ctc_lpa"] = tgt
    hc = _input("Hard constraints (comma-separated, optional): ")
    if hc:
        a["hard_constraints"] = [s.strip() for s in hc.split(",") if s.strip()]

    res = write_from_answers(a)
    if res.get("error"):
        print(f"\n✗ {res['error']}")
        for pr in res.get("problems", []):
            print(f"  - {pr}")
        return 1
    print(f"\n✓ wrote {', '.join(res['wrote'])}")
    print("→ Review config/profile.yml — especially function.out_of_scope (it drives the wrong-function gate).")
    print("→ Run `python -m jobfinder doctor` to confirm READY, then say 'find me jobs' in your CLI.")
    return 0


def _coerce(v: str):
    """Coerce a --set VALUE string into bool / number / comma-list / str."""
    s = v.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.replace(".", "", 1).lstrip("-").isdigit():
        return _num(s)
    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]
    return s


def cmd(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder onboard")
    ap.add_argument("--seed", action="store_true", help="create missing config files from templates")
    ap.add_argument("--resume-from", help="import a resume file into resume.md")
    ap.add_argument("--answers", help="JSON file of onboarding answers → writes resume.md + config/profile.yml")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override/add a single answer (repeatable); merges over --answers")
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
    if a.answers or a.set:
        answers: dict = {}
        if a.answers:
            with open(a.answers, encoding="utf-8") as f:
                answers = json.load(f)
        for kv in a.set:
            k, _, v = kv.partition("=")
            answers[k.strip()] = _coerce(v)
        seed_config_files()                       # ensure sources/run templates exist too
        res = write_from_answers(answers, force=a.force)
        # PII hygiene: on success, delete the answers file so résumé + personal
        # details are not left sitting in the repo (data/ is gitignored anyway).
        if not res.get("error") and a.answers and os.path.exists(a.answers):
            os.remove(a.answers)
            res["answers_file"] = "deleted after successful write"
        print(json.dumps(res, ensure_ascii=False))
        return 1 if res.get("error") else 0
    if a.health_check is not None:
        print(json.dumps(cli_adapter.health_check(a.health_check or None), ensure_ascii=False))
        did = True
    return 0 if did else _interactive()
