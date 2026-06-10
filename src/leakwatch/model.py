"""Core data structures shared across the engine, classifier, and renderers.

These are deliberately plain dataclasses with no third-party dependencies so the
classification, scoring, and reporting layers can be imported and unit-tested
without a browser present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Tracker categories, ordered roughly by how invasive they are. The classifier
# normalises every dataset label down to one of these.
CATEGORY_ADVERTISING = "advertising"
CATEGORY_ANALYTICS = "analytics"
CATEGORY_SOCIAL = "social"
CATEGORY_SESSION_REPLAY = "session-replay"
CATEGORY_DATA_BROKER = "data-broker"
CATEGORY_FINGERPRINTING = "fingerprinting"
CATEGORY_CDN = "cdn"
CATEGORY_OTHER = "other"

CATEGORY_ORDER = [
    CATEGORY_DATA_BROKER,
    CATEGORY_SESSION_REPLAY,
    CATEGORY_FINGERPRINTING,
    CATEGORY_ADVERTISING,
    CATEGORY_SOCIAL,
    CATEGORY_ANALYTICS,
    CATEGORY_CDN,
    CATEGORY_OTHER,
]


@dataclass
class Request:
    """A single network request observed during a scan."""

    url: str
    host: str
    method: str
    resource_type: str
    is_third_party: bool
    elapsed_ms: int
    before_consent: bool = True


@dataclass
class Cookie:
    name: str
    domain: str
    is_third_party: bool
    http_only: bool = False
    secure: bool = False
    same_site: str = ""
    session: bool = True


@dataclass
class StorageWrite:
    kind: str  # "local" or "session"
    key: str
    origin: str


@dataclass
class Fingerprint:
    """A fingerprinting technique the page exercised, with a call count."""

    technique: str  # canvas | webgl | audio | fonts | navigator
    api: str
    count: int = 0


@dataclass
class TrackerHit:
    """A third-party domain matched to the tracker dataset."""

    domain: str
    category: str
    entity: str
    entity_country: str = ""
    source: str = "tracker-radar"


@dataclass
class Company:
    """A parent entity with the tracker domains rolled up under it."""

    name: str
    country: str
    domains: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


@dataclass
class Verdict:
    """The one-line summary shown at the top of every scan."""

    score: int
    grade: str
    tracker_count: int
    company_count: int
    broker_count: int
    fingerprint_count: int
    records_screen: bool
    pre_consent_count: int
    headline: str


@dataclass
class ScanResult:
    """Everything a single scan produced."""

    url: str
    final_url: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    requests: List[Request] = field(default_factory=list)
    cookies: List[Cookie] = field(default_factory=list)
    storage: List[StorageWrite] = field(default_factory=list)
    fingerprints: List[Fingerprint] = field(default_factory=list)
    trackers: List[TrackerHit] = field(default_factory=list)
    companies: List[Company] = field(default_factory=list)
    verdict: Optional[Verdict] = None

    def to_dict(self) -> Dict:
        """A JSON-serialisable view, used by ``--json`` and the scorecard."""

        return {
            "url": self.url,
            "final_url": self.final_url,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "verdict": _verdict_dict(self.verdict),
            "trackers": [t.__dict__ for t in self.trackers],
            "companies": [c.__dict__ for c in self.companies],
            "fingerprints": [f.__dict__ for f in self.fingerprints],
            "cookies": [c.__dict__ for c in self.cookies],
            "storage": [s.__dict__ for s in self.storage],
            "request_count": len(self.requests),
            "third_party_request_count": sum(
                1 for r in self.requests if r.is_third_party
            ),
        }


def _verdict_dict(verdict: Optional[Verdict]) -> Optional[Dict]:
    return verdict.__dict__ if verdict else None
