"""Discovery-health tests — a network failure must never render as an honest empty.

Proves: all channels erroring (connection errors — e.g. Codex's sandboxed run) is a
LOUD failure with the network + stale-top.md warning, NOT "0 candidates"; a single
channel erroring while another returns jobs degrades quietly; and the registry marks
an errored channel as such so discovery_health flags it. No network.

Run:  python -m pytest tests/test_discovery_health.py -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder.discovery import registry
from jobfinder.discovery.base import Query
from jobfinder.discovery.registry import ChannelReport, discovery_health


def test_all_channels_errored_is_loud_failure_not_empty():
    reports = [
        ChannelReport("ats", True, count=0,
                      errors=["Acme(greenhouse:acme): Max retries exceeded: Failed to establish a new connection"]),
        ChannelReport("adzuna", True, count=0, errors=["Connection refused"]),
        ChannelReport("jsearch", True, count=0, errors=["getaddrinfo failed"]),
    ]
    h = discovery_health(reports)
    assert h["failed"] is True and h["ats_errored"] is True
    assert "no network access" in h["message"] and "Codex" in h["message"]
    assert "top.md was NOT updated" in h["message"]                 # stale-artifact warning
    assert 'not the same as "no jobs matched"'.lower() in h["message"].lower()
    assert {c["id"]: c["status"] for c in h["channels"]} == {"ats": "errored", "adzuna": "errored", "jsearch": "errored"}
    print("✓ all-channels-errored → LOUD failure (network + stale-top.md), never '0 candidates'")


def test_single_channel_errored_degrades_quietly():
    reports = [
        ChannelReport("ats", True, count=12),                        # floor returned jobs
        ChannelReport("adzuna", True, count=0, errors=["Connection refused"]),   # one channel down
    ]
    h = discovery_health(reports)
    assert h["failed"] is False and h["message"] == ""              # quiet degrade, run proceeds
    assert {c["id"]: c["status"] for c in h["channels"]} == {"ats": "ok", "adzuna": "errored"}
    print("✓ one channel errored + another returned jobs → quiet degrade (failed=False)")


def test_genuine_empty_and_http_error_distinguished():
    # all channels returned 0 with NO errors → a real empty, not a failure
    assert discovery_health([ChannelReport("ats", True, count=0),
                             ChannelReport("adzuna", True, count=0)])["failed"] is False
    # all errored but with HTTP (non-network) errors → failed, but NOT network-worded
    h = discovery_health([ChannelReport("ats", True, count=0, errors=["HTTP 500 internal error"])])
    assert h["failed"] is True and "no network access" not in h["message"]
    print("✓ genuine empty ≠ failure; HTTP-only errors flagged failed but not mislabelled 'no network'")


def test_registry_discover_marks_errored_channel():
    class Boom:
        id = "ats"
        gap_fill_after = None
        last_errors: list = []

        def enabled(self, cfg):
            return True

        def fetch(self, q, cfg):
            raise ConnectionError("Max retries exceeded: Failed to establish a new connection")

    saved = registry.build_providers
    registry.build_providers = lambda cfg: [Boom()]
    try:
        jobs, reports = registry.discover(Query(titles=["PM"], location="India", limit_per_channel=5), {})
    finally:
        registry.build_providers = saved
    assert jobs == [] and len(reports) == 1
    h = discovery_health(reports)
    assert h["failed"] is True and h["channels"][0]["status"] == "errored"   # errored, not a clean 0
    print("✓ registry.discover records an errored channel → discovery_health flags failed")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} discovery-health tests passed.")
