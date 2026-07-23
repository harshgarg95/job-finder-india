"""Suite-wide CI parity.

The developer's machine has real discovery keys (env + .env); CI has neither.
That difference once masked a real bug: the onboarding keys gate stayed silent
locally (keys present) but hung forever in CI (keyless) — three 10-minute
workflow timeouts before diagnosis. This fixture makes every test run keyless,
so the suite behaves identically on a keyed laptop and a bare runner. Tests
that need keys set them explicitly.
"""

import pytest


@pytest.fixture(autouse=True)
def _keyless_environment(monkeypatch):
    for k in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JSEARCH_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    # Point the onboarding keys-gate at a nonexistent .env so the developer's
    # real file can't satisfy it either. Tests that exercise the gate re-point
    # this themselves (and restore it).
    from jobfinder import onboard
    monkeypatch.setattr(onboard, "_ENV_PATH", "/nonexistent/.env", raising=False)
