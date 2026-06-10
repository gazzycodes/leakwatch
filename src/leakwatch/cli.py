"""Command-line interface for leakwatch.

    leakwatch example.com                 live dashboard for one site
    leakwatch example.com --no-tui        plain-text report
    leakwatch example.com --json          machine-readable output
    leakwatch batch sites.txt             ranked leaderboard scorecard
    leakwatch diff example.com -b base.json   CI gate: fail on new trackers
    leakwatch login example.com -o auth.json  save a sign-in session
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import List, Optional, Sequence

from leakwatch import __version__

EXIT_OK = 0
EXIT_FOUND = 1
EXIT_ERROR = 2

_COMMANDS = {"scan", "batch", "diff", "login", "update-data"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leakwatch",
        description="See every tracker, data broker, fingerprinting trick, and "
        "session recorder watching you on any website.",
    )
    parser.add_argument("--version", action="version", version=f"leakwatch {__version__}")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Scan a single URL (default).")
    scan.add_argument("url", help="URL or domain to scan.")
    scan.add_argument("--no-tui", action="store_true", help="Plain text, no dashboard.")
    scan.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    scan.add_argument("--timeout", type=int, default=30000, help="Page timeout (ms).")
    scan.add_argument("--storage-state", metavar="FILE", help="Saved login session.")
    scan.add_argument(
        "--login",
        action="store_true",
        help="Open a visible browser to sign in first, then scan that session.",
    )
    scan.add_argument(
        "--no-consent",
        action="store_true",
        help="Do not attempt to click the consent banner.",
    )

    batch = sub.add_parser("batch", help="Scan many sites and rank them.")
    batch.add_argument("file", help="File with one URL per line (# for comments).")
    batch.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="Scorecard format (default: text).",
    )
    batch.add_argument("--out", metavar="FILE", help="Write the scorecard to a file.")
    batch.add_argument("--timeout", type=int, default=30000, help="Page timeout (ms).")

    diff = sub.add_parser("diff", help="Compare a scan to a baseline (CI gate).")
    diff.add_argument("url", help="URL or domain to scan.")
    diff.add_argument("-b", "--baseline", required=True, help="Baseline JSON file.")
    diff.add_argument("--timeout", type=int, default=30000, help="Page timeout (ms).")
    diff.add_argument(
        "--save-baseline",
        metavar="FILE",
        help="Write the current scan as a new baseline and exit 0.",
    )

    login = sub.add_parser("login", help="Save a sign-in session for later scans.")
    login.add_argument("url", help="URL to open for signing in.")
    login.add_argument(
        "-o", "--out", default="auth.json", help="Where to save the session."
    )

    sub.add_parser("update-data", help="Refresh the bundled tracker dataset.")
    return parser


def _preprocess(argv: List[str]) -> List[str]:
    """Allow `leakwatch example.com` with no explicit `scan` subcommand."""

    for token in argv:
        if token in ("-h", "--help", "--version"):
            return argv
        if token.startswith("-"):
            continue
        if token not in _COMMANDS:
            return ["scan", *argv]
        return argv
    return argv


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(_preprocess(raw))

    if args.command == "batch":
        return _cmd_batch(args)
    if args.command == "diff":
        return _cmd_diff(args)
    if args.command == "login":
        return _cmd_login(args)
    if args.command == "update-data":
        return _cmd_update_data()
    if args.command == "scan":
        return _cmd_scan(args)
    parser.print_help()
    return EXIT_OK


def _cmd_scan(args) -> int:
    from leakwatch.engine import capture_login, scan
    from leakwatch.report import render_json, render_text

    storage_state = args.storage_state
    if args.login:
        tmp = "leakwatch.storage.json"
        try:
            asyncio.run(capture_login(args.url, tmp))
        except Exception as exc:  # noqa: BLE001
            return _fail(exc)
        storage_state = tmp

    if args.no_tui or args.json:
        try:
            result = scan(
                args.url,
                timeout_ms=args.timeout,
                storage_state=storage_state,
                detect_consent=not args.no_consent,
            )
        except Exception as exc:  # noqa: BLE001
            return _fail(exc)
        print(render_json(result) if args.json else render_text(result))
        return EXIT_OK

    try:
        from leakwatch.tui import run_dashboard
    except ImportError:
        return _fail(RuntimeError("Textual not installed; use --no-tui or --json."))
    run_dashboard(
        args.url,
        scan_kwargs={
            "timeout_ms": args.timeout,
            "storage_state": storage_state,
            "detect_consent": not args.no_consent,
        },
    )
    return EXIT_OK


def _cmd_batch(args) -> int:
    from leakwatch.engine import scan
    from leakwatch.report import render_scorecard

    urls = _read_url_list(args.file)
    if not urls:
        return _fail(RuntimeError(f"No URLs found in {args.file}"))
    results = []
    for url in urls:
        print(f"scanning {url} ...", file=sys.stderr)
        try:
            results.append(scan(url, timeout_ms=args.timeout))
        except Exception as exc:  # noqa: BLE001
            print(f"  skipped ({exc})", file=sys.stderr)
    card = render_scorecard(results, fmt=args.format)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(card + "\n")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(card)
    return EXIT_OK


def _cmd_diff(args) -> int:
    from leakwatch.engine import scan
    from leakwatch.report import diff_against_baseline, render_json

    try:
        result = scan(args.url, timeout_ms=args.timeout)
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)

    if args.save_baseline:
        with open(args.save_baseline, "w", encoding="utf-8") as handle:
            handle.write(render_json(result))
        print(f"Saved baseline to {args.save_baseline}", file=sys.stderr)
        return EXIT_OK

    try:
        with open(args.baseline, encoding="utf-8") as handle:
            baseline = json.load(handle)
    except OSError as exc:
        return _fail(exc)

    new = diff_against_baseline(result, baseline)
    if new:
        print("New third-party trackers since baseline:")
        for domain in new:
            print(f"  + {domain}")
        return EXIT_FOUND
    print("No new third-party trackers.")
    return EXIT_OK


def _cmd_login(args) -> int:
    from leakwatch.engine import capture_login

    try:
        asyncio.run(capture_login(args.url, args.out))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    return EXIT_OK


def _cmd_update_data() -> int:
    print(
        "Bundled dataset is a curated seed. Full DuckDuckGo Tracker Radar refresh "
        "is planned for a later release.",
        file=sys.stderr,
    )
    return EXIT_OK


def _read_url_list(path: str) -> List[str]:
    urls: List[str] = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except OSError as exc:
        print(f"leakwatch: {exc}", file=sys.stderr)
    return urls


def _fail(exc: Exception) -> int:
    print(f"leakwatch: {exc}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
