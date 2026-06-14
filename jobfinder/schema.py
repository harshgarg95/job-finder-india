"""Normalized JobPosting — the single shape every discovery channel emits.

It is a *union*: it must hold Naukri's structured experience/salary bands, a
LinkedIn-style coarse seniority enum, and bare ATS prose, so the scorer always
sees one consistent record regardless of where the job came from.

Design rule: fields a channel cannot fill are left as None (not faked). The
scorer is told explicitly when a field is unknown — honesty starts at the data
layer (see prompts/_rubric.md: "if the JD does not state X, say so").
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Optional


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


@dataclass
class JobPosting:
    # ── Identity / provenance ───────────────────────────────────────────────
    title: str
    company: str
    source: str                      # e.g. "ats:greenhouse", "google_jobs", "apify:naukri"
    url: str = ""
    location: str = ""
    description: str = ""             # full JD text when available, else short blurb
    posted_at: Optional[str] = None  # ISO date string if known

    # ── India-structured fields (populated when the channel provides them) ───
    experience_min: Optional[float] = None   # years
    experience_max: Optional[float] = None   # years
    salary_min: Optional[float] = None       # numeric, in salary_currency
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None    # "INR", "USD", ...
    salary_text: Optional[str] = None        # raw, e.g. "6-15 Lacs PA" when unparsed

    # ── Coarse signals (best-effort, channel-dependent) ─────────────────────
    seniority_level: Optional[str] = None    # LinkedIn-style enum, e.g. "Mid-Senior level"
    employment_type: Optional[str] = None    # full-time / contract / intern
    remote: Optional[str] = None             # "remote" / "hybrid" / "onsite"
    skills: list[str] = field(default_factory=list)

    # ── Discovery metadata ──────────────────────────────────────────────────
    fetched_at: Optional[str] = None

    # ── Link verification (Google Jobs "authentication") ────────────────────
    # Whether `url` was confirmed to resolve to a real JD/company page, and what
    # kind of source it points to (employer-ats | employer-site | linkedin |
    # naukri | board | unverified). ATS-channel jobs are employer-native, so they
    # are verified by construction.
    link_verified: Optional[bool] = None
    link_source: Optional[str] = None

    @property
    def id(self) -> str:
        """Stable id for dedup + 'never show twice'. URL is the strongest key;
        fall back to company+title when a channel omits the URL."""
        key = (self.url or f"{_slug(self.company)}::{_slug(self.title)}").strip().lower()
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "JobPosting":
        allowed = {f for f in cls.__dataclass_fields__}  # noqa: C416
        return cls(**{k: v for k, v in d.items() if k in allowed})

    def scoring_view(self) -> str:
        """Compact, honest JD block handed to the scoring rubric. Unknown
        structured fields are shown as 'not stated' rather than omitted, so the
        scorer never silently assumes a missing requirement is met."""
        def band(lo, hi, unit=""):
            if lo is None and hi is None:
                return "not stated"
            if lo is not None and hi is not None:
                return f"{lo:g}–{hi:g}{unit}"
            return f"{(lo if lo is not None else hi):g}{unit}"

        if self.salary_min is not None or self.salary_max is not None:
            cur = self.salary_currency or ""
            comp = f"{band(self.salary_min, self.salary_max)} {cur}".strip()
        else:
            comp = self.salary_text or "not stated"

        lines = [
            f"Title: {self.title}",
            f"Company: {self.company}",
            f"Location: {self.location or 'not stated'}",
            f"Remote: {self.remote or 'not stated'}",
            f"Experience required (years): {band(self.experience_min, self.experience_max)}",
            f"Seniority (as labelled): {self.seniority_level or 'not stated'}",
            f"Compensation: {comp}",
            f"Employment type: {self.employment_type or 'not stated'}",
            f"Source: {self.source}",
            f"URL: {self.url or 'n/a'}",
        ]
        if self.skills:
            lines.append(f"Listed skills: {', '.join(self.skills[:25])}")
        jd = (self.description or "").strip()
        lines.append("")
        lines.append("Job description:")
        lines.append(jd if jd else "(no description text was provided by the source)")
        return "\n".join(lines)
