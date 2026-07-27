"""ATS-aware deep-fetch tests — offline (requests stubbed, no network).

Covers the Workday-CXS / SmartRecruiters JD branches: URL derivation, payload
parsing, the ≥600-char floor, and the polite-client contract — one attempt,
honest UA, and a 403/429 is a "no" (honest no_jd, never around the block,
never falling through to hammer the page).

Run:  python -m pytest tests/test_job_fetcher.py -q  (or: python tests/test_job_fetcher.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder.discovery import job_fetcher as JF

JF._API_MIN_INTERVAL = 0        # no pacing sleeps in tests


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _FakeRequests:
    """Records every GET; serves responses per URL-substring match."""
    def __init__(self, routes):
        self.routes = routes            # [(substring, _Resp)]
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        for frag, resp in self.routes:
            if frag in url:
                return resp
        return _Resp(404)

    class RequestException(Exception):
        pass


_WD_URL = ("https://genpact.wd108.myworkdayjobs.com/External_Careers/job/"
           "Bangalore/Tech-Lead_JR10007960-1")
_WD_CXS = "/wday/cxs/genpact/External_Careers/job/Bangalore/Tech-Lead_JR10007960-1"


def test_workday_cxs_derivation_parse_and_floor():
    saved = JF.requests
    long_jd = "<p>Responsibilities and requirements. " * 40 + "</p>"     # ≥600 after strip
    JF.requests = _FakeRequests([("/wday/cxs/", _Resp(200, {"jobPostingInfo": {"jobDescription": long_jd}}))])
    try:
        text = JF._fetch_workday_jd(_WD_URL)
        assert text and len(text) >= 600 and "Responsibilities" in text and "<p>" not in text
        url, kw = JF.requests.calls[0]
        assert _WD_CXS in url                                            # exact CXS derivation
        assert kw["headers"]["User-Agent"].startswith("job-finder-india/")   # honest UA, not a browser
        # thin payload → None (the ≥600 floor holds — no thin text passes)
        JF.requests = _FakeRequests([("/wday/cxs/", _Resp(200, {"jobPostingInfo": {"jobDescription": "<p>tiny</p>"}}))])
        assert JF._fetch_workday_jd(_WD_URL) is None
    finally:
        JF.requests = saved
    print("✓ workday: URL→CXS derivation, HTML stripped, honest UA, ≥600 floor enforced")


def test_smartrecruiters_posting_api_parse():
    saved = JF.requests
    sect = {"jobAd": {"sections": {
        "companyDescription": {"text": "<p>About us. " * 20 + "</p>"},
        "jobDescription": {"text": "<p>The role. " * 30 + "</p>"},
        "qualifications": {"text": "<p>You bring. " * 20 + "</p>"}}}}
    JF.requests = _FakeRequests([("api.smartrecruiters.com/v1/companies/Freshworks/postings/744000137263090",
                                  _Resp(200, sect))])
    try:
        text = JF._fetch_smartrecruiters_jd("https://jobs.smartrecruiters.com/Freshworks/744000137263090")
        assert text and len(text) >= 600 and "The role." in text and "You bring." in text
        assert JF._fetch_smartrecruiters_jd("https://jobs.smartrecruiters.com/Freshworks/") is None  # no id → no call
    finally:
        JF.requests = saved
    print("✓ smartrecruiters: company+id parsed from URL, sections joined, floor enforced")


def test_dispatch_block_is_a_no_and_failure_falls_through():
    saved = JF.requests
    saved_pw = JF._fetch_playwright
    JF._fetch_playwright = lambda url: None     # keep the test OFFLINE — no chromium, no network
    try:
        # (a) branch success → generic page fetch is never attempted
        long_jd = "<p>Full JD text. " * 60 + "</p>"
        fake = _FakeRequests([("/wday/cxs/", _Resp(200, {"jobPostingInfo": {"jobDescription": long_jd}}))])
        JF.requests = fake
        out = JF.fetch_full_jd(_WD_URL)
        assert out and "Full JD text." in out
        assert len(fake.calls) == 1 and "/wday/cxs/" in fake.calls[0][0]

        # (b) 403 → a "no": returns None, does NOT retry, does NOT hit the page
        fake = _FakeRequests([("/wday/cxs/", _Resp(403))])
        JF.requests = fake
        assert JF.fetch_full_jd(_WD_URL) is None
        assert len(fake.calls) == 1                     # exactly one attempt, nothing after

        # (c) 404 on the API → guarded fallback: generic page path IS attempted (today's behavior)
        fake = _FakeRequests([("/wday/cxs/", _Resp(404))])
        JF.requests = fake
        assert JF.fetch_full_jd(_WD_URL) is None        # page also yields nothing in the stub
        assert len(fake.calls) == 2 and fake.calls[1][0] == _WD_URL      # fell through to the page
        # the GENERIC path also identifies honestly — no spoofed browser UA anywhere
        assert fake.calls[1][1]["headers"]["User-Agent"].startswith("job-finder-india/")
        assert "Mozilla" not in JF.UA                    # the canonical UA is the honest one

        # (d) 403 on the GENERIC page → same contract: one attempt, no playwright render
        pw_calls = []
        JF._fetch_playwright = lambda url: pw_calls.append(url)
        fake = _FakeRequests([("example.com", _Resp(403))])
        JF.requests = fake
        assert JF.fetch_full_jd("https://example.com/roles/12345") is None
        assert len(fake.calls) == 1 and pw_calls == []   # no retry, no browser-render around the block
    finally:
        JF.requests = saved
        JF._fetch_playwright = saved_pw
    print("✓ dispatch: success skips the page; 403/429 is a 'no' (one attempt); other failures degrade to today's path")


def test_ats_host_match_rejects_spoofs_accepts_tenants():
    """CodeQL py/incomplete-url-substring-sanitization (#4/#5): the ATS branch must
    match the host by suffix, not substring — a spoof host that merely CONTAINS the
    brand ('myworkdayjobs.com.evil.test') must NOT route into the JSON-API branch;
    it falls through to the generic page fetch. Real tenant subdomains still route.

    We spy on the two derivation functions directly (unambiguous: 'did the ATS
    branch select this host?'), rather than inferring from request URLs."""
    saved = (JF.requests, JF._fetch_playwright, JF._fetch_workday_jd, JF._fetch_smartrecruiters_jd)
    routed = {"workday": [], "sr": []}
    JF._fetch_playwright = lambda url: None
    JF._fetch_workday_jd = lambda url: routed["workday"].append(url)
    JF._fetch_smartrecruiters_jd = lambda url: routed["sr"].append(url)
    JF.requests = _FakeRequests([("", _Resp(404))])          # generic path yields nothing
    try:
        # --- spoofs: brand appears but NOT as a real host suffix → must NOT route to either API
        for spoof in ("https://myworkdayjobs.com.evil.test/careers/job/1",   # brand as prefix of attacker domain
                      "https://smartrecruiters.com.evil.test/acme/123456",
                      "https://evilmyworkdayjobs.com/job/1",                  # no dot boundary
                      "https://notsmartrecruiters.com/acme/123456"):
            assert JF.fetch_full_jd(spoof) is None
        assert routed == {"workday": [], "sr": []}, f"a spoof host routed into the ATS branch: {routed}"

        # --- legitimate tenants: MUST still route into the JSON-API branch
        JF._fetch_workday_jd = lambda url: (routed["workday"].append(url) or "WD JD text " * 80)
        JF._fetch_smartrecruiters_jd = lambda url: (routed["sr"].append(url) or "SR JD text " * 80)
        assert "WD JD text" in (JF.fetch_full_jd("https://genpact.myworkdayjobs.com/EC/job/City/Role_JR1") or "")
        assert "SR JD text" in (JF.fetch_full_jd("https://jobs.smartrecruiters.com/Acme/123456789") or "")
        assert len(routed["workday"]) == 1 and len(routed["sr"]) == 1     # each real tenant routed once
    finally:
        JF.requests, JF._fetch_playwright, JF._fetch_workday_jd, JF._fetch_smartrecruiters_jd = saved
    print("✓ ATS host match is suffix-based: brand-substring spoofs fall through; real tenants route")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} job_fetcher tests passed.")
