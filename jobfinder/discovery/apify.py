"""Channel B, Layer 3 — Apify BYO-token, multi-platform (Naukri + LinkedIn + Indeed).

The legitimate way to reach the India-native boards and LinkedIn/Indeed that ATS
+ Google Jobs miss: cookieless community actors hitting each platform's PUBLIC
guest API (no login, no account-ban risk). OFF unless APIFY_TOKEN is set; runs
bill to the USER's own Apify account; the user accepts each board's ToS directly.

Each platform is one actor run per search (multiple title-URLs in a single run →
cost-efficient). Actor handles + field maps were confirmed against live runs on
2026-06-14; all are configurable so a user can swap actors without code changes.

Token is sent only as `Authorization: Bearer` to api.apify.com — never logged.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from .. import state
from ..schema import JobPosting
from .base import Query

API = "https://api.apify.com/v2/acts"
USERS_ME = "https://api.apify.com/v2/users/me"
TIMEOUT = 240
DEFAULT_PLATFORMS = ["naukri", "linkedin", "indeed"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _slug(s: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in s.lower()).split())


def _epoch_iso(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except Exception:
        return None


def _strip_html(html: str) -> str:
    if not html or "<" not in html:
        return html or ""
    try:
        from bs4 import BeautifulSoup
        import re as _re
        t = BeautifulSoup(html, "html.parser").get_text("\n")
        return _re.sub(r"\n{3,}", "\n\n", t).strip()
    except Exception:
        import re as _re
        return _re.sub(r"<[^>]+>", " ", html).strip()


# ── URL builders (per platform search URLs) ─────────────────────────────────
def _naukri_url(title, loc):
    # Naukri keyword search needs ?k= (a bare SEO slug returns loosely-related
    # jobs). Format mirrors the memo23 actor's own example input.
    base = f"https://www.naukri.com/{_slug(title)}-jobs"
    if loc and loc.lower() != "india":
        base += f"-in-{_slug(loc)}"
    url = f"{base}?k={quote(title)}"
    if loc and loc.lower() != "india":
        url += f"&l={quote(loc)}"
    return url


def _linkedin_url(title, loc):
    return (f"https://www.linkedin.com/jobs/search/?keywords={quote(title)}"
            f"&location={quote(loc or 'India')}&f_TPR=r2592000")  # last 30 days


def _indeed_url(title, loc):
    return f"https://in.indeed.com/jobs?q={quote(title)}&l={quote(loc or 'India')}"


# ── Output mappers (actor item -> JobPosting) ───────────────────────────────
def _map_naukri(it):
    """Robust across Naukri actors: memo23 (full HTML `description`, locations[],
    companyDetail.name, staticUrl) and epicscrapers (snippet `jobDescription`,
    placeholders[], companyName, jdURL)."""
    # location
    loc = ""
    if isinstance(it.get("locations"), list) and it["locations"]:
        loc = ", ".join(x.get("label", "") for x in it["locations"] if x.get("label"))
    if not loc:
        for p in it.get("placeholders", []) or []:
            if p.get("type") == "location":
                loc = p.get("label", "")
    # company
    company = it.get("companyName") or (it.get("companyDetail") or {}).get("name") \
        or it.get("staticCompanyName") or ""
    # full description (memo23 `description` HTML) preferred over snippet
    desc = _strip_html(it.get("description") or "") or (it.get("jobDescription") or "")
    # url
    jd = it.get("jdURL") or ""
    url = it.get("staticUrl") or it.get("jobUrl") or \
        (("https://www.naukri.com" + jd) if jd.startswith("/") else jd)
    sd = it.get("salaryDetail") or {}
    smin, smax = _f(sd.get("minimumSalary")), _f(sd.get("maximumSalary"))
    hidden = sd.get("hideSalary") or (smin in (0, None) and smax in (0, None))
    skills = it.get("keySkills") or it.get("tagsAndSkills") or ""
    skills = skills.split(",") if isinstance(skills, str) else (skills or [])
    return JobPosting(
        title=it.get("title", "") or "", company=company,
        source="apify:naukri", url=url, location=loc, description=desc,
        experience_min=_f(it.get("minimumExperience")), experience_max=_f(it.get("maximumExperience")),
        salary_min=None if hidden else smin, salary_max=None if hidden else smax,
        salary_currency=sd.get("currency"),
        salary_text="Not disclosed" if hidden else None,
        skills=[s for s in skills if s],
        posted_at=_epoch_iso(it.get("createdDate")),
        link_verified=True, link_source="apify:naukri")


def _map_linkedin(it):
    sal = it.get("salary")
    return JobPosting(
        title=it.get("title", "") or "", company=it.get("companyName", "") or "",
        source="apify:linkedin", url=it.get("link") or it.get("applyUrl", "") or "",
        location=it.get("location", "") or "",
        description=it.get("descriptionText") or "",
        seniority_level=it.get("seniorityLevel"), employment_type=it.get("employmentType"),
        salary_text=sal if isinstance(sal, str) else None,
        posted_at=it.get("postedAt"),
        link_verified=True, link_source="apify:linkedin")


def _map_indeed(it):
    if it.get("isExpired"):
        return None
    return JobPosting(
        title=it.get("positionName", "") or "", company=it.get("company", "") or "",
        source="apify:indeed", url=it.get("url") or it.get("externalApplyLink", "") or "",
        location=it.get("location", "") or "",
        description=it.get("description") or "",
        salary_text=it.get("salary") if isinstance(it.get("salary"), str) else None,
        employment_type=it.get("jobType") if isinstance(it.get("jobType"), str) else None,
        posted_at=it.get("postedAt"),
        link_verified=True, link_source="apify:indeed")


PLATFORMS = {
    "naukri": {
        # memo23 returns the FULL JD (epicscrapers gave snippets); cheapest + most-used.
        "actor": "memo23~naukri-scraper",
        "input": lambda titles, loc, lim: {"startUrls": [{"url": _naukri_url(t, loc)} for t in titles],
                                           "maximumJobs": lim},
        "map": _map_naukri,
    },
    "linkedin": {
        "actor": "curious_coder~linkedin-jobs-scraper",
        "input": lambda titles, loc, lim: {"urls": [_linkedin_url(t, loc) for t in titles],
                                           "count": max(10, lim), "scrapeCompany": False},
        "map": _map_linkedin,
    },
    "indeed": {
        "actor": "misceres~indeed-scraper",
        "input": lambda titles, loc, lim: {"startUrls": [{"url": _indeed_url(t, loc)} for t in titles],
                                           "maxItemsPerSearch": lim, "country": "IN"},
        "map": _map_indeed,
    },
}


# ── Auto-pause / auto-resume ─────────────────────────────────────────────────
# Apify bills the USER's own account. When credits run out (or quota/repeated
# timeout), we PAUSE the channel (persisted in data/.state), notify, and keep
# running the free ATS scan — we NEVER hard-fail the run. At the next run start
# a cheap, read-only probe auto-resumes the channel if credits are back.
_STATE = "apify"
_CREDIT_HINTS = ("payment required", "monthly usage", "hard limit", "usage limit",
                 "limit-exceeded", "limit exceeded", "exceeded", "insufficient",
                 "credit", "quota", "out of credit")


def _sources_apify(cfg: dict) -> dict:
    src = (cfg.get("sources", {}) or {}).get("apify")
    if src is not None:
        return src or {}
    # Back-compat: older configs kept the flag under profile.discovery.apify.
    return (cfg.get("discovery", {}) or {}).get("apify", {}) or {}


def is_paused() -> bool:
    return bool(state.read(_STATE).get("paused"))


def pause(reason: str) -> None:
    state.write(_STATE, {"paused": True, "reason": reason,
                         "paused_at": datetime.now(timezone.utc).isoformat()})
    print(f"⚠ Apify auto-paused: {reason}. Continuing with the free ATS scan only.",
          file=sys.stderr)


def resume() -> None:
    state.clear(_STATE)


def is_credit_or_quota_error(status: int, body: str) -> bool:
    """Out-of-credits / quota shape. HTTP 402 (Payment Required) is definitive;
    401/403/429 count only when the body carries a credit/quota message."""
    if status == 402:
        return True
    b = (body or "").lower()
    return status in (401, 403, 429) and any(h in b for h in _CREDIT_HINTS)


# Read-only usage endpoint + fields, VERIFIED live on 2026-06-18 against this
# account: /users/me → data.plan.maxMonthlyUsageUsd (the cap); /users/me/usage/
# monthly → data.totalUsageCreditsUsdAfterVolumeDiscount (consumed this cycle) +
# data.usageCycle.endAt (when it resets). We require a little headroom to resume.
USAGE_MONTHLY = "https://api.apify.com/v2/users/me/usage/monthly"
_MIN_HEADROOM_USD = 0.10


def probe(token: str) -> tuple[bool | None, str, float | None]:
    """Cheap, read-only credit/account check (NOT a scrape). Returns
    (available, note, remaining_usd):  available True=credits remain /
    False=exhausted / None=could-not-determine (transient, re-probe next run).
    remaining_usd is the USD headroom (None if the plan doesn't expose usage).

    Reads (verified live against this account, 2026-06-18):
      • GET /v2/users/me           → data.plan.maxMonthlyUsageUsd   (monthly cap, USD)
      • GET /v2/users/me/usage/monthly
            → data.totalUsageCreditsUsdAfterVolumeDiscount          (consumed this cycle)
            → data.usageCycle.endAt                                 (when it resets)
      remaining = maxMonthlyUsageUsd − totalUsageCreditsUsdAfterVolumeDiscount
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        me = requests.get(USERS_ME, headers=headers, timeout=20)
        if me.status_code != 200:
            if is_credit_or_quota_error(me.status_code, me.text):
                return False, f"users/me HTTP {me.status_code} (credits/quota)", 0.0
            return None, f"users/me HTTP {me.status_code}", None
        plan = ((me.json() or {}).get("data") or {}).get("plan") or {}
        limit = plan.get("maxMonthlyUsageUsd")

        used, resets = None, ""
        um = requests.get(USAGE_MONTHLY, headers=headers, timeout=20)
        if um.status_code == 200:
            ud = (um.json() or {}).get("data") or {}
            used = ud.get("totalUsageCreditsUsdAfterVolumeDiscount")
            resets = ((ud.get("usageCycle") or {}).get("endAt") or "")[:10]
    except Exception as e:  # noqa: BLE001
        return None, f"probe error: {e}", None

    if isinstance(limit, (int, float)) and isinstance(used, (int, float)):
        remaining = limit - used
        available = remaining >= _MIN_HEADROOM_USD
        note = f"${remaining:.2f} of ${limit:.0f} remaining" + (f", cycle resets {resets}" if resets else "")
        return available, note, remaining
    return True, "account reachable (usage fields not exposed)", None


def resolve(cfg: dict) -> dict:
    """Start-of-run, read-only resolution of the Apify channel — call this BEFORE
    discovery. Cheap probe only (no scrape). Returns:
        {"state": active | no-token | paused-no-credits | error | disabled,
         "reason": str, "credits": str|None}
    Side effects (state only, never raises): persists a pause on no-credits, and
    auto-resumes (clears the pause) the moment a probe shows credits are back — so
    the NEXT run recovers automatically. Apify is always OPTIONAL: any non-active
    state just means 'skip Apify, run ATS-only'.
    """
    sub = _sources_apify(cfg)
    if not sub.get("enabled"):
        return {"state": "disabled", "reason": "off in config/sources.yml",
                "credits": None, "remaining_usd": None}
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return {"state": "no-token", "reason": "no APIFY_TOKEN in .env",
                "credits": None, "remaining_usd": None}

    available, note, remaining = probe(token)
    if available is None:                                   # transient — re-probe next run
        return {"state": "error", "reason": note, "credits": None, "remaining_usd": None}
    if available:
        was_paused = is_paused()
        if was_paused:
            resume()                                        # credits returned → auto-resume
        return {"state": "active",
                "reason": ("credits returned — auto-resumed; " + note) if was_paused else note,
                "credits": note, "remaining_usd": remaining}
    pause(f"no credits ({note})")                           # persist; auto-resumes when probe ok
    return {"state": "paused-no-credits", "reason": note, "credits": note, "remaining_usd": remaining}


class ApifyProvider:
    id = "apify"

    def enabled(self, cfg: dict) -> bool:
        # Prefer the start-of-run resolution (run.py calls resolve() and stashes it),
        # so we don't probe twice. Only "active" runs the channel.
        resolved = cfg.get("apify_resolved")
        if isinstance(resolved, dict) and resolved.get("state"):
            if resolved["state"] == "active":
                return True
            self._skip = f"{resolved['state']} ({resolved.get('reason', '')})"
            return False

        # Fallback (resolve() not called): self-contained enable + auto-resume.
        sub = _sources_apify(cfg)
        if not sub.get("enabled"):
            self._skip = "off in config/sources.yml (set enabled: true + APIFY_TOKEN in .env)"
            return False
        if not os.environ.get("APIFY_TOKEN"):
            self._skip = "enabled but no APIFY_TOKEN in .env"
            return False
        if is_paused():
            st = state.read(_STATE)
            ok, note, _ = probe(os.environ["APIFY_TOKEN"])
            if ok:
                resume()
                print(f"✓ Apify credits look available again ({note}) — auto-resumed.", file=sys.stderr)
            else:
                self._skip = (f"auto-paused ({st.get('reason', 'credits/quota')}); "
                              f"probe: {note}. Running ATS-only.")
                return False
        return True

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            return []
        sub = _sources_apify(cfg)
        budget = (cfg.get("run") or {}).get("apify") or {}
        max_spend = float(budget.get("max_spend_usd_per_run", 0.50))
        max_items = int(budget.get("max_items", 200))
        actor_timeout = int(budget.get("actor_timeout_s", 300))

        # ── BEFORE: budget gate. effective_budget = min(per-run ceiling,
        #    remaining − headroom). <= 0 → skip, never scrape (never drains). ──
        remaining_before = (cfg.get("apify_resolved") or {}).get("remaining_usd")
        if remaining_before is None:
            _, _, remaining_before = probe(token)
        effective_budget = (min(max_spend, remaining_before - _MIN_HEADROOM_USD)
                            if remaining_before is not None else max_spend)
        if remaining_before is not None and effective_budget <= 0:
            self.last_errors = [f"skipped pre-scrape: effective budget ${effective_budget:.2f} "
                                f"<= 0 (remaining ${remaining_before:.2f}) — never drains the balance"]
            pause(f"effective budget ${effective_budget:.2f} <= 0 (remaining ${remaining_before:.2f})")
            return []

        platforms = sub.get("platforms", DEFAULT_PLATFORMS)
        actors = sub.get("actors", {})            # optional per-platform actor override
        per = min(int(sub.get("limit", max_items)), max_items)   # per-platform records, capped
        titles = query.titles[:6] or ([query.raw_keywords] if query.raw_keywords else [])
        headers = {"Authorization": f"Bearer {token}"}
        out, errors, timeouts = [], [], 0
        t0 = time.monotonic()

        # ── DURING: bound the scrape with Apify-NATIVE limits, not just ours. ──
        for plat in platforms:
            spec = PLATFORMS.get(plat)
            if not spec:
                errors.append(f"{plat}: unknown platform"); continue
            actor = actors.get(plat, spec["actor"]).replace("/", "~")
            try:
                r = requests.post(
                    f"{API}/{actor}/run-sync-get-dataset-items",
                    # Run options: maxItems = platform-enforced record cap,
                    # timeout = kill a scrape that runs too long, limit = items returned.
                    params={"timeout": actor_timeout, "memory": 1024,
                            "maxItems": max_items, "limit": per},
                    # Actor INPUT cap, per the live schemas: maximumJobs (naukri) /
                    # count (linkedin) / maxItemsPerSearch (indeed) — set to `per`.
                    json=spec["input"](titles, query.location, per),
                    headers=headers, timeout=actor_timeout + 40)
                if r.status_code >= 300:
                    # out-of-credits/quota → auto-pause and STOP, but never raise.
                    if is_credit_or_quota_error(r.status_code, r.text):
                        pause(f"HTTP {r.status_code} on {plat}: {r.text[:120]}")
                        errors.append(f"{plat}: out-of-credits/quota (HTTP {r.status_code}) → Apify auto-paused")
                        break
                    errors.append(f"{plat} ({actor}): HTTP {r.status_code} {r.text[:120]}")
                    continue
                items = r.json()
                if isinstance(items, list):
                    for it in items:
                        jp = spec["map"](it)
                        if jp and jp.title:
                            out.append(jp)
                if len(out) >= max_items:        # global record cap reached → stop early
                    break
            except requests.Timeout:
                timeouts += 1
                errors.append(f"{plat} ({actor}): timeout")
            except Exception as e:
                errors.append(f"{plat} ({actor}): {e}")

        elapsed = time.monotonic() - t0

        # ── AFTER: re-read usage, log spend, warn + persist if over budget. ──
        _, _, remaining_after = probe(token)
        if remaining_before is not None and remaining_after is not None:
            spent = max(0.0, remaining_before - remaining_after)
            print(f"  Apify spent ~${spent:.3f} this run ({len(out)} items, {elapsed:.0f}s)", file=sys.stderr)
            if spent > effective_budget:
                note = (f"Apify OVER budget: spent ${spent:.3f} > effective ${effective_budget:.2f} "
                        f"({len(out)} items, {elapsed:.0f}s)")
                print("⚠ " + note, file=sys.stderr)
                state.write("apify_overspend", {"note": note, "at": datetime.now(timezone.utc).isoformat()})
        else:
            print(f"  Apify run done ({len(out)} items, {elapsed:.0f}s); spend not readable from API",
                  file=sys.stderr)

        # Repeated timeouts across platforms → pause so future runs don't hang.
        if timeouts >= 2:
            pause(f"repeated timeouts ({timeouts} platforms)")
            errors.append("repeated timeouts → Apify auto-paused")

        self.last_errors = errors
        return out
