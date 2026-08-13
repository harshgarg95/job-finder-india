"""Canary policy: transient upstream weather WARNs (run passes); real breakage FAILs.

Covers the four historical false-alarms (all transient third-party hiccups while ats
was healthy) and the guardrails that must still hard-fail. Pure-function tests on
classify_keyed() (one channel's status) and decide() (cross-channel verdict) — no
network, no providers.
"""
import importlib.util
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load the script by path (scripts/ isn't a package).
_spec = importlib.util.spec_from_file_location(
    "discovery_smoke", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "discovery_smoke.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


class J:
    """Minimal JobPosting stand-in for well_formed() + the location check."""
    def __init__(self, title="SWE", company="Acme", url="https://x/1", location="Bengaluru, IN"):
        self.title, self.company, self.url, self.location = title, company, url, location


# ── classify_keyed: the FAIL vs WARN line ────────────────────────────────────
def test_adzuna_503_is_warn():                       # 13 Aug incident
    s, d = smoke.classify_keyed("adzuna", [], ["'software engineer': HTTP 503 <!DOCTYPE html>"])
    assert s == "WARN" and "5xx" in d
    print("✓ HTTP 503 → WARN (transient upstream)")


def test_jsearch_empty_results_is_warn():            # 08 Aug incident (0 jobs, 200 OK)
    s, d = smoke.classify_keyed("jsearch", [], [])
    assert s == "WARN" and "0 well-formed" in d
    print("✓ 200 OK + 0 jobs → WARN (empty/degraded data)")


def test_jsearch_all_empty_location_is_warn():       # 27 Jul + 13 Aug re-run incident
    s, d = smoke.classify_keyed("jsearch", [J(location=""), J(location="  ")], [])
    assert s == "WARN" and "locations empty" in d
    print("✓ postings present but all-empty location → WARN (degraded data)")


def test_timeout_and_connection_errors_are_warn():   # transport weather, same class as 5xx
    # exactly how the providers spell these (jsearch.py / adzuna.py)
    assert smoke.classify_keyed("jsearch", [], ["'software engineer': timeout"])[0] == "WARN"
    conn = ("'software engineer': HTTPSConnectionPool(host='api', port=443): "
            "Max retries exceeded (Caused by NewConnectionError('Failed to establish a new connection'))")
    assert smoke.classify_keyed("adzuna", [], [conn])[0] == "WARN"
    print("✓ timeout / connection error → WARN (transient network weather)")


def test_4xx_body_containing_timeout_still_fails():   # status decides, not body text
    # a 401/4xx whose error-page body happens to contain 'timeout' must NOT be softened
    s, _ = smoke.classify_keyed("jsearch", [], ["HTTP 401 <html>session timeout, please log in</html>"])
    assert s == "FAIL"
    print("✓ 4xx wins over a 'timeout' substring in its body — status-first classification")


def test_4xx_is_hard_fail():                         # auth / 404 / bad request → drift/secrets
    for err in (["HTTP 404 not found"], ["HTTP 401 unauthorized"], ["HTTP 400 bad request"]):
        assert smoke.classify_keyed("jsearch", [], err)[0] == "FAIL", err
    print("✓ 4xx → FAIL (secrets / endpoint drift, incl. the v1→v5 rename which 404s)")


def test_parse_error_is_hard_fail():                 # 200 with unparseable/HTML body → shape drift
    s, _ = smoke.classify_keyed("adzuna", [], ["'x': Expecting value: line 1 column 1 (char 0)"])
    assert s == "FAIL"
    print("✓ JSON parse error → FAIL (changed/unparseable shape)")


def test_quota_unchanged():
    s, _ = smoke.classify_keyed("jsearch", [], ["quota/rate limit (HTTP 429) → paused for the month"])
    assert s == "QUOTA"
    print("✓ quota/rate-limit → QUOTA (unchanged, passes)")


def test_healthy_is_ok():
    s, d = smoke.classify_keyed("adzuna", [J(), J()], [])
    assert s == "OK" and "2 well-formed postings (2 with location)" in d
    print("✓ well-formed postings with location → OK")


# ── decide: cross-channel guardrails ─────────────────────────────────────────
def test_single_keyed_warn_passes_when_ats_ok():
    for degraded in ("adzuna", "jsearch"):
        st = {"ats": "OK", "adzuna": "OK", "jsearch": "OK", degraded: "WARN"}
        fail, _ = smoke.decide(st)
        assert fail is False, degraded
    print("✓ a single keyed WARN with ats healthy → run PASSES (the four historical cases)")


def test_single_channel_timeout_with_ats_healthy_passes():   # end-to-end: classify → decide
    # a jsearch timeout while ats + adzuna are healthy → WARN, run PASSES
    status, _ = smoke.classify_keyed("jsearch", [], ["'software engineer': timeout"])
    fail, _ = smoke.decide({"ats": "OK", "adzuna": "OK", "jsearch": status})
    assert status == "WARN" and fail is False
    print("✓ single-channel timeout + ats healthy → WARN, run PASSES")


def test_ats_fail_is_hard_fail():
    fail, reasons = smoke.decide({"ats": "FAIL", "adzuna": "OK", "jsearch": "OK"})
    assert fail is True and any("floor" in r for r in reasons)
    print("✓ ats down → hard FAIL (the keyless floor pages loudly)")


def test_both_keyed_degraded_is_outage_fail():
    for combo in (("WARN", "WARN"), ("WARN", "FAIL"), ("FAIL", "FAIL")):
        fail, reasons = smoke.decide({"ats": "OK", "adzuna": combo[0], "jsearch": combo[1]})
        assert fail is True, combo
    fail, reasons = smoke.decide({"ats": "OK", "adzuna": "WARN", "jsearch": "WARN"})
    assert any("all keyed" in r for r in reasons)
    print("✓ ALL keyed channels degraded at once → hard FAIL (outage, not a blip)")


def test_single_keyed_4xx_fails_even_alone():
    fail, _ = smoke.decide({"ats": "OK", "adzuna": "FAIL", "jsearch": "OK"})
    assert fail is True
    print("✓ a single keyed hard-FAIL (4xx/parse) → run FAILS even with the other keyed OK")


def test_warn_passes_when_other_keyed_skipped():
    fail, _ = smoke.decide({"ats": "OK", "adzuna": "WARN", "jsearch": "SKIP"})
    assert fail is False                              # only one keyed attempted → not 'all degraded'
    print("✓ one keyed WARN + the other SKIP (no key) + ats OK → PASSES")


# ── persistence escalation ───────────────────────────────────────────────────
def _apply(counters, jsearch="OK", adzuna="OK", ats="OK"):
    return smoke.update_counters(counters, {"ats": ats, "adzuna": adzuna, "jsearch": jsearch})


def test_persistence_three_consecutive_warns_escalates():
    c = {}
    for _ in range(3):
        c = _apply(c, jsearch="WARN")
    assert c["jsearch"] == 3
    esc = smoke.escalations(c)
    assert any("jsearch" in r and "consecutive" in r for r in esc)
    print("✓ 3 consecutive WARNs on a channel → escalates to FAIL")


def test_persistence_two_warns_do_not_escalate():
    c = _apply(_apply({}, jsearch="WARN"), jsearch="WARN")
    assert c["jsearch"] == 2 and smoke.escalations(c) == []
    print("✓ a 2-run WARN streak stays WARN (weather) — no escalation")


def test_persistence_recovery_resets_streak():
    c = _apply(_apply({}, jsearch="WARN"), jsearch="WARN")   # streak 2
    c = _apply(c, jsearch="OK")                              # recovered
    assert c["jsearch"] == 0 and smoke.escalations(c) == []
    print("✓ WARN×2 then OK → counter resets, no escalation")


def test_persistence_flapping_flavors_still_escalate():
    # 5xx → empty-results → timeout are DIFFERENT WARN flavors, SAME channel.
    # classify_keyed maps them all to WARN; the per-channel counter keeps rising.
    a = smoke.classify_keyed("jsearch", [], ["HTTP 503"])[0]
    b = smoke.classify_keyed("jsearch", [], [])[0]
    d = smoke.classify_keyed("jsearch", [], ["'q': timeout"])[0]
    assert a == b == d == "WARN"
    c = {}
    for st in (a, b, d):
        c = smoke.update_counters(c, {"ats": "OK", "adzuna": "OK", "jsearch": st})
    assert c["jsearch"] == 3 and smoke.escalations(c)
    print("✓ flapping between WARN flavors on one channel still escalates (per-channel, not per-condition)")


def test_persistence_cold_cache_no_crash():
    counters, note = smoke.load_counters("/nonexistent/dir/counters.json")
    assert note == "cold" and counters == {"adzuna": 0, "jsearch": 0}
    assert smoke.escalations(counters) == []
    counters, note = smoke.load_counters(None)               # persistence disabled path
    assert note == "cold" and counters == {"adzuna": 0, "jsearch": 0}
    print("✓ cold cache / no state file → counters 0, no crash")


def test_persistence_corrupt_state_treated_as_zero():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "counters.json")
    open(p, "w").write("{ this is not json")
    counters, note = smoke.load_counters(p)
    assert note.startswith("corrupt") and counters == {"adzuna": 0, "jsearch": 0}
    open(p, "w").write('{"jsearch": "notanint", "adzuna": 5}')  # one corrupt value
    counters, note = smoke.load_counters(p)
    assert counters == {"adzuna": 5, "jsearch": 0} and note == "ok"
    print("✓ corrupt state file / value → treated as 0, never hard-fails the canary")


def test_persistence_save_load_roundtrip_creates_dir():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "nested", "counters.json")
    smoke.save_counters(p, {"adzuna": 1, "jsearch": 2})       # nested dir must be created
    counters, note = smoke.load_counters(p)
    assert note == "ok" and counters == {"adzuna": 1, "jsearch": 2}
    print("✓ save creates the dir + round-trips through load")


def test_persistence_never_softens_ats_fail():
    # ats FAIL is immediate; persistence only ADDS FAILs, never removes one.
    fail, _ = smoke.decide({"ats": "FAIL", "adzuna": "WARN", "jsearch": "OK"})
    assert fail is True
    print("✓ ats-fail still hard-FAILs immediately regardless of counters")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} discovery-smoke policy tests passed.")
