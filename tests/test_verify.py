"""Verifiability classifier tests — the "Couldn't verify" gate (FIX A). No network.

Proves the deterministic gate that keeps a job the tool couldn't actually read
out of APPLY/STRETCH: empty/too-thin JD → no_jd; bare domain or careers/list
landing → non_job_link; a specific posting with a real JD → ok.

Run:  python -m pytest tests/test_verify.py -q   (or: python tests/test_verify.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import verify


def test_no_jd_empty_or_too_thin():
    for jd in ("", "   ", "x" * (verify.MIN_JD_CHARS - 1)):
        st, reason = verify.classify("https://acme.com/jobs/12345", jd)
        assert st == "no_jd", (jd, st)
    # A full JD on a specific link is fine.
    assert verify.classify("https://acme.com/jobs/12345", "x" * 500)[0] == "ok"
    print("✓ empty / too-thin JD → no_jd")


def test_non_job_link_bare_domain_and_landing():
    for url in ("https://acme.com", "https://acme.com/", "acme.com",
                "https://acme.com/careers", "https://acme.com/jobs", "https://x.io/openings/",
                "https://co.com/positions", "https://co.com/join-us"):
        st, _ = verify.classify(url, "x" * 500)          # real JD, but the LINK is not a posting
        assert st == "non_job_link", url
    assert verify.classify("", "x" * 500)[0] == "non_job_link"     # no link at all
    print("✓ bare domain + careers/list landing + empty link → non_job_link")


def test_ok_specific_posting():
    for url in ("https://boards.greenhouse.io/acme/jobs/7719673003",
                "https://www.adzuna.in/details/5793371652",
                "https://in.linkedin.com/jobs/view/ai-manager-at-acme-4012345678",
                "https://jobs.lever.co/acme/3fa1c0de-aaaa-bbbb-cccc-1234567890ab"):
        st, _ = verify.classify(url, "x" * 500)
        assert st == "ok", url
    print("✓ specific-posting URLs (with a job id) → ok")


def test_deep_job_path_without_numeric_id_not_flagged():
    # A real posting whose path is neither bare nor a landing word → ok even w/o a numeric id.
    st, _ = verify.classify("https://careers.acme.com/job/ai-delivery-manager", "x" * 500)
    assert st == "ok"
    print("✓ deep job path without a numeric id is not falsely flagged")


def test_url_only_recheck_ignores_no_jd():
    # jd_text=None (render time): only the link is checkable, not the JD.
    assert verify.classify("https://acme.com/jobs/12345", None) == ("ok", "")
    assert verify.classify("https://acme.com/careers", None)[0] == "non_job_link"
    print("✓ URL-only re-check (jd_text=None) checks the link, not the JD")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} verify tests passed.")
