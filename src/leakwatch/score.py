"""Turn a raw scan into a leakage score and the one-line verdict.

The score runs 0 (clean) to 100 (worst). It is intentionally simple and
explainable: a small fixed weight per tracker, with heavier penalties for the
things people actually care about — data brokers, session recorders, and
trackers that slip through a consent gate.
"""

from __future__ import annotations

from typing import List

from leakwatch.classify import classify_host, count_brokers, count_session_replay
from leakwatch.model import CONSENT_ACCEPTED, ScanResult, TrackerHit, Verdict

_W_TRACKER = 3
_W_COMPANY = 4
_W_BROKER = 12
_W_SESSION_REPLAY = 18
_W_FINGERPRINT = 6
_W_PRE_CONSENT = 5


def _grade(score: int) -> str:
    if score <= 5:
        return "A"
    if score <= 25:
        return "B"
    if score <= 50:
        return "C"
    if score <= 75:
        return "D"
    return "F"


def _pre_consent_trackers(result: ScanResult) -> int:
    """Distinct tracker hosts that fired before consent was accepted.

    Only meaningful when a consent banner actually existed and was accepted;
    otherwise there was no gate to jump, so we do not claim "before consent".
    """

    if result.consent_state != CONSENT_ACCEPTED:
        return 0
    hosts = {
        r.host
        for r in result.requests
        if r.is_third_party and r.before_consent and classify_host(r.host) is not None
    }
    return len(hosts)


def compute_verdict(result: ScanResult) -> Verdict:
    """Derive the headline verdict from a completed scan."""

    hits: List[TrackerHit] = result.trackers
    tracker_count = len(hits)
    company_count = len(result.companies)
    broker_count = count_brokers(hits)
    replay_count = count_session_replay(hits)
    fingerprint_count = len([f for f in result.fingerprints if f.count > 0])
    pre_consent = _pre_consent_trackers(result)

    raw = (
        tracker_count * _W_TRACKER
        + company_count * _W_COMPANY
        + broker_count * _W_BROKER
        + replay_count * _W_SESSION_REPLAY
        + fingerprint_count * _W_FINGERPRINT
        + min(pre_consent, 10) * _W_PRE_CONSENT
    )
    score = max(0, min(100, raw))

    headline = _headline(
        score=score,
        tracker_count=tracker_count,
        broker_count=broker_count,
        records_screen=replay_count > 0,
        fingerprint_count=fingerprint_count,
        pre_consent=pre_consent,
    )

    return Verdict(
        score=score,
        grade=_grade(score),
        tracker_count=tracker_count,
        company_count=company_count,
        broker_count=broker_count,
        fingerprint_count=fingerprint_count,
        records_screen=replay_count > 0,
        pre_consent_count=pre_consent,
        headline=headline,
    )


def _dot(score: int) -> str:
    if score <= 25:
        return "\U0001f7e2"  # green
    if score <= 50:
        return "\U0001f7e1"  # yellow
    if score <= 75:
        return "\U0001f7e0"  # orange
    return "\U0001f534"  # red


def _headline(
    *,
    score: int,
    tracker_count: int,
    broker_count: int,
    records_screen: bool,
    fingerprint_count: int,
    pre_consent: int,
) -> str:
    if tracker_count == 0:
        return f"{_dot(score)} No known trackers detected"
    parts = [f"{tracker_count} trackers"]
    if broker_count:
        parts.append(f"leaks to {broker_count} data broker{_s(broker_count)}")
    if records_screen:
        parts.append("records your screen")
    if fingerprint_count:
        parts.append(
            f"fingerprints you {fingerprint_count} way{_s(fingerprint_count)}"
        )
    if pre_consent:
        parts.append(f"{pre_consent} fired before consent")
    return f"{_dot(score)} " + " · ".join(parts)


def _s(n: int) -> str:
    return "" if n == 1 else "s"
