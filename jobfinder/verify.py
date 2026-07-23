"""Verifiability gate — never recommend a job the tool couldn't actually read.

A posting is scoreable only if BOTH hold:
  (a) we have real JD text to score against, and
  (b) the link points at a SPECIFIC posting — not a bare domain or a careers/
      list landing page.

This is a DETERMINISTIC classifier (no LLM). It runs once after `enrich` (with
the fetched JD) and again at render time (URL-only). Anything it flags is routed
to the "⚠️ Couldn't verify — check manually" bucket and is NEVER shown as APPLY/
STRETCH, whatever a provisional score might say — the whole point is to not vouch
for a job we couldn't read.

Status:
  • "ok"           — real JD + a specific job link.
  • "no_jd"        — JD text empty / too short to score honestly.
  • "non_job_link" — bare domain, or a careers/list landing with no job id.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .discovery import link_resolver

# A JD shorter than this (stripped) is too thin to score honestly. Tunable.
MIN_JD_CHARS = 200

# A path that is itself a listing / landing surface (no specific posting).
_LANDING_RE = re.compile(
    r"/(careers?|jobs?|job-?search|openings?|vacancies|positions?|opportunities|"
    r"join-?us|work-?with-?us|our-?team|talent|search|listings?)/?$",
    re.I,
)

# Embedded-ATS boards pin ONE specific posting via a job-id QUERY param on a
# landing-looking path (…/careers/?gh_jid=4012345 — the Greenhouse embed pattern;
# 175/175 URL-level rejects in the 2026-07 census were exactly this). Count ONLY
# a whitelisted id param with a numeric value — never "any query string": a
# landing page with utm/fbclid noise must still classify as a landing page.
_QUERY_ID_RE = re.compile(r"(?:^|&)(?:gh_jid|jid|job_?id|posting|vacancy)=\d{4,}", re.I)


def classify(url: str, jd_text: str | None) -> tuple[str, str]:
    """Return (status, human-readable reason).

    Pass the fetched JD as `jd_text` post-enrich to check (a); pass `jd_text=None`
    at render time when only the link (b) can be re-checked."""
    # (a) JD presence — only meaningful when we were handed the JD text.
    if jd_text is not None:
        body = (jd_text or "").strip()
        if len(body) < MIN_JD_CHARS:
            return "no_jd", f"JD text too thin to score ({len(body)} chars < {MIN_JD_CHARS})"

    # (b) Does the link resolve to a SPECIFIC posting?
    u = (url or "").strip()
    if not u:
        return "non_job_link", "no link on the posting"
    parsed = urlparse(u if "://" in u else "https://" + u)
    path = parsed.path or ""
    # A job id in the PATH (…/jobs/4012345) or a whitelisted id QUERY param
    # (…/careers/?gh_jid=4012345). Query check lives HERE, not in
    # _distinctive_token — that token's redirect-survival semantics back the
    # liveness check and must stay path-only.
    has_job_id = bool(link_resolver._distinctive_token(u)) or bool(_QUERY_ID_RE.search(parsed.query or ""))
    bare_domain = path.rstrip("/") == ""
    is_landing = bool(_LANDING_RE.search(path))
    if not has_job_id and (bare_domain or is_landing):
        where = "a bare domain" if bare_domain else "a careers/list landing page"
        return "non_job_link", f"link is {where} with no specific job id — can't confirm the posting"

    return "ok", ""


def is_scoreable(url: str, jd_text: str | None) -> bool:
    return classify(url, jd_text)[0] == "ok"
