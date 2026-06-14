"""Discovery adapter interface.

Every channel — the free public-ATS scan, Google Jobs, Apify-Naukri — implements
this one shape, so the pipeline treats them uniformly:

    provider.id                       -> short stable id, e.g. "ats", "google_jobs"
    provider.enabled(cfg)  -> bool    -> is it turned on + are its prerequisites met
    provider.fetch(query, cfg) -> list[JobPosting]

`fetch` MUST return real results or an empty list. It must NEVER fabricate a
job. If a channel errors, it raises; the registry records the error and moves on
(a broken channel is reported, never silently turned into "0 jobs found").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..schema import JobPosting


@dataclass
class Query:
    """What the user is looking for. Channels translate this to their own params."""
    titles: list[str] = field(default_factory=list)   # role titles / keywords
    location: str = "India"
    remote_ok: bool = True
    limit_per_channel: int = 60                        # cap to stay free-tier-friendly
    raw_keywords: str = ""                             # free-text fallback


class Provider(Protocol):
    id: str

    def enabled(self, cfg: dict) -> bool:
        """True only if this channel is switched on AND its prerequisites
        (e.g. an API token) are present. Off-by-default channels return False
        unless the user explicitly enabled them in config/.env."""
        ...

    def fetch(self, query: Query, cfg: dict) -> list[JobPosting]:
        """Return real, normalized postings (possibly empty). Never fabricate."""
        ...
