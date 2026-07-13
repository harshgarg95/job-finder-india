"""Free-tier quota-safety + Adzuna/JSearch provider tests. No real network.

Proves the request-budget safety net for the keyed India-native channels:
  • the monthly counter records, exhausts, and RESETS on a new calendar month;
  • the per-run request cap is honoured (never more than max_requests_per_run);
  • a 429 / quota error PAUSES the channel for the month and never raises
    (discovery degrades to the ATS floor + others — it never hard-fails);
  • the field mappers produce the verified JobPosting shape;
  • the registry gap-fill gate spends JSearch ONLY when Adzuna is thin.

Run:  python -m pytest tests/test_quota.py -q   (or: python tests/test_quota.py)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import state
from jobfinder.discovery import quota, adzuna as AD, jsearch as JS, registry as REG
from jobfinder.discovery.base import Query


def _isolate_state():
    state.STATE_DIR = tempfile.mkdtemp(prefix="jf-quota-")


class _Resp:
    def __init__(self, status, text="", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _T(Exception):
    pass


class _FakeRequests:
    """Stands in for the `requests` module inside a provider. Returns queued
    responses (or one repeated) and records every call."""
    Timeout = _T

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)


# ── quota counter ───────────────────────────────────────────────────────────
def test_counter_record_remaining_exhaust():
    _isolate_state()
    assert quota.used_this_month("adzuna") == 0
    assert quota.remaining("adzuna", 250) == 250
    quota.record("adzuna", 1)
    quota.record("adzuna", 2)
    assert quota.used_this_month("adzuna") == 3
    assert quota.remaining("adzuna", 250) == 247
    assert not quota.exhausted("adzuna", 250)
    quota.mark_exhausted("adzuna", 250)
    assert quota.exhausted("adzuna", 250)
    assert quota.remaining("adzuna", 250) == 0
    print("✓ counter records, remaining, exhausts")


def test_counter_resets_on_new_month():
    _isolate_state()
    # A stale-month counter must read as 0 this month (auto-reset).
    state.write("quota_jsearch", {"month": "2000-01", "count": 999})
    assert quota.used_this_month("jsearch") == 0
    assert quota.remaining("jsearch", 200) == 200
    quota.record("jsearch", 1)                      # writes THIS month, replacing the stale one
    assert quota.used_this_month("jsearch") == 1
    print("✓ monthly counter resets on a new calendar month")


def test_is_quota_error():
    assert quota.is_quota_error(429, "")
    assert quota.is_quota_error(403, "monthly quota exceeded")
    assert quota.is_quota_error(402, "rate limit reached")
    assert not quota.is_quota_error(500, "server error")
    assert not quota.is_quota_error(200, "ok")
    assert not quota.is_quota_error(404, "Endpoint '/search' does not exist")
    print("✓ quota-error classifier (429 definitive; body-gated otherwise)")


# ── Adzuna ──────────────────────────────────────────────────────────────────
def _adz_item(title="Agentic AI Manager", predicted="0"):
    return {"title": title, "company": {"display_name": "Marico Limited"},
            "location": {"display_name": "Mumbai, Maharashtra"},
            "redirect_url": "https://www.adzuna.in/land/ad/123",
            "description": "About the role ...", "created": "2026-06-18T15:55:06Z",
            "id": "123", "salary_max": 3000000, "salary_is_predicted": predicted,
            "contract_time": "full_time"}


def test_adzuna_map_verified_shape():
    j = AD._map(_adz_item())
    assert j.title == "Agentic AI Manager"
    assert j.company == "Marico Limited"
    assert j.source == "adzuna" and j.link_source == "adzuna"
    assert j.url == "https://www.adzuna.in/land/ad/123"
    assert j.location == "Mumbai, Maharashtra"
    assert j.posted_at == "2026-06-18"
    assert j.salary_max == 3000000 and j.salary_currency == "INR"
    assert j.employment_type == "full_time"
    # Predicted salary is Adzuna's estimate, not the employer's → not presented.
    jp = AD._map(_adz_item(predicted="1"))
    assert jp.salary_max is None and jp.salary_currency is None
    print("✓ Adzuna field map matches the verified live shape")


def test_adzuna_per_run_cap_and_records():
    _isolate_state()
    os.environ["ADZUNA_APP_ID"] = "x"
    os.environ["ADZUNA_APP_KEY"] = "y"
    AD.requests = _FakeRequests([_Resp(200, payload={"results": [_adz_item(), _adz_item("Data Lead")]})])
    cfg = {"sources": {"adzuna": {"enabled": True}},
           "run": {"discovery": {"adzuna": {"max_requests_per_run": 2, "monthly_cap": 250}}}}
    q = Query(titles=["a", "b", "c", "d", "e"], location="India", limit_per_channel=50)
    jobs = AD.AdzunaProvider().fetch(q, cfg)
    assert len(AD.requests.calls) == 2                 # per-run cap of 2, not 5 titles
    assert quota.used_this_month("adzuna") == 2        # each request counted
    assert all(j.source == "adzuna" for j in jobs)
    print("✓ Adzuna honours per-run cap + records each request")


def test_adzuna_429_pauses_and_never_raises():
    _isolate_state()
    os.environ["ADZUNA_APP_ID"] = "x"
    os.environ["ADZUNA_APP_KEY"] = "y"
    AD.requests = _FakeRequests([_Resp(429, text="rate limit exceeded")])
    cfg = {"sources": {"adzuna": {"enabled": True}},
           "run": {"discovery": {"adzuna": {"max_requests_per_run": 3, "monthly_cap": 250}}}}
    jobs = AD.AdzunaProvider().fetch(Query(titles=["a", "b"], location="India"), cfg)
    assert jobs == []                                  # degraded, not crashed
    assert quota.exhausted("adzuna", 250)              # paused for the month
    print("✓ Adzuna 429 → paused for the month, never raises")


# ── JSearch (guarded; success shape pending live verification) ───────────────
def test_jsearch_map_documented_shape():
    j = JS._map({"job_title": "AI Manager", "employer_name": "Acme",
                 "job_apply_link": "https://acme.com/jobs/1", "job_city": "Bengaluru",
                 "job_state": "KA", "job_country": "IN", "job_description": "...",
                 "job_is_remote": True, "job_posted_at_datetime_utc": "2026-07-01T00:00:00Z",
                 "job_employment_type": "FULLTIME"})
    assert j.title == "AI Manager" and j.company == "Acme" and j.source == "jsearch"
    assert j.location == "Bengaluru, KA, IN" and j.remote == "remote"
    assert j.posted_at == "2026-07-01"
    print("✓ JSearch documented field map")


def test_jsearch_404_guard_skips_no_raise():
    _isolate_state()
    os.environ["JSEARCH_API_KEY"] = "k"
    JS.requests = _FakeRequests([_Resp(404, text="Endpoint '/search' does not exist")])
    cfg = {"sources": {"jsearch": {"enabled": True, "host": "rapidapi"}},
           "run": {"discovery": {"jsearch": {"max_requests_per_run": 3, "monthly_cap": 200}}}}
    p = JS.JSearchProvider()
    jobs = p.fetch(Query(titles=["a"], location="India"), cfg)
    assert jobs == []                                  # guard: no unverified data enters
    assert p.last_errors and "unverified" in p.last_errors[0]
    print("✓ JSearch non-200 guard → skips cleanly, no unverified data, no raise")


# ── registry gap-fill: JSearch spent only when Adzuna is thin ────────────────
def _reg_cfg():
    return {"ats_tenants": [],
            "sources": {"ats": {"enabled": False}, "google_jobs": {"enabled": False},
                        "apify": {"enabled": False},
                        "adzuna": {"enabled": True}, "jsearch": {"enabled": True, "host": "rapidapi"}},
            "run": {"discovery": {"adzuna": {"max_requests_per_run": 1, "monthly_cap": 250},
                                  "jsearch": {"max_requests_per_run": 1, "monthly_cap": 200,
                                              "trigger_below": 40}}}}


def test_gapfill_skips_jsearch_when_adzuna_sufficient():
    _isolate_state()
    os.environ.update({"ADZUNA_APP_ID": "x", "ADZUNA_APP_KEY": "y", "JSEARCH_API_KEY": "k"})
    AD.requests = _FakeRequests([_Resp(200, payload={"results": [_adz_item(f"r{i}") for i in range(50)]})])
    js_fake = _FakeRequests([_Resp(200, payload={"data": []})])
    JS.requests = js_fake
    _, reports = REG.discover(Query(titles=["a"], location="India"), _reg_cfg())
    rmap = {r.id: r for r in reports}
    assert rmap["adzuna"].count == 50
    assert not rmap["jsearch"].enabled                 # skipped by the gap-fill gate
    assert "sufficient" in rmap["jsearch"].skipped_reason
    assert js_fake.calls == []                          # JSearch never called → quota saved
    print("✓ gap-fill: Adzuna ≥ trigger → JSearch skipped, quota saved")


def test_gapfill_runs_jsearch_when_adzuna_thin():
    _isolate_state()
    os.environ.update({"ADZUNA_APP_ID": "x", "ADZUNA_APP_KEY": "y", "JSEARCH_API_KEY": "k"})
    AD.requests = _FakeRequests([_Resp(200, payload={"results": [_adz_item()]})])   # 1 < 40
    js_fake = _FakeRequests([_Resp(404, text="Endpoint '/search' does not exist")])  # guarded
    JS.requests = js_fake
    _, reports = REG.discover(Query(titles=["a"], location="India"), _reg_cfg())
    rmap = {r.id: r for r in reports}
    assert rmap["adzuna"].count == 1
    assert rmap["jsearch"].enabled                      # gate opened (Adzuna thin)
    assert len(js_fake.calls) == 1                       # JSearch attempted the fill
    print("✓ gap-fill: Adzuna < trigger → JSearch runs (fills the gap)")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} quota/provider tests passed.")
