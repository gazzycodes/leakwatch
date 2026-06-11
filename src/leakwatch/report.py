"""Non-TUI renderers: plain text, JSON, and the batch leaderboard scorecard.

Used for ``--no-tui``, ``--json``, piping into other tools, and the shareable
"card" the batch mode produces.
"""

from __future__ import annotations

import json
from typing import List

from leakwatch.model import (
    CATEGORY_ORDER,
    CONSENT_ACCEPTED,
    CONSENT_PRESENT,
    CONSENT_SKIPPED,
    ScanResult,
)
from leakwatch.security import audit_headers, header_grade


def category_counts(result: ScanResult) -> dict:
    """Number of distinct tracker domains per category."""

    counts: dict = {}
    for hit in result.trackers:
        counts[hit.category] = counts.get(hit.category, 0) + 1
    return counts


def render_json(result: ScanResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)


def consent_label(result: ScanResult) -> str:
    cmp = f" ({result.consent_cmp})" if result.consent_cmp else ""
    if result.consent_state == CONSENT_ACCEPTED:
        return f"accepted{cmp}"
    if result.consent_state == CONSENT_PRESENT:
        return f"banner present{cmp} — not auto-accepted (may under-report)"
    if result.consent_state == CONSENT_SKIPPED:
        return "skipped"
    return "no banner detected"


def render_text(result: ScanResult) -> str:
    """A compact, colour-free summary of a single scan."""

    lines: List[str] = []
    target = result.final_url or result.url
    lines.append(f"leakwatch · {target}")
    if result.error:
        lines.append(f"  error: {result.error}")
    if result.blocked:
        lines.append(f"  ! blocked: {result.blocked_reason}")
    verdict = result.verdict
    if verdict:
        lines.append(f"  {verdict.headline}")
        lines.append(f"  leakage score: {verdict.score}/100  (grade {verdict.grade})")
    lines.append(f"  consent: {consent_label(result)}")
    lines.append("")

    if result.companies:
        lines.append("Companies receiving data:")
        for company in result.companies:
            cats = ", ".join(company.categories)
            place = f" [{company.country}]" if company.country else ""
            lines.append(
                f"  - {company.name}{place}: "
                f"{len(company.domains)} domain(s) — {cats}"
            )
        lines.append("")

    by_category = _group_by_category(result)
    if by_category:
        lines.append("Trackers by category:")
        for category in CATEGORY_ORDER:
            domains = by_category.get(category)
            if domains:
                lines.append(f"  {category}: {', '.join(sorted(domains))}")
        lines.append("")

    active_fp = [f for f in result.fingerprints if f.count > 0]
    if active_fp:
        techniques = ", ".join(f"{f.technique}({f.count})" for f in active_fp)
        lines.append(f"Fingerprinting: {techniques}")

    findings = audit_headers(result.security_headers)
    present = [f.name for f in findings if f.present]
    missing = [f.name for f in findings if not f.present]
    lines.append(
        f"Security headers (grade {header_grade(findings)}): "
        f"present: {', '.join(present) or 'none'}; "
        f"missing: {', '.join(missing) or 'none'}"
    )

    third = sum(1 for r in result.requests if r.is_third_party)
    lines.append(
        f"Requests: {len(result.requests)} total, {third} third-party · "
        f"cookies: {len(result.cookies)} · storage keys: {len(result.storage)} · "
        f"scanned in {result.duration_ms} ms"
    )
    return "\n".join(lines)


def _group_by_category(result: ScanResult):
    grouped = {}
    for hit in result.trackers:
        grouped.setdefault(hit.category, set()).add(hit.domain)
    return grouped


def render_scorecard(results: List[ScanResult], *, fmt: str = "text") -> str:
    """Render a ranked leaderboard across many scans (batch mode)."""

    ranked = sorted(
        results,
        key=lambda r: (r.verdict.score if r.verdict else -1),
        reverse=True,
    )
    if fmt == "json":
        return json.dumps([r.to_dict() for r in ranked], indent=2, sort_keys=True)
    if fmt == "markdown":
        return _scorecard_markdown(ranked)
    return _scorecard_text(ranked)


def _score_dot(score: int) -> str:
    if score <= 25:
        return "\U0001f7e2"  # green
    if score <= 50:
        return "\U0001f7e1"  # yellow
    if score <= 75:
        return "\U0001f7e0"  # orange
    return "\U0001f534"  # red


def _status_note(result: ScanResult) -> str:
    """Flag sites we could not fully measure, so they are not read as 'clean'."""

    if result.blocked:
        return "blocked"
    if _is_error_page(result) or result.error:
        return "failed"
    if result.consent_state == CONSENT_PRESENT:
        return "consent wall"
    return ""


def _is_error_page(result: ScanResult) -> bool:
    final = result.final_url or ""
    return final.startswith("chrome-error") or "chromewebdata" in final


def _site_label(result: ScanResult) -> str:
    from leakwatch.classify import host_from_url

    host = host_from_url(result.final_url or "")
    if not host or host == "chromewebdata" or _is_error_page(result):
        host = host_from_url(result.url)
    return host or result.url


def _row_fields(result: ScanResult):
    verdict = result.verdict
    site = _site_label(result)
    score = verdict.score if verdict else 0
    grade = verdict.grade if verdict else "?"
    trackers = verdict.tracker_count if verdict else 0
    brokers = verdict.broker_count if verdict else 0
    replay = "yes" if (verdict and verdict.records_screen) else "no"
    fp = "yes" if (verdict and verdict.fingerprint_count) else "no"
    note = _status_note(result)
    return site, score, grade, trackers, brokers, replay, fp, note


def _scorecard_text(ranked: List[ScanResult]) -> str:
    header = (
        f"{'#':>2}  {'site':<26}{'score':>6} {'grd':>4}  "
        f"{'trk':>4}  {'brk':>4}  {'rec':>3}  {'fp':>3}  note"
    )
    lines = ["leakwatch leaderboard — ranked by leakage", header, "-" * len(header)]
    for i, result in enumerate(ranked, 1):
        site, score, grade, trackers, brokers, replay, fp, note = _row_fields(result)
        lines.append(
            f"{i:>2}  {site[:26]:<26}{score:>6} {grade:>4}  "
            f"{trackers:>4}  {brokers:>4}  {replay:>3}  {fp:>3}  {note}"
        )
    return "\n".join(lines)


def _scorecard_markdown(ranked: List[ScanResult]) -> str:
    lines = [
        "| # | Site | Leakage | Trackers | Brokers | Records screen "
        "| Fingerprinting | Note |",
        "|--:|------|:--------|--------:|--------:|:--------------:"
        "|:--------------:|------|",
    ]
    for i, result in enumerate(ranked, 1):
        site, score, grade, trackers, brokers, replay, fp, note = _row_fields(result)
        badge = f"{_score_dot(score)} {score} ({grade})"
        lines.append(
            f"| {i} | {site} | {badge} | {trackers} | {brokers} "
            f"| {replay} | {fp} | {note} |"
        )
    return "\n".join(lines)


def diff_against_baseline(result: ScanResult, baseline: dict):
    """Return the tracker domains present now but absent from a saved baseline."""

    old = {t["domain"] for t in baseline.get("trackers", [])}
    new = {t.domain for t in result.trackers}
    return sorted(new - old)
