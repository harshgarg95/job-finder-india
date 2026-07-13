"""Tiny progress reporter — human-readable step lines to STDERR.

The agent-facing tools (`discover`, `prescreen`) print their machine-readable
result as JSON on STDOUT — that is what the calling CLI parses. Progress lines go
to STDERR so they never corrupt that JSON, while still telling a watching human
that a long step ("discovery: greenhouse 526 · adzuna 93") is moving, not stuck.

Silence entirely with JOBFINDER_QUIET=1 (e.g. in CI where only the JSON matters).
"""

from __future__ import annotations

import os
import sys


def emit(msg: str) -> None:
    """Write one progress line to stderr (no-op under JOBFINDER_QUIET)."""
    if os.environ.get("JOBFINDER_QUIET"):
        return
    print(msg, file=sys.stderr, flush=True)
