"""Location re-gate — close the coarse-location onsite leak.

Some channels (Adzuna) report only a coarse location ("India"), so prescreen's
onsite-city hard gate never sees a city and an onsite-Bengaluru role can slip
through to scoring for a Hyderabad-locked candidate. After enrich (when the full
JD is available), this module derives the real city from the JD and re-runs the
SAME onsite gate — before any score. Deterministic; no LLM.

regate(job, profile) -> (status, reason, city):
  • "ok"                 — remote-India, or an onsite city the candidate allows.
  • "onsite_elsewhere"   — onsite in a city NOT in onsite_cities → gate out.
  • "location_unverified"— onsite but no city derivable from the JD → do NOT pass
                            it through as "India"; treat like the couldn't-verify path.
"""

from __future__ import annotations

import re
from dataclasses import replace

from . import prescreen as _ps
from .schema import JobPosting

# "Location: Bengaluru", "Work Location - Hyderabad", "Based in Pune", etc.
_CITY_LINE_RE = re.compile(
    r"\b(?:job\s+location|work\s+location|location|based\s+(?:in|at|out\s+of)|office|city|"
    r"posting\s+location|primary\s+location|work\s+site)\b[\s:\-–]{0,4}([A-Za-z .,/&()-]{3,60})",
    re.I,
)

# A STRONG remote signal (a bare "remote" mention isn't enough — it appears in
# passing too often). Matches an explicit remote work-mode or a "location: remote".
_REMOTE_RE = re.compile(
    r"\b(?:fully[- ]remote|remote[- ]first|100%\s*remote|work\s+from\s+(?:home|anywhere)|"
    r"remote\s+(?:position|role|opportunity|work)|wfh)\b"
    r"|\b(?:job|work)\s+location\b[\s:\-–]{0,4}remote\b"
    r"|\b(?:employment\s+type|work\s+type|work\s+mode|type)\b[\s:\-–]{0,4}remote\b"
    # Location-slug phrasings where remote sits next to India (either order, tight):
    # "(Remote | India)", "Remote - India", "Remote, India", "India (Remote)", "Remote/India".
    r"|\bremote\b[\s|,/\-–()]{0,6}india\b"
    r"|\bindia\b[\s|,/\-–()]{0,6}\(?\s*remote\b"
    r"|\(\s*remote\s*[|)]",                    # a parenthesized "(Remote |" / "(Remote)" work-mode tag
    re.I,
)


# ── Location classification — ONE source of truth (discovery filter + prescreen gate) ──
# The leak this closes: a foreign role whose channel sets `remote` (Harvey/Munich,
# "Remote - Colombia", "Remote, North America") slipped past both the discovery filter
# and the gate, because neither had the city/country and both short-circuited on "remote".
_INDIA_WORDS = [
    "india", "bharat", "hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai",
    "pune", "delhi", "new delhi", "gurgaon", "gurugram", "noida", "chennai", "kolkata",
    "ahmedabad", "jaipur", "indore", "kochi", "cochin", "coimbatore", "chandigarh",
    "trivandrum", "thiruvananthapuram", "nagpur", "vadodara", "bhubaneswar", "mysuru",
    "mysore", "visakhapatnam", "surat", "lucknow", "kanpur", "goa", "ncr",
    "telangana", "karnataka", "maharashtra", "tamil nadu", "kerala", "gujarat",
    "west bengal", "haryana", "punjab", "rajasthan", "odisha", "andhra pradesh",
    "uttar pradesh", "madhya pradesh",
]
# NOTE: APAC / "asia pacific" are deliberately NOT here — they INCLUDE India.
_FOREIGN_WORDS = [
    # countries
    "united states", "usa", "us", "united kingdom", "uk", "england", "scotland", "ireland",
    "canada", "mexico", "brazil", "colombia", "argentina", "chile", "peru", "france",
    "germany", "spain", "portugal", "italy", "netherlands", "belgium", "switzerland",
    "austria", "sweden", "norway", "denmark", "finland", "poland", "czech", "romania",
    "hungary", "greece", "turkey", "russia", "ukraine", "israel", "saudi arabia",
    "united arab emirates", "uae", "qatar", "kuwait", "bahrain", "oman", "egypt",
    "south africa", "nigeria", "kenya", "morocco", "australia", "new zealand", "japan",
    "south korea", "korea", "china", "hong kong", "taiwan", "singapore", "malaysia",
    "indonesia", "thailand", "vietnam", "philippines", "pakistan", "bangladesh",
    "sri lanka", "nepal",
    # major cities
    "london", "manchester", "dublin", "paris", "berlin", "munich", "hamburg", "frankfurt",
    "madrid", "barcelona", "lisbon", "milan", "rome", "vienna", "zurich", "geneva",
    "amsterdam", "rotterdam", "brussels", "stockholm", "oslo", "copenhagen", "helsinki",
    "warsaw", "prague", "budapest", "istanbul", "tel aviv", "dubai", "abu dhabi",
    "riyadh", "doha", "cairo", "johannesburg", "cape town", "lagos", "nairobi",
    "new york", "san francisco", "seattle", "boston", "chicago", "austin", "dallas",
    "houston", "denver", "atlanta", "miami", "los angeles", "san jose", "san diego",
    "phoenix", "philadelphia", "washington dc", "toronto", "vancouver", "montreal",
    "sydney", "melbourne", "brisbane", "perth", "auckland", "wellington", "tokyo",
    "osaka", "seoul", "beijing", "shanghai", "shenzhen", "taipei", "kuala lumpur",
    "jakarta", "bangkok", "manila", "hanoi", "karachi", "lahore", "dhaka", "colombo",
    # regions that EXCLUDE India
    "emea", "amer", "americas", "north america", "south america", "latam",
    "latin america", "middle east", "mea", "anz", "benelux", "nordics", "dach",
    "europe", "africa",
]
_REMOTE_WORDS = ("remote", "anywhere", "work from home", "wfh", "distributed")


def _words_rx(tokens: list[str]) -> re.Pattern:
    longest_first = sorted(tokens, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in longest_first) + r")\b", re.I)


_INDIA_WORD_RX = _words_rx(_INDIA_WORDS)
_FOREIGN_WORD_RX = _words_rx(_FOREIGN_WORDS)


def classify(loc: str) -> str:
    """Classify a job location string:

      "india"                 — an Indian city/state, or "India"
      "remote_india_eligible" — remote with NO foreign qualifier (bare "Remote",
                                "Remote (Global)"), or remote tied to India
      "foreign"               — names a non-India country/city/region, INCLUDING a
                                remote with a foreign qualifier ("Remote - Colombia",
                                "Remote, North America", "Remote, UAE", EMEA/ANZ/MEA)
      "unknown"               — blank or unrecognisable (must NOT be treated as a fit;
                                it flows to the location_unverified path)

    India-positive wins on collisions (e.g. "Amer, Jaipur" is India, not AMER)."""
    norm = re.sub(r"\.", "", (loc or "").strip().lower())
    if not norm:
        return "unknown"
    india = bool(_INDIA_WORD_RX.search(norm))
    foreign = bool(_FOREIGN_WORD_RX.search(norm))
    remote = any(w in norm for w in _REMOTE_WORDS)
    if foreign and not india:
        return "foreign"
    if india:
        return "remote_india_eligible" if remote else "india"
    if remote:
        return "remote_india_eligible"
    return "unknown"


def is_coarse(loc: str) -> bool:
    """True when the location string has no resolvable city (India or foreign) —
    the onsite gate is then blind and could leak an onsite-elsewhere role."""
    l = (loc or "").strip().lower()
    if not l:
        return True
    if any(c in l for c in _ps._INDIA_CITIES):
        return False
    if _FOREIGN_WORD_RX.search(re.sub(r"\.", "", l)):
        return False   # a foreign city is resolvable; the gate's foreign check handles it
    return True


def looks_remote(jd_text: str, job: JobPosting | None = None) -> bool:
    if job is not None and "remote" in str(job.remote or "").lower():
        return True
    return bool(_REMOTE_RE.search(jd_text or ""))


def derive_cities(jd_text: str) -> list[str]:
    """India cities named in the JD, most-prominent first: cities on a 'Location:'
    line rank ahead of the earliest city mentioned in the body."""
    if not jd_text:
        return []
    ordered: list[str] = []
    for m in _CITY_LINE_RE.finditer(jd_text):
        seg = m.group(1).lower()
        for _, c in sorted((seg.find(c), c) for c in _ps._INDIA_CITIES if c in seg):
            if c not in ordered:
                ordered.append(c)
    tl = jd_text.lower()
    for _, c in sorted((tl.find(c), c) for c in _ps._INDIA_CITIES if c in tl):
        if c not in ordered:
            ordered.append(c)
    return ordered


def regate(job: JobPosting, profile: dict) -> tuple[str, str, str | None]:
    """After enrich: if the channel location is coarse, derive the city from the JD
    and re-run the onsite gate. Returns (status, reason, derived_city)."""
    # Not coarse → prescreen's gate already saw the city; just report its verdict.
    if not is_coarse(job.location):
        ok, why = _ps._location_gate(job, profile)
        return ("ok", "", None) if ok else ("onsite_elsewhere", why, None)

    locp = profile.get("location", {}) or {}
    if locp.get("willing_to_relocate"):
        return "ok", "", None
    remote_ok = bool(locp.get("remote_ok") or locp.get("hybrid_ok"))
    onsite = [c.lower() for c in (locp.get("onsite_cities") or [])]

    jd = job.description or ""
    cities = derive_cities(jd)

    # Explicit remote/hybrid role + candidate is remote-OK → India-remote is fine.
    loc_is_remote = any(t in (job.location or "").lower() for t in _ps._REMOTE_TOKENS)
    if (loc_is_remote or looks_remote(jd, job)) and remote_ok:
        return "ok", "", (cities[0] if cities else None)

    if cities:
        if not onsite or any(c in onsite for c in cities):
            return "ok", "", next((c for c in cities if c in onsite), cities[0])
        # Onsite in a city the candidate won't take → gate (reuse the gate's wording).
        probe = replace(job, location=f"{cities[0].title()}, India")
        _, why = _ps._location_gate(probe, profile)
        return "onsite_elsewhere", (why or f"onsite in {cities[0].title()} "
                                    f"(you're onsite-{onsite[0].title() if onsite else '?'} only)"), cities[0]

    # No city derivable and not clearly remote → don't pass it through as "India".
    return ("location_unverified",
            "onsite role but no city could be derived from the JD — location unverified", None)
