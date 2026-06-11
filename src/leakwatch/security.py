"""Audit a page's HTTP security headers.

A privacy scan already loads the page in a real browser, so the main response's
security posture is free to inspect — useful recon for the same audience. This
module is pure (no browser, no network) so it unit-tests cleanly; the engine just
hands it the response headers it captured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# (header, short label, severity if missing). Ordered most-important first.
SECURITY_HEADERS = [
    ("strict-transport-security", "HSTS", "high"),
    ("content-security-policy", "CSP", "high"),
    ("x-frame-options", "X-Frame-Options", "medium"),
    ("x-content-type-options", "X-Content-Type-Options", "medium"),
    ("referrer-policy", "Referrer-Policy", "low"),
    ("permissions-policy", "Permissions-Policy", "low"),
]
SECURITY_HEADER_KEYS = {h[0] for h in SECURITY_HEADERS}


@dataclass
class HeaderFinding:
    name: str          # short label, e.g. "HSTS"
    key: str           # header name, e.g. "strict-transport-security"
    present: bool
    severity: str      # high | medium | low


def audit_headers(headers: Dict[str, str]) -> List[HeaderFinding]:
    """Return a finding per security header, in importance order."""

    low = {(k or "").lower(): v for k, v in (headers or {}).items()}
    return [
        HeaderFinding(name=name, key=key, present=key in low, severity=sev)
        for key, name, sev in SECURITY_HEADERS
    ]


def missing_headers(findings: List[HeaderFinding]) -> List[HeaderFinding]:
    return [f for f in findings if not f.present]


def header_grade(findings: List[HeaderFinding]) -> str:
    """A quick A–F grade from how many (weighted) headers are present."""

    weight = {"high": 3, "medium": 2, "low": 1}
    total = sum(weight[f.severity] for f in findings)
    have = sum(weight[f.severity] for f in findings if f.present)
    if total == 0:
        return "A"
    ratio = have / total
    if ratio >= 0.95:
        return "A"
    if ratio >= 0.75:
        return "B"
    if ratio >= 0.5:
        return "C"
    if ratio >= 0.25:
        return "D"
    return "F"
