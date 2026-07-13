"""Apify auto-pause / auto-resume + spend-safety tests. No real network.

Proves: the out-of-credits/quota trigger is classified correctly; a credit error
during fetch PAUSES (persisted) and never raises; the channel reports its state;
the resolver resumes cleanly; and — critically — a single run can NEVER drain the
balance (low balance → skip; otherwise the scrape is capped by Apify-native limits).

Run:  python -m pytest tests/test_apify_pause.py -q  (or: python tests/test_apify_pause.py)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import state
from jobfinder.discovery import apify as AP
from jobfinder.discovery.base import Query


def _isolate_state():
    """Point the state store at a throwaway dir so tests never touch real data/."""
    state.STATE_DIR = tempfile.mkdtemp(prefix="jf-state-")


class _Resp:
    def __init__(self, status, text="", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload if payload is not None else []
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


class _Capture:
    """Records requests.post calls and returns a canned item list (no network)."""
    def __init__(self, payload=None):
        self.calls = []
        self._payload = payload if payload is not None else [
            {"title": "AI Program Manager", "companyName": "Acme"}]

    def post(self, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "json": json})
        return _Resp(200, payload=self._payload)


def test_error_classifier():
    assert AP.is_credit_or_quota_error(402, "") is True               # Payment Required = definitive
    assert AP.is_credit_or_quota_error(403, "monthly usage hard limit exceeded") is True
    assert AP.is_credit_or_quota_error(429, "quota exceeded") is True
    assert AP.is_credit_or_quota_error(500, "internal server error") is False  # transient, not credits
    assert AP.is_credit_or_quota_error(403, "forbidden: bad actor input") is False


def test_pause_resume_state_machine():
    _isolate_state()
    assert AP.is_paused() is False
    AP.pause("HTTP 402 out of credits")
    assert AP.is_paused() is True
    assert "402" in state.read("apify").get("reason", "")
    AP.resume()
    assert AP.is_paused() is False


def test_disabled_in_sources_is_skipped():
    _isolate_state()
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": False}}}) is False
    assert "sources.yml" in p._skip


def test_enabled_but_no_token():
    _isolate_state()
    os.environ.pop("APIFY_TOKEN", None)
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": True}}}) is False
    assert "APIFY_TOKEN" in p._skip


def test_fetch_on_402_pauses_and_does_not_raise():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy-not-a-real-token"
    AP.probe = lambda t: (None, "stub", None)          # no network in tests
    AP.requests.post = lambda *a, **k: _Resp(402, '{"error":{"type":"monthly-usage-hard-limit-exceeded"}}')

    p = AP.ApifyProvider()
    out = p.fetch(Query(titles=["AI PM"], location="India", limit_per_channel=10),
                  {"sources": {"apify": {"enabled": True, "platforms": ["naukri", "linkedin"]}}})
    assert out == []                       # no jobs, but...
    assert AP.is_paused() is True          # ...auto-paused for next run
    assert any("auto-paused" in e for e in p.last_errors)
    os.environ.pop("APIFY_TOKEN", None)


def test_paused_channel_stays_off_when_probe_says_unavailable():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy-not-a-real-token"
    AP.pause("HTTP 402 out of credits")
    AP.probe = lambda t: (False, "used $5/$5", 0.0)    # credits still out
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": True}}}) is False
    assert AP.is_paused() is True          # not resumed
    os.environ.pop("APIFY_TOKEN", None)


def test_paused_channel_auto_resumes_when_probe_says_ok():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy-not-a-real-token"
    AP.pause("HTTP 402 out of credits")
    AP.probe = lambda t: (True, "used $0/$5", 5.0)     # credits back
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": True}}}) is True
    assert AP.is_paused() is False         # auto-resumed (state cleared)
    os.environ.pop("APIFY_TOKEN", None)


def test_resolve_disabled():
    _isolate_state()
    assert AP.resolve({"sources": {"apify": {"enabled": False}}})["state"] == "disabled"


def test_resolve_no_token():
    _isolate_state()
    os.environ.pop("APIFY_TOKEN", None)
    assert AP.resolve({"sources": {"apify": {"enabled": True}}})["state"] == "no-token"


def test_resolve_active_clears_any_pause():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    AP.pause("stale pause")
    AP.probe = lambda t: (True, "$5.00 of $5 remaining", 5.0)
    r = AP.resolve({"sources": {"apify": {"enabled": True}}})
    assert r["state"] == "active" and AP.is_paused() is False and r["remaining_usd"] == 5.0
    os.environ.pop("APIFY_TOKEN", None)


def test_resolve_paused_no_credits_persists():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    AP.probe = lambda t: (False, "$0.02 of $5 remaining, cycle resets 2026-07-05", 0.02)
    r = AP.resolve({"sources": {"apify": {"enabled": True}}})
    assert r["state"] == "paused-no-credits" and AP.is_paused() is True
    os.environ.pop("APIFY_TOKEN", None)


def test_resolve_error_is_transient_not_paused():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    AP.probe = lambda t: (None, "probe error: timeout", None)
    r = AP.resolve({"sources": {"apify": {"enabled": True}}})
    assert r["state"] == "error" and AP.is_paused() is False   # transient → re-probe next run
    os.environ.pop("APIFY_TOKEN", None)


def test_resolve_auto_resumes_when_credits_return():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    AP.probe = lambda t: (False, "no credits", 0.0)
    assert AP.resolve({"sources": {"apify": {"enabled": True}}})["state"] == "paused-no-credits"
    assert AP.is_paused() is True
    AP.probe = lambda t: (True, "$5 remaining", 5.0)           # next run: credits back
    assert AP.resolve({"sources": {"apify": {"enabled": True}}})["state"] == "active"
    assert AP.is_paused() is False                              # auto-resumed
    os.environ.pop("APIFY_TOKEN", None)


# ── Spend-safety: a single run can NEVER drain the balance ───────────────────

def test_low_balance_skips_scrape_never_drains():
    """Low remaining → effective budget <= 0 → skip BEFORE any scrape call."""
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    cap = _Capture()
    AP.requests.post = cap.post
    AP.probe = lambda t: (False, "$0.10 of $5 remaining", 0.10)   # after-read (won't be reached)
    p = AP.ApifyProvider()
    cfg = {
        "sources": {"apify": {"enabled": True, "platforms": ["naukri"]}},
        "run": {"apify": {"max_spend_usd_per_run": 0.50, "max_items": 200, "actor_timeout_s": 300}},
        "apify_resolved": {"state": "active", "remaining_usd": 0.10},  # 0.10 − 0.10 headroom = 0
    }
    out = p.fetch(Query(titles=["AI PM"], location="India", limit_per_channel=10), cfg)
    assert out == []                       # skipped
    assert cap.calls == []                 # NO scrape request made → cannot drain
    assert p.last_errors and "never drains" in p.last_errors[0]
    os.environ.pop("APIFY_TOKEN", None)


def test_scrape_is_capped_by_apify_native_limits():
    """With budget, the scrape runs but is bounded by Apify-native maxItems +
    timeout (and the actor's own input cap), not just by us."""
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy"
    cap = _Capture()
    AP.requests.post = cap.post
    AP.probe = lambda t: (True, "$4.99 of $5 remaining", 4.99)   # after-read → ~no spend
    p = AP.ApifyProvider()
    cfg = {
        "sources": {"apify": {"enabled": True, "platforms": ["naukri"], "limit": 40}},
        "run": {"apify": {"max_spend_usd_per_run": 0.50, "max_items": 5, "actor_timeout_s": 120}},
        "apify_resolved": {"state": "active", "remaining_usd": 5.0},
    }
    p.fetch(Query(titles=["AI PM"], location="India", limit_per_channel=40), cfg)
    assert cap.calls, "scrape should have run with budget available"
    params = cap.calls[0]["params"]
    assert params["maxItems"] == 5         # Apify-native hard record cap
    assert params["timeout"] == 120        # Apify-native run timeout (kills long scrapes)
    assert params["limit"] <= 5            # items returned, capped
    assert cap.calls[0]["json"].get("maximumJobs") <= 5   # naukri actor INPUT cap (live schema)
    os.environ.pop("APIFY_TOKEN", None)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
