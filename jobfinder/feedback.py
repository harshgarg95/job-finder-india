"""File-based feedback loop — the product's core differentiator.

When the user corrects a result ("wouldn't apply", "wrong location/level/domain",
"good match"), it persists to data/feedback.* and **retunes future scoring** with
no statistical ML: corrections are (a) replayed into the scoring prompt as binding
lessons, and (b) used to suppress already-rejected jobs from future results.

career-ops's own issue #35 notes nobody built this loop. It is User-Layer data
(never leaves the machine; gitignored).
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FB_JSONL = os.path.join(DATA, "feedback.jsonl")
FB_MD = os.path.join(DATA, "feedback.md")

# Two top-level calls (owner's model): you either Applied, or you Wouldn't apply
# (with an optional reason). Both suppress the job from future recommendations —
# you've made your call on it. The reasons under "wouldn't apply" are the signal
# that retunes scoring. (Latest choice per job wins — see _latest().)
ACTIONS = {
    "applied":        ("Applied", True),          # you applied → tracked application
    "wouldnt_apply":  ("Wouldn't apply", True),   # passed, no specific reason
    "wrong_location": ("Wrong location", True),   # ── reasons for "wouldn't apply" ──
    "wrong_level":    ("Wrong seniority", True),
    "wrong_function": ("Wrong function", True),
    "wrong_domain":   ("Wrong domain", True),
    "wrong_comp":     ("Comp too low", True),
}
TRACKED = {"applied"}                              # actions that = a tracked application
REASONS = ("wrong_location", "wrong_level", "wrong_function", "wrong_domain", "wrong_comp")


def _latest(entries: list[dict]) -> list[dict]:
    """Keep only the most recent correction per job_id — so changing your mind
    (re-clicking a different option) overrides the earlier choice."""
    by_job = {}
    for e in entries:
        by_job[e["job_id"]] = e
    return list(by_job.values())


def record(job_id: str, company: str, title: str, url: str, action: str,
           note: str = "", ts: float | None = None) -> dict:
    """Append one correction to the feedback store. Returns the entry."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown action '{action}'. Known: {', '.join(ACTIONS)}")
    os.makedirs(DATA, exist_ok=True)
    entry = {
        "ts": ts if ts is not None else time.time(),
        "job_id": job_id, "company": company, "title": title, "url": url,
        "action": action, "note": note,
    }
    with open(FB_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    label = ACTIONS[action][0]
    when = time.strftime("%Y-%m-%d", time.localtime(entry["ts"]))
    line = f"- [{when}] **{label}** — {company} · {title}" + (f" — _{note}_" if note else "")
    header_needed = not os.path.exists(FB_MD) or os.path.getsize(FB_MD) == 0
    with open(FB_MD, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("# Feedback log\n\nYour corrections. The scorer reads these "
                    "to retune future results. (User Layer — never leaves your machine.)\n\n")
        f.write(line + "\n")
    return entry


def load() -> list[dict]:
    if not os.path.exists(FB_JSONL):
        return []
    out = []
    for ln in open(FB_JSONL, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def suppressed_ids(entries: list[dict] | None = None) -> set[str]:
    """job_ids whose latest call suppresses them (applied or wouldn't-apply)."""
    entries = load() if entries is None else entries
    return {e["job_id"] for e in _latest(entries)
            if ACTIONS.get(e["action"], ("", False))[1]}


def undo(job_id: str) -> int:
    """Remove all corrections for a job (the dashboard's 'change/undo'). Returns
    how many were removed; rewrites both feedback files."""
    entries = load()
    kept = [e for e in entries if e.get("job_id") != job_id]
    removed = len(entries) - len(kept)
    if removed:
        _write_all(kept)
    return removed


def _write_all(entries: list[dict]) -> None:
    """Rewrite both feedback files from scratch (used by undo)."""
    os.makedirs(DATA, exist_ok=True)
    with open(FB_JSONL, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    lines = ["# Feedback log", "",
             "Your corrections. The scorer reads these to retune future results. "
             "(User Layer — never leaves your machine.)", ""]
    for e in entries:
        label = ACTIONS.get(e["action"], (e["action"], False))[0]
        when = time.strftime("%Y-%m-%d", time.localtime(e.get("ts", 0)))
        note = f" — _{e['note']}_" if e.get("note") else ""
        lines.append(f"- [{when}] **{label}** — {e.get('company','')} · {e.get('title','')}{note}")
    with open(FB_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def lessons_digest(entries: list[dict] | None = None, limit: int = 40) -> str:
    """A compact, prompt-ready summary of past corrections, grouped by type, so
    the scorer applies them as binding lessons on the next run."""
    entries = _latest(load() if entries is None else entries)
    if not entries:
        return ""
    by_action = defaultdict(list)
    for e in entries[-limit:]:
        by_action[e["action"]].append(e)

    GUIDE = {
        "wrong_location": "Apply the location rule strictly for similar roles.",
        "wrong_level":    "Be stricter on seniority for similar roles.",
        "wrong_function": "Treat this function as out-of-scope going forward.",
        "wrong_domain":   "Weight the domain gap heavily for similar roles.",
        "wrong_comp":     "Respect the comp floor strictly for similar roles.",
        "wouldnt_apply":  "The user passed on these despite the score — down-rank similar roles.",
        "applied":        "The user APPLIED to these — confirmed-good fit; favor similar roles.",
    }
    lines = ["## PRIOR USER CORRECTIONS — binding lessons (apply on this run)",
             "The user has reviewed earlier results and gave the corrections below. "
             "Honor them: do not re-recommend what they rejected, and lean toward what they liked."]
    for action, items in by_action.items():
        label = ACTIONS.get(action, (action, False))[0]
        lines.append(f"\n**{label}** — {GUIDE.get(action, '')}")
        for e in items[:12]:
            note = f" ({e['note']})" if e.get("note") else ""
            lines.append(f"  - {e['company']} · {e['title']}{note}")
    return "\n".join(lines)


def stats(entries: list[dict] | None = None) -> dict:
    entries = _latest(load() if entries is None else entries)
    c = defaultdict(int)
    for e in entries:
        c[e["action"]] += 1
    return dict(c)
