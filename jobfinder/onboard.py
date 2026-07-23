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
import datetime
import json
import os
import re
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

# ── Optional discovery keys — guided, prominent, never typed INTO this tool ──
# The keys unlock the India-native channels (Adzuna + JSearch). Onboarding only
# GUIDES the user to put their own keys in their own .env — it never prompts for
# a key value (hard rule: this tool never collects/prints/transmits keys).
_RECOMMENDED_KEYS = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JSEARCH_API_KEY")
_ENV_PATH = os.path.join(ROOT, ".env")     # module-level so tests can point elsewhere


def _env_file_keys(path: str) -> set[str]:
    """Names with a non-empty value in a .env file (values are never returned)."""
    names: set[str] = set()
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if v.strip():
                names.add(k.strip())
    except OSError:
        pass
    return names


def _missing_keys() -> list[str]:
    """Recommended keys with no value in os.environ NOR the .env file. Re-reads
    .env every call, so a mid-onboarding edit is seen on re-check."""
    have = _env_file_keys(_ENV_PATH) | {k for k, v in os.environ.items() if v.strip()}
    return [k for k in _RECOMMENDED_KEYS if k not in have]


def _print_keys_howto() -> None:
    print("""
How to (once, ~2 min — in your own editor, not here):
  1. In this folder:  cp .env.example .env      (if .env doesn't exist yet)
  2. Adzuna — register a free app at https://developer.adzuna.com
     → copy App ID + App Key into .env as:
         ADZUNA_APP_ID=...
         ADZUNA_APP_KEY=...
  3. JSearch — free tier at https://rapidapi.com (subscribe "JSearch")
     or https://openwebninja.com → into .env as:
         JSEARCH_API_KEY=...
  4. Save .env, come back here.""")


def _keys_gate() -> None:
    """Guided keys step at the start of interactive onboarding. Shown ONLY when a
    recommended key is missing; requires an explicit choice — never silently
    proceeds past missing keys, and never asks the user to type a key here."""
    missing = _missing_keys()
    if not missing:
        return
    present = [k for k in _RECOMMENDED_KEYS if k not in missing]
    print("── Free API keys — strongly recommended ────────────────────────────────")
    print("Strongly recommended (free, ~2 min): add your own API keys — they unlock")
    print("India-native listings (Naukri-style) beyond company career pages. Without")
    print("them you still get company-ATS jobs, but fewer India-specific ones.")
    print(f"\n  Missing: {', '.join(missing)}"
          + (f"   (already set: {', '.join(present)})" if present else ""))
    print("  • Adzuna  → https://developer.adzuna.com")
    print("  • JSearch → https://rapidapi.com (\"JSearch\") or https://openwebninja.com")
    print("  Keys go in the .env file in this folder — never typed into this tool.\n")
    while True:
        choice = _select("API keys — what would you like to do?", [
            "I've added them — re-check .env and confirm",
            "Show me how — links + steps, then re-check",
            "Skip — ATS-only (fewer India-native jobs)",
        ])
        if choice.startswith("Skip"):
            print("Skipping keys: discovery runs on the free company-ATS floor only "
                  "(you can add keys to .env any time — no re-setup needed).")
            return
        if choice.startswith("Show me how"):
            _print_keys_howto()
        missing = _missing_keys()                    # both non-skip options re-check
        if not missing:
            print("✓ found all keys in .env — India-native channels are on.")
            return
        print(f"Still missing: {', '.join(missing)} — pick again (or Skip).\n")


def seed_config_files(force: bool = False, skip: tuple = ()) -> list[str]:
    """Create any missing live config files from their shipped templates. `skip`
    names live paths to leave alone (onboarding skips config/profile.yml — that is
    written from the user's answers, never seeded as a placeholder to proceed with)."""
    created = []
    for ex, live in _SEED_PAIRS:
        if live in skip:
            continue
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
# function.out_of_scope drives the rubric's wrong-function cap. Left EMPTY by design (B-2). One persona's opposites are another's core function —
# defaulting to "ML research / data science / backend" pre-declared a data scientist's
# own function out of scope. An unset out_of_scope means the rubric's wrong-function
# cap simply doesn't fire on an unknown, rather than firing wrongly. The agent proposes
# real values from the résumé after setup (see modes/onboarding.md).
_DEFAULT_OUT_OF_SCOPE: list[str] = []
_DEFAULT_HARD_CONSTRAINTS = ["Must be India-based or fully remote (no relocation outside India)."]


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


def validate_answers(a: dict) -> list[str]:
    """Return a list of problems with the answers (empty = valid).

    NOTHING is strictly required anymore — every dimension is skippable and
    _answers_to_profile fills a safe, doctor-ready default (work_mode→mix,
    honest_ceiling→mid, name/city→derived, target_roles→empty is fine: the rubric
    scores against `function.*` + the résumé, not target_roles). The résumé itself
    is still required, but that is enforced in write_from_answers, not here. This
    function only FORMAT-checks values that ARE supplied, so the --answers
    automation path can't write a malformed value (bad number, unknown enum)."""
    errs: list[str] = []

    roles = a.get("target_roles")
    if roles is not None and not isinstance(roles, list):
        errs.append("target_roles must be a list of role titles")
    wm = a.get("work_mode")
    if wm is not None and str(wm).strip() and str(wm).lower() not in _WORK_MODES:
        errs.append(f"work_mode must be one of {sorted(_WORK_MODES)}")
    hc = a.get("honest_ceiling")
    if hc is not None and str(hc).strip() and str(hc).lower() not in _CEILINGS:
        errs.append(f"honest_ceiling must be one of {sorted(_CEILINGS)}")
    for k in ("years_total", "years_in_function", "floor_ctc_lpa"):
        if a.get(k) is not None and str(a.get(k)).strip() != "" and _num(a.get(k)) is None:
            errs.append(f"invalid number: {k}")
    # factual sanity — these numbers feed the seniority gate, so a wrong value silently
    # breaks scoring. Cheap deterministic checks: plausible range + no impossibility.
    yt, yf = _num(a.get("years_total")), _num(a.get("years_in_function"))
    for name, val in (("years_total", yt), ("years_in_function", yf)):
        if val is not None and not (0 <= val <= 45):
            errs.append(f"{name} must be between 0 and 45 (got {val})")
    if yt is not None and yf is not None and yf > yt:
        errs.append(f"years_in_function ({yf:g}) can't exceed years_total ({yt:g})")
    return errs


def _answers_to_profile(a: dict) -> dict:
    """Map the flat answers onto the nested config/profile.yml schema. function.*
    is auto-derived from target_roles (the agent reviews out_of_scope afterward).

    Only work_mode + target_roles are guaranteed by validate_answers; every other
    field is filled here with a safe, doctor-ready fallback (non-empty name / city
    / ceiling) so a minimal 'answered work-mode + relocate only' run still writes a
    valid profile."""
    roles = [str(r).strip() for r in (a.get("target_roles") or []) if str(r).strip()]
    wm = str(a.get("work_mode") or "mix").lower()
    onsite = [str(c).strip() for c in (a.get("onsite_cities") or []) if str(c).strip()]
    email = (a.get("email") or "").strip()
    full_name = ((a.get("full_name") or "").strip()
                 or (email.split("@")[0] if email else "") or "Candidate")
    base_city = (a.get("base_city") or "").strip()
    city_only = base_city.split(",")[0].strip()
    if wm == "onsite":
        remote_ok, hybrid_ok = False, False
    else:                                    # remote / hybrid / mix
        remote_ok, hybrid_ok = True, True
        onsite = onsite or ([city_only] if city_only else [])
    base_city = base_city or (onsite[0] if onsite else "India")
    return {
        "candidate": {"full_name": full_name, "location": base_city, "email": email},
        "seniority": {"years_total": _num(a.get("years_total")),
                      "years_in_function": _num(a.get("years_in_function")),
                      "current_title": (a.get("current_title") or "").strip(),
                      "honest_ceiling": str(a.get("honest_ceiling") or "mid").lower(),
                      "honest_ceiling_ic": str(a.get("honest_ceiling_ic") or "mid").lower()},
        "function": {"actual": a.get("function_actual")
                     or ("Delivery / implementation / program management"
                         + (f" across: {', '.join(roles[:3])}" if roles else " (see résumé)")),
                     "in_scope": a.get("function_in_scope") or list(roles),
                     "out_of_scope": a.get("function_out_of_scope") or list(_DEFAULT_OUT_OF_SCOPE)},
        "target_roles": {"primary": list(roles),
                         "archetypes": [{"name": r, "fit": "primary"} for r in roles]},
        "domains": {"strong": a.get("domains_strong") or [], "open_to": a.get("domains_open_to") or []},
        "compensation": {"current_ctc_lpa": _num(a.get("current_ctc_lpa")),
                         "target_ctc_lpa": _num(a.get("target_ctc_lpa")),
                         "floor_ctc_lpa": _num(a.get("floor_ctc_lpa")),
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


# Top-level profile fields that may be UPDATED in place after setup (e.g. the agent
# proposing better target_roles). Anything else requires re-running onboarding.
_PATCHABLE = ("target_roles", "function_out_of_scope", "honest_ceiling", "base_city",
              "floor_ctc_lpa", "work_mode")


def patch_profile(updates: dict) -> dict:
    """Surgically update whitelisted fields in an EXISTING config/profile.yml, leaving
    everything else exactly as written (name, relocate, curated function.out_of_scope …).
    This is the post-setup refinement path — NOT a regeneration from flat answers (which
    would default-fill the untouched fields). Unknown keys are refused with a clear
    message. work_mode maps to the [GATE] remote_ok/hybrid_ok flags (relocate untouched)."""
    dest = os.path.join(ROOT, "config", "profile.yml")
    if not os.path.exists(dest) or _profile_is_placeholder(dest):
        return {"error": "no real config/profile.yml to update — run onboarding first"}
    unknown = [k for k in updates if k not in _PATCHABLE]
    if unknown:
        return {"error": f"--set {', '.join(unknown)} not supported for in-place update "
                         f"(patchable: {', '.join(_PATCHABLE)}); re-run onboarding for other fields"}
    prof = yaml.safe_load(open(dest, encoding="utf-8")) or {}
    applied: dict = {}
    for k, v in updates.items():
        if k == "target_roles":
            roles = [str(r).strip() for r in (v if isinstance(v, list) else _split(str(v))) if str(r).strip()]
            prof.setdefault("target_roles", {})["primary"] = roles
            prof["target_roles"]["archetypes"] = [{"name": r, "fit": "primary"} for r in roles]
            prof.setdefault("function", {})["in_scope"] = list(roles)   # mirror → reaches prescreen
            applied["target_roles"] = roles
        elif k == "function_out_of_scope":
            vals = [str(x).strip() for x in (v if isinstance(v, list) else _split(str(v))) if str(x).strip()]
            prof.setdefault("function", {})["out_of_scope"] = vals
            applied["function_out_of_scope"] = vals
        elif k == "honest_ceiling":
            if str(v).lower() not in _CEILINGS:
                return {"error": f"honest_ceiling must be one of {sorted(_CEILINGS)}"}
            prof.setdefault("seniority", {})["honest_ceiling"] = str(v).lower()
            applied["honest_ceiling"] = str(v).lower()
        elif k == "base_city":
            prof.setdefault("location", {})["base_city"] = str(v).strip()
            applied["base_city"] = str(v).strip()
        elif k == "floor_ctc_lpa":
            prof.setdefault("compensation", {})["floor_ctc_lpa"] = _num(v)
            applied["floor_ctc_lpa"] = _num(v)
        elif k == "work_mode":
            if str(v).lower() not in _WORK_MODES:
                return {"error": f"work_mode must be one of {sorted(_WORK_MODES)}"}
            loc = prof.setdefault("location", {})
            loc["remote_ok"] = str(v).lower() != "onsite"    # onsite → both False; else both True
            loc["hybrid_ok"] = str(v).lower() != "onsite"    # relocate (willing_to_relocate) untouched
            applied["work_mode"] = str(v).lower()
    with open(dest, "w", encoding="utf-8") as f:
        f.write("# job-finder profile (User Layer — written by onboarding from your answers).\n"
                "# [GATE] fields feed the disqualifier checks in prompts/_rubric.md.\n\n")
        yaml.safe_dump(prof, f, sort_keys=False, allow_unicode=True)
    return {"updated": applied}


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


# ── Direct-run interactive onboarding (the USER runs `python -m jobfinder onboard`) ──
# Arrow-key menus for the constrained fields via questionary when present; a plain
# numbered input() menu otherwise. Reuses write_from_answers to write both files.
_RESUME_CHOICES = [
    "Paste résumé text (end with Ctrl-D)",
    "Give a file path (.pdf / .docx / .md / .txt)",
    "Paste LinkedIn profile text (end with Ctrl-D)",
]
_CEILING_CHOICES = ["Intern", "Junior", "Mid", "Senior", "Lead", "Manager", "Director"]
_WORKMODE_CHOICES = ["Remote", "Hybrid", "On-site", "Open to a mix"]
_WORKMODE_MAP = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite", "Open to a mix": "mix"}


def _split(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


# ── Best-effort résumé field derivation (deterministic, never raises) ────────
# Minimise compulsory input: parse what the résumé already states and present it
# as an editable DEFAULT (Enter accepts). Anything we can't derive degrades to an
# OPTIONAL prompt — never a hard block. Only work-mode + relocate are asked fresh.
_ROLE_KEYWORDS = (
    "manager", "engineer", "analyst", "lead", "developer", "consultant", "designer",
    "architect", "scientist", "specialist", "coordinator", "director", "head", "officer",
    "associate", "product", "program", "project", "strategist", "administrator", "executive",
    "founder", "marketer", "recruiter", "accountant", "operations", "delivery", "scrum",
    "devops", "sre",
)
_INDIAN_CITIES = (
    "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Mumbai", "New Delhi", "Delhi", "Gurugram",
    "Gurgaon", "Noida", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Kochi", "Cochin",
    "Chandigarh", "Indore", "Coimbatore", "Thiruvananthapuram", "Trivandrum", "Nagpur",
    "Vadodara", "Bhubaneswar", "Mysuru", "Mysore",
)
_NAME_BLOCK = {"curriculum vitae", "resume", "résumé", "cv", "profile", "summary",
               "biodata", "bio data", "contact", "objective"}
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december",
           "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec")
_MONTH_RE = r"\b(?:" + "|".join(_MONTHS) + r")\b"
_YEAR_RE = r"\b(?:19|20)\d{2}\b"
# Connective/prose markers a real job TITLE never contains — reject sentence fragments.
_ROLE_STOP = (" and ", " with ", " the ", " across ", " that ", " into ", " using ", " for the ")
_EDU_WORDS = ("bachelor", "master", "b.arch", "b.tech", "m.tech", "b.e.", "m.e.", "mba",
              "ph.d", "phd", "diploma", "degree", "university", "institute", "college")


def _clean_role(seg: str) -> str | None:
    """Reduce ONE header/segment to a clean role phrase, or None. Cuts trailing
    company/date noise at the first hard boundary (tab / 2+ spaces / bullet / ':' /
    ',' / spaced-dash / month / 4-digit year), then REJECTS anything that isn't a
    short title: too long/short, >6 words, a sentence fragment (connective words),
    an education line, or still carrying a date. Silent-wrong is worse than absent."""
    seg = re.split(r"\t| {2,}|[•·]|:|,| [-–—] ", seg)[0]              # first hard boundary
    seg = re.split(_MONTH_RE + "|" + _YEAR_RE, seg, flags=re.I)[0]    # drop a date onward
    seg = seg.strip(" \t-–—|,:•·/()").strip()
    low = seg.lower()
    if not (3 <= len(seg) <= 45) or len(seg.split()) > 6:
        return None
    if any(s in f" {low} " for s in _ROLE_STOP):                     # prose, not a title
        return None
    if any(e in low for e in _EDU_WORDS):                            # a degree line, not a role
        return None
    if re.search(_YEAR_RE, seg) or re.search(_MONTH_RE, low):        # a date survived → reject
        return None
    if not any(k in low for k in _ROLE_KEYWORDS):                    # no role-family word left
        return None
    return seg


def _ceiling_from_years(years) -> str:
    """A conservative honest-ceiling GUESS from tenure — used only to PRE-SELECT
    the arrow menu (the user confirms/overrides). People-management levels
    (Manager/Director) stay an explicit choice: tenure alone never implies them."""
    y = _num(years)
    if y is None:
        return "Mid"
    if y < 2:
        return "Junior"
    if y < 5:
        return "Mid"
    if y < 9:
        return "Senior"
    return "Lead"


def _parse_resume_fields(text: str) -> dict:
    """Return any of {full_name, email, base_city, years_total, target_roles} the
    résumé states, best-effort. Deterministic and defensive — any parse quirk just
    yields fewer keys, never an exception (onboarding must not break on a résumé)."""
    out: dict = {}
    try:
        lines = [ln.strip() for ln in (text or "").splitlines()]
        nonempty = [ln for ln in lines if ln]
        head = nonempty[:12]

        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")
        if m:
            out["email"] = m.group(0)

        for ln in head[:5]:                      # name: a header line shaped like a person's name
            toks = ln.split()
            if (2 <= len(toks) <= 4 and "@" not in ln and len(ln) <= 40
                    and ln.lower() not in _NAME_BLOCK
                    and not any(ch.isdigit() for ch in ln)
                    and all(t[:1].isalpha() for t in toks)
                    and not any(k in ln.lower() for k in _ROLE_KEYWORDS)):
                out["full_name"] = ln
                break

        for ln in head:                          # base_city: header line naming a known Indian city
            for c in _INDIAN_CITIES:
                if re.search(rf"\b{re.escape(c)}\b", ln, re.I):
                    out["base_city"] = f"{c}, India"
                    break
            if "base_city" in out:
                break

        # years_total: FULL career span — earliest year → latest end (Present → today),
        # not a single job's range (which undercounted). Sanity-capped ≤ 45.
        yrs = [int(y) for y in re.findall(r"\b(?:19[89]\d|20[0-4]\d)\b", text or "")]
        if yrs:
            present = re.search(r"\b(?:present|current|till date|to date|ongoing|now)\b", text or "", re.I)
            hi = datetime.date.today().year if present else max(yrs)
            span = hi - min(yrs)
            if 0 < span <= 45:
                out["years_total"] = span

        # target_roles: clean, distinct title phrases. Consider a line only if it's in
        # the header (top 3) OR is a dated experience line — this skips summary prose,
        # competency lists, and bullet fragments. SPLIT pipe/slash headers into multiple
        # roles ("AI Solutions Consultant | Business Analyst" → both), then _clean_role.
        roles: list[str] = []
        for idx, ln in enumerate(nonempty):
            low = ln.lower()
            if "@" in ln or not (3 <= len(ln) <= 120) or not any(k in low for k in _ROLE_KEYWORDS):
                continue
            if idx >= 3 and not re.search(_MONTH_RE + "|" + _YEAR_RE, ln, re.I):
                continue                          # not a header line and not dated → not a title line
            for seg in re.split(r"\s*\|\s*|\s+/\s+", ln):
                r = _clean_role(seg)
                if r and r.lower() not in [x.lower() for x in roles]:
                    roles.append(r)
            if len(roles) >= 4:
                break
        if roles:
            out["target_roles"] = roles[:4]
    except Exception:                            # noqa: BLE001 — derivation is best-effort, never fatal
        return out
    return out


def _ask_default(label: str, default: str) -> str:
    """Editable default: `label [default]:` (Enter accepts, typed text overrides).
    With no derived default, an OPTIONAL prompt the user may skip with Enter."""
    if default:
        return _input(f"{label} [{default}]: ", default)
    return _input(f"{label} (optional, Enter to skip): ", "")


def _select(question: str, choices: list[str], default: str | None = None) -> str:
    """Arrow-key select via questionary if installed; else a plain numbered input() menu."""
    try:
        import questionary                     # optional dep — clean text fallback below if absent
        ans = questionary.select(question, choices=choices, default=default).ask()
        if ans is None:                        # user pressed Ctrl-C
            raise KeyboardInterrupt
        return ans
    except ImportError:
        print(question)
        for i, c in enumerate(choices, 1):
            print(f"   {i}. {c}")
        for _ in range(5):                       # retry cap — never loop forever on bad/absent input
            v = _input(f"Reply with the number{' (Enter = default)' if default else ''}: ")
            if not v and default:                # a bare Enter accepts the default
                return default
            if v.isdigit() and 1 <= int(v) <= len(choices):
                return choices[int(v) - 1]
            if v in choices:
                return v
            print("   (pick a number from the list)")
        return default or choices[0]             # give up cleanly after the cap → default / first


def _read_pasted() -> str:
    """Read a pasted block until EOF (Ctrl-D at line start) OR a lone `END` line.
    The END sentinel spares the user the 'Ctrl-D only signals EOF at line start'
    dance (needing Enter-then-Ctrl-D, sometimes twice). Echoes a receipt so the
    user can see the paste registered."""
    buf = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":        # explicit terminator — no Ctrl-D needed
            break
        buf.append(line)
    text = "\n".join(buf)
    print(f"✓ read {len(buf)} lines ({len(text.split())} words)")
    return text


def _ask_resume() -> dict:
    choice = _select("How will you provide your résumé?", _RESUME_CHOICES)
    idx = _RESUME_CHOICES.index(choice)
    if idx == 1:                               # file path
        return {"resume_path": _input("Résumé file path: ")}
    what = "résumé" if idx == 0 else "LinkedIn profile text"
    print(f"Paste your {what}, then press Enter and Ctrl-D (or type END on its own line):")
    return {"resume_text": _read_pasted()}


def _ask_workmode(a: dict) -> None:
    a["work_mode"] = _WORKMODE_MAP[_select("Work-mode:", _WORKMODE_CHOICES, default="Open to a mix")]
    if a["work_mode"] in ("hybrid", "onsite", "mix"):
        a["onsite_cities"] = _split(_input("On-site city/cities (comma-separated): "))


def _collect_answers() -> dict:
    a: dict = {}
    parsed: dict = {}
    if not os.path.exists(os.path.join(ROOT, "resume.md")):
        a.update(_ask_resume())
        text = a.get("resume_text") or ""
        if not text and a.get("resume_path"):
            try:
                text = load_resume(os.path.expanduser(a["resume_path"]))
            except Exception:            # noqa: BLE001 — best-effort; write_from_answers surfaces real load errors
                text = ""
        parsed = _parse_resume_fields(text)
        if parsed:
            print("\nRead your résumé — filled in what I could. "
                  "Press Enter to accept, or type to change:")

    # Derived-with-Enter-accept — never a blank required prompt ──────────────
    a["full_name"] = _ask_default("Full name", parsed.get("full_name", ""))
    a["email"] = _ask_default("Email", parsed.get("email", ""))
    a["base_city"] = _ask_default("Base city", parsed.get("base_city", ""))
    shown = ", ".join(parsed.get("target_roles") or [])
    raw = _input(f"Target roles (comma-separated, optional) [{shown}]: " if shown
                 else "Target roles (comma-separated, optional — Enter to skip): ")
    a["target_roles"] = _split(raw) if raw else list(parsed.get("target_roles") or [])
    yt = _ask_default("Years of experience",
                      str(parsed["years_total"]) if parsed.get("years_total") else "")
    if yt:
        a["years_total"] = _num(yt)
    yf = _input("Years in your target function (optional, Enter to skip): ")
    if yf:
        a["years_in_function"] = _num(yf)
    ceiling = _select(
        "Honest ceiling (highest level you can credibly claim today):",
        _CEILING_CHOICES + ["Skip / Not sure"],
        default=_ceiling_from_years(a.get("years_total")))
    a["honest_ceiling"] = "mid" if ceiling.lower().startswith("skip") else ceiling.lower()

    # The few things a résumé can't decide — the ONLY strictly-required asks ──
    print("\nNow the few things your résumé can't tell me:")
    _ask_workmode(a)
    a["willing_to_relocate"] = _select("Open to relocating?", ["No", "Yes"], default="No") == "Yes"

    # Optional — Enter to skip ───────────────────────────────────────────────
    floor = _input("Comp floor / walk-away LPA (optional, Enter = no comp filter): ")
    if floor:
        a["floor_ctc_lpa"] = _num(floor)
    tgt = _num(_input("Target comp (LPA, optional): "))
    if tgt:
        a["target_ctc_lpa"] = tgt
    hc = _input("Hard constraints (comma-separated, optional): ")
    if hc:
        a["hard_constraints"] = _split(hc)
    return a


def _refill(a: dict, res: dict) -> None:
    """Re-ask only what the last write flagged. Reads BOTH the error string and the
    problems list — a résumé failure carries an `error` but no `problems`, so
    keying on problems alone would re-ask nothing and spin. The résumé is the only
    thing that can persistently fail now (everything else is optional/defaulted)."""
    t = (res.get("error", "") + " " + " ".join(res.get("problems", []))).lower()
    if "résumé" in t or "resume" in t:
        a.pop("resume_text", None)
        a.pop("resume_path", None)
        a.update(_ask_resume())
    if "target_roles" in t:
        a["target_roles"] = _split(_input("Target roles (comma-separated, optional): "))
    if "work_mode" in t or "onsite_cities" in t:
        _ask_workmode(a)
    if "years" in t:                          # factual years problem → re-ask both (skippable)
        yt = _input("Years of total experience (optional, Enter to skip): ")
        yf = _input("Years in your target function (optional, Enter to skip): ")
        a["years_total"] = _num(yt) if yt else None
        a["years_in_function"] = _num(yf) if yf else None


def _interactive() -> int:
    # No-TTY refuse: an agent-spawned run has no keyboard, so do NOT silently
    # seed-and-collect-nothing. Point to the deterministic --answers path instead.
    if not sys.stdin.isatty():
        print("This interactive setup needs a real terminal (a keyboard).", file=sys.stderr)
        print("• Run it yourself:   python -m jobfinder onboard          (in YOUR terminal)", file=sys.stderr)
        print("• From an AI agent:  python -m jobfinder onboard --answers <file.json>", file=sys.stderr)
        return 2

    prof = os.path.join(ROOT, "config", "profile.yml")
    if os.path.exists(prof) and not _profile_is_placeholder(prof):
        if _select("You already have a profile. Redo setup?", ["No, keep it", "Yes, redo"]) == "No, keep it":
            print("Keeping your existing profile. Nothing changed.")
            return 0

    print("── job-finder onboarding ──  (I'll write resume.md + config/profile.yml for you)\n")
    seed_config_files(skip=("config/profile.yml",))   # config defaults; profile comes from answers
    try:
        _keys_gate()                                  # guided free-keys step (explicit choice, skippable)
        a = _collect_answers()
        for attempt in range(3):               # retry CAP — a bad résumé can never loop forever
            res = write_from_answers(a, force=True)
            if not res.get("error"):
                break
            print(f"\n✗ {res['error']}")
            for pr in res.get("problems", []):
                print(f"   - {pr}")
            if attempt < 2:
                print("Let's fix that.\n")
                _refill(a, res)
        else:                                  # 3 tries exhausted (bad résumé, or a value never fixed)
            detail = "; ".join(res.get("problems", [])) or res.get("error", "setup incomplete")
            print(f"\n✗ Couldn't complete setup after 3 tries ({detail}). Re-run "
                  "`python -m jobfinder onboard` when ready.")
            return 1
    except (KeyboardInterrupt, EOFError):
        print("\n(cancelled — nothing written)")
        return 1

    print(f"\n✓ wrote {', '.join(res['wrote'])}")
    oos = _answers_to_profile(a)["function"]["out_of_scope"]
    if oos:
        print(f"→ Roles you'll be gated OUT of (function.out_of_scope): {', '.join(oos)}")
        print("  Edit config/profile.yml if that's wrong — it drives the wrong-function gate.")
    else:
        print("→ function.out_of_scope is empty — the wrong-function gate won't fire until it's set.")
        print("  Say 'find me jobs' in your CLI and it can propose one from your résumé.")
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
    if a.set and not a.answers:
        # POST-SETUP refinement: --set alone patches the EXISTING profile in place
        # (e.g. the agent proposing better target_roles) — never regenerates it.
        updates = {}
        for kv in a.set:
            k, _, v = kv.partition("=")
            updates[k.strip()] = _coerce(v)
        res = patch_profile(updates)
        print(json.dumps(res, ensure_ascii=False))
        return 1 if res.get("error") else 0
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
        # No TTY here, so no keys menu — surface missing optional keys in the
        # result instead (never silent, never a prompt, never a key value).
        if not res.get("error"):
            _mk = _missing_keys()
            if _mk:
                res["keys_note"] = (f"optional discovery keys missing ({', '.join(_mk)}) — "
                                    "discovery runs ATS-only (fewer India-native listings); "
                                    "see .env.example for the free signup links")
        print(json.dumps(res, ensure_ascii=False))
        return 1 if res.get("error") else 0
    if a.health_check is not None:
        print(json.dumps(cli_adapter.health_check(a.health_check or None), ensure_ascii=False))
        did = True
    return 0 if did else _interactive()
