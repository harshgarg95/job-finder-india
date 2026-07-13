"""Progress-visibility tests (Change 2) — human-readable step lines to STDERR.

Proves progress.emit writes to stderr (and honours JOBFINDER_QUIET), and that
registry.discover streams a per-channel line as each provider runs. Offline: a
stub provider stands in for the real ATS/Adzuna channels — no network.

Run:  python -m pytest tests/test_progress.py -q   (or: python tests/test_progress.py)
"""

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfinder import progress
from jobfinder.discovery import registry
from jobfinder.discovery.base import Query
from jobfinder.schema import JobPosting


def test_emit_writes_to_stderr_and_respects_quiet():
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        progress.emit("hello-progress")
    assert "hello-progress" in buf.getvalue()

    os.environ["JOBFINDER_QUIET"] = "1"                 # CI: only the JSON on stdout matters
    try:
        buf2 = io.StringIO()
        with contextlib.redirect_stderr(buf2):
            progress.emit("should-be-silent")
        assert buf2.getvalue() == ""
    finally:
        del os.environ["JOBFINDER_QUIET"]
    print("✓ progress.emit → stderr; JOBFINDER_QUIET silences it")


def test_discover_streams_per_channel_progress():
    class Fake:
        id = "greenhouse"
        gap_fill_after = None
        last_errors: list = []

        def enabled(self, cfg):
            return True

        def fetch(self, q, cfg):
            return [JobPosting.from_dict({"title": "PM", "company": "Acme",
                                          "source": "greenhouse", "url": "https://x"})]

    saved = registry.build_providers
    registry.build_providers = lambda cfg: [Fake()]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            jobs, _reps = registry.discover(
                Query(titles=["PM"], location="India", limit_per_channel=5), {})
    finally:
        registry.build_providers = saved
    assert "discovery: greenhouse 1" in buf.getvalue()   # per-channel line, to stderr, as it runs
    assert len(jobs) == 1
    print("✓ registry.discover streams 'discovery: <channel> <count>' per channel to stderr")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} progress tests passed.")
