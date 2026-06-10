"""Map third-party domains to trackers, then roll them up to parent companies.

The dataset is a bundled JSON seed (a curated slice of the well-known tracker
lists). ``leakwatch update-data`` can later replace it with the full DuckDuckGo
Tracker Radar export; the matching logic here does not change.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from leakwatch.model import (
    CATEGORY_DATA_BROKER,
    CATEGORY_OTHER,
    CATEGORY_SESSION_REPLAY,
    Company,
    TrackerHit,
)

_DATA_FILE = Path(__file__).with_name("data") / "trackers.json"

# A small set of multi-label public suffixes so "bbc.co.uk" reduces to
# "bbc.co.uk" rather than "co.uk". Not exhaustive — good enough for grouping.
_MULTI_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "co.jp", "co.in", "com.au",
    "com.br", "com.cn", "co.kr", "co.nz", "co.za", "com.mx", "com.tr",
}


@lru_cache(maxsize=1)
def _load_dataset() -> Dict:
    with _DATA_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


def host_from_url(url: str) -> str:
    """Return the lowercased hostname for a URL, or '' if it has none."""

    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().lstrip(".")


def registrable_domain(host: str) -> str:
    """Reduce a hostname to its registrable domain (eTLD+1, approximately)."""

    host = host.lower().strip(".")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def is_third_party(host: str, site_domain: str) -> bool:
    """True when ``host`` belongs to a different registrable domain than the site."""

    if not host or not site_domain:
        return False
    return registrable_domain(host) != registrable_domain(site_domain)


def classify_host(host: str) -> Optional[TrackerHit]:
    """Match a hostname to the tracker dataset, longest suffix wins."""

    if not host:
        return None
    dataset = _load_dataset()
    domains: Dict[str, Dict] = dataset["domains"]
    labels = host.split(".")
    # Try the full host, then progressively broader parent domains.
    for start in range(len(labels) - 1):
        candidate = ".".join(labels[start:])
        entry = domains.get(candidate)
        if entry:
            return TrackerHit(
                domain=candidate,
                category=entry.get("category", CATEGORY_OTHER),
                entity=entry.get("entity", candidate),
                entity_country=entry.get("country", ""),
            )
    return None


def is_session_replay(host: str) -> bool:
    dataset = _load_dataset()
    replay = dataset.get("session_replay", [])
    return any(host == d or host.endswith("." + d) for d in replay)


def classify_hosts(
    hosts: List[str], site_domain: str
) -> Tuple[List[TrackerHit], List[Company]]:
    """Classify a list of (already third-party) hosts and roll up to companies."""

    seen: Dict[str, TrackerHit] = {}
    for host in hosts:
        hit = classify_host(host)
        if hit and hit.domain not in seen:
            seen[host] = hit
    hits = list(seen.values())
    return hits, rollup_companies(hits)


def rollup_companies(hits: List[TrackerHit]) -> List[Company]:
    """Group tracker hits under their parent entity."""

    companies: Dict[str, Company] = {}
    for hit in hits:
        company = companies.get(hit.entity)
        if company is None:
            company = Company(name=hit.entity, country=hit.entity_country)
            companies[hit.entity] = company
        if hit.domain not in company.domains:
            company.domains.append(hit.domain)
        if hit.category not in company.categories:
            company.categories.append(hit.category)
    # Brokers first, then by how many domains each company brings.
    return sorted(
        companies.values(),
        key=lambda c: (CATEGORY_DATA_BROKER not in c.categories, -len(c.domains)),
    )


def count_brokers(hits: List[TrackerHit]) -> int:
    return sum(1 for h in hits if h.category == CATEGORY_DATA_BROKER)


def count_session_replay(hits: List[TrackerHit]) -> int:
    return sum(1 for h in hits if h.category == CATEGORY_SESSION_REPLAY)
