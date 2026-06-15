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

# action key -> (human label, does it suppress the job from future results?)
# Suppress = don't re-surface as a NEW recommendation. Rejections suppress
# (you said no). "applied" also suppresses — you've ACTED on it, so it moves to
# your tracked applications rather than being re-recommended. "good_match" does
# NOT suppress — it's pure scoring feedback (you agree it fits) and stays visible.
ACTIONS = {
    "good_match":     ("Good match", False),   # agree it fits → favor similar; keep showing
    "applied":        ("Applied", True),        # you applied → track it, don't re-recommend
    "interested":     ("Interested", False),
    "not_interested": ("Not interested", True),
    "wouldnt_apply":  ("Wouldn't apply", True),
    "wrong_location": ("Wrong location", True),
    "wrong_level":    ("Wrong seniority", True),
    "wrong_function": ("Wrong function", True),
    "wrong_domain":   ("Wrong domain", True),
}
# actions that mean "I acted on / am tracking this application"
TRACKED = {"applied"}


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
    """job_ids the user rejected → don't show them again."""
    entries = load() if entries is None else entries
    return {e["job_id"] for e in entries
            if ACTIONS.get(e["action"], ("", False))[1]}


def lessons_digest(entries: list[dict] | None = None, limit: int = 40) -> str:
    """A compact, prompt-ready summary of past corrections, grouped by type, so
    the scorer applies them as binding lessons on the next run."""
    entries = load() if entries is None else entries
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
        "wouldnt_apply":  "Down-rank roles like these.",
        "not_interested": "The user is not interested in roles like these.",
        "good_match":     "These are the kind of role that genuinely fits — favor similar ones.",
        "applied":        "The user applied to these (confirmed-good fit).",
        "interested":     "The user was interested in these.",
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
    entries = load() if entries is None else entries
    c = defaultdict(int)
    for e in entries:
        c[e["action"]] += 1
    return dict(c)
