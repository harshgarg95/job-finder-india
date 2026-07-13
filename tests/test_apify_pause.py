"""Apify auto-pause / auto-resume tests. No real network.

Proves: the out-of-credits/quota trigger is classified correctly, a credit
error during fetch PAUSES (persisted) and never raises, the channel reports its
paused reason, and the state machine resumes cleanly.

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
    # stub the network: every actor run returns HTTP 402 (out of credits)
    def fake_post(*a, **k):
        return _Resp(402, '{"error":{"type":"monthly-usage-hard-limit-exceeded"}}')
    AP.requests.post = fake_post

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
    # stub the resume-probe to report credits still out
    AP.probe = lambda token: (False, "used $5/$5")
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": True}}}) is False
    assert "auto-paused" in p._skip
    assert AP.is_paused() is True          # not resumed
    os.environ.pop("APIFY_TOKEN", None)


def test_paused_channel_auto_resumes_when_probe_says_ok():
    _isolate_state()
    os.environ["APIFY_TOKEN"] = "dummy-not-a-real-token"
    AP.pause("HTTP 402 out of credits")
    AP.probe = lambda token: (True, "used $0/$5")   # credits back
    p = AP.ApifyProvider()
    assert p.enabled({"sources": {"apify": {"enabled": True}}}) is True
    assert AP.is_paused() is False         # auto-resumed (state cleared)
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
