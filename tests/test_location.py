"""Location re-gate tests (CHANGE 1) — the coarse-"India" onsite leak. No network.

Proves: a coarse-location ("India") ONSITE-Bengaluru JD is gated out for a
Hyderabad-locked profile (the Amazon-TPM leak); remote-India passes; a Hyderabad
JD passes; a coarse onsite role with no derivable city is 'location_unverified'
(→ couldn't-verify path); and already-tagged non-coarse locations still gate.

Run:  python -m pytest tests/test_location.py -q   (or: python tests/test_location.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import location as LOC
from jobfinder.schema import JobPosting

PROFILE = {"location": {"onsite_cities": ["Hyderabad"], "remote_ok": True,
                        "hybrid_ok": True, "willing_to_relocate": False}}


def _job(loc, desc, remote=None, source="adzuna"):
    return JobPosting(title="Technical Program Manager, AI", company="C", source=source,
                      url="https://x/jobs/1", location=loc, description=desc, remote=remote)


def test_coarse_india_onsite_bengaluru_is_gated():
    # The Amazon-TPM leak: coarse "India" + a Bengaluru-onsite JD, no remote signal.
    jd = ("Sr. Technical Program Manager, Amazon Now. Bengaluru, Karnataka, IND. Full time. "
          "Own the customer experience end to end and build AI as a worldwide platform.")
    st, reason, city = LOC.regate(_job("India", jd), PROFILE)
    assert st == "onsite_elsewhere" and city == "bengaluru"
    assert "bengaluru" in reason.lower() and "hyderabad" in reason.lower()
    print("✓ coarse 'India' + onsite-Bengaluru JD → gated (onsite_elsewhere)")


def test_coarse_india_remote_passes():
    jd = "Project Manager, RPA & AI Delivery. Job Location: Remote. Bengaluru, South, India (HQ)."
    st, _, _ = LOC.regate(_job("India", jd), PROFILE)
    assert st == "ok"
    print("✓ coarse 'India' + remote JD → ok (not gated on the HQ city)")


def test_coarse_india_hyderabad_passes():
    jd = "AI Delivery Manager. Location: Hyderabad, Telangana, India. Onsite."
    st, _, city = LOC.regate(_job("India", jd), PROFILE)
    assert st == "ok" and city == "hyderabad"
    print("✓ coarse 'India' + Hyderabad JD → ok (matches onsite city)")


def test_coarse_india_multi_city_with_hyderabad_option_passes():
    jd = "TPM, AI. Locations: Bengaluru, Karnataka; Hyderabad, Telangana, India. Onsite."
    st, _, _ = LOC.regate(_job("India", jd), PROFILE)
    assert st == "ok"                        # Hyderabad is offered → acceptable
    print("✓ coarse 'India' + multi-city incl. Hyderabad → ok")


def test_coarse_india_no_city_onsite_is_unverified():
    jd = "AI Program Manager. We deliver enterprise AI. Full-time. Strong delivery track record."
    st, reason, city = LOC.regate(_job("India", jd), PROFILE)
    assert st == "location_unverified" and city is None
    assert "unverified" in reason.lower()
    print("✓ coarse 'India' + onsite + no derivable city → location_unverified")


def test_noncoarse_bengaluru_still_gates_and_hyderabad_ok():
    st_b, _, _ = LOC.regate(_job("Bengaluru, India", "onsite role"), PROFILE)
    st_h, _, _ = LOC.regate(_job("Hyderabad, India", "onsite role"), PROFILE)
    assert st_b == "onsite_elsewhere" and st_h == "ok"
    print("✓ already-tagged Bengaluru gates; Hyderabad passes (existing gate preserved)")


def test_piped_and_spaced_remote_india_resolves_remote():
    # The Abacus.AI case that the benchmark surfaced: "(Remote | India)" in the title
    # must resolve remote-India, NOT location_unverified.
    jd = ("Technical Program Manager (Remote | India) About Abacus.AI. We're looking for an "
          "exceptional Technical Program Manager to drive execution across engineering, product.")
    st, _, _ = LOC.regate(_job("India", jd), PROFILE)
    assert st == "ok"
    # the spaced / piped / parenthesized variants all read as remote
    for s in ("(Remote | India)", "Remote - India", "Remote, India", "India (Remote)", "Remote/India"):
        assert LOC.looks_remote(s), s
    # and a plain onsite city with no such phrasing still does NOT read as remote
    assert not LOC.looks_remote("Bengaluru, Karnataka, India. Full time.")
    print("✓ spaced/piped remote-India phrasings resolve remote (Abacus.AI fix)")


def test_helpers():
    assert LOC.is_coarse("India") and LOC.is_coarse("") and not LOC.is_coarse("Pune, India")
    assert LOC.derive_cities("Work Location: Pune. Also we have a Mumbai office.")[0] == "pune"
    assert LOC.looks_remote("This is a fully-remote position") and not LOC.looks_remote("Onsite in Noida")
    print("✓ is_coarse / derive_cities / looks_remote helpers")


FOREIGN_LEAKS = ["Munich", "Sydney", "Dallas", "Amsterdam", "Seoul, South Korea", "Switzerland",
                 "Remote, United Arab Emirates", "Remote; Remote, United Arab Emirates",
                 "Remote - Colombia", "Remote, North America"]
INDIA_OK = ["Hyderabad", "Bengaluru", "Remote", "Remote - India", "Remote, India", "India",
            "Remote (Global)", "Hyderabad, Telangana, India"]


def test_classify_foreign_vs_india_eligible():
    for loc in FOREIGN_LEAKS:
        assert LOC.classify(loc) == "foreign", loc
    for loc in INDIA_OK:
        assert LOC.classify(loc) in ("india", "remote_india_eligible"), loc
    assert LOC.classify("") == "unknown"
    assert LOC.classify("Amer, Jaipur") == "india"        # India-positive wins on collisions
    print("✓ classify: the 10 leaked foreign strings are foreign; India/remote strings are eligible")


def test_gate_disqualifies_foreign_for_no_relocation_profile():
    from jobfinder.prescreen import _location_gate
    for loc in FOREIGN_LEAKS:                              # remote flag set → the old leak path
        ok, why = _location_gate(_job(loc, "jd", remote="remote"), PROFILE)
        assert ok is False and "foreign" in why, loc
    for loc in ["Hyderabad, Telangana, India", "Remote", "Remote - India", "Remote, India"]:
        assert _location_gate(_job(loc, "jd"), PROFILE)[0] is True, loc
    # profile-driven: a relocation-open candidate still sees them
    relo = {"location": {"onsite_cities": ["Hyderabad"], "remote_ok": True, "willing_to_relocate": True}}
    assert all(_location_gate(_job(loc, "jd"), relo)[0] is True for loc in FOREIGN_LEAKS)
    print("✓ gate disqualifies foreign for a no-relocation profile; relocation-open still sees them")


def test_discovery_filter_drops_foreign_keeps_unknown():
    from jobfinder.filters import location_ok
    # foreign (with the channel's remote flag set — the exact discovery leak) → dropped
    assert location_ok(_job("Munich", "jd", remote="remote"), PROFILE) is False
    assert location_ok(_job("Remote - Colombia", "jd"), PROFILE) is False
    # unknown MUST still enter candidates.jsonl (it has to reach location_unverified)
    assert location_ok(_job("", "jd"), PROFILE) is True
    assert location_ok(_job("Somewhereville", "jd"), PROFILE) is True
    # remote-eligible + india pass
    assert location_ok(_job("Remote", "jd"), PROFILE) is True
    assert location_ok(_job("Hyderabad, India", "jd"), PROFILE) is True
    # relocation-open → no foreign filtering at discovery either
    relo = {"location": {"willing_to_relocate": True}}
    assert location_ok(_job("Munich", "jd"), relo) is True
    print("✓ discovery filter drops foreign (no-relo) but never drops unknown / remote-eligible")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} location tests passed.")
