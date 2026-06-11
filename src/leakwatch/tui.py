"""The live Textual dashboard — verdict bar, streaming feed, rollup, and panels.

Imported lazily by the CLI so text/JSON output never needs Textual installed.
The futurism is the live, colour-drenched stream, not pixels: requests scroll in
as the page loads, each tinted by what kind of tracker it is, and the bottom
panels summarise fingerprinting, cookies/storage, and the category breakdown.
"""

from __future__ import annotations

from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from leakwatch.classify import classify_host
from leakwatch.model import (
    CATEGORY_ADVERTISING,
    CATEGORY_ANALYTICS,
    CATEGORY_CDN,
    CATEGORY_DATA_BROKER,
    CATEGORY_FINGERPRINTING,
    CATEGORY_ORDER,
    CATEGORY_SESSION_REPLAY,
    CATEGORY_SOCIAL,
    Request,
    ScanResult,
)
from leakwatch.report import category_counts, consent_label
from leakwatch.security import audit_headers

_CATEGORY_COLOR = {
    CATEGORY_DATA_BROKER: "bright_red",
    CATEGORY_SESSION_REPLAY: "red",
    CATEGORY_FINGERPRINTING: "magenta",
    CATEGORY_ADVERTISING: "yellow",
    CATEGORY_SOCIAL: "cyan",
    CATEGORY_ANALYTICS: "blue",
    CATEGORY_CDN: "green",
}


class RequestSeen(Message):
    def __init__(self, request: Request) -> None:
        self.request = request
        super().__init__()


class ScanDone(Message):
    def __init__(self, result: ScanResult) -> None:
        self.result = result
        super().__init__()


class LeakwatchApp(App):
    """A single-scan live dashboard."""

    CSS = """
    #verdict {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $panel;
    }
    #main { height: 1fr; }
    #feed { width: 2fr; border: round $primary; }
    #companies { width: 1fr; border: round $secondary; }
    #panels { height: 10; }
    .panel { width: 1fr; border: round $accent; padding: 0 1; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "rescan", "Rescan"),
    ]

    def __init__(self, url: str, scan_kwargs: Optional[dict] = None) -> None:
        super().__init__()
        self._url = url
        self._scan_kwargs = scan_kwargs or {}
        self._result: Optional[ScanResult] = None
        self._seen = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Scanning " + self._url + " ...", id="verdict")
        with Horizontal(id="main"):
            yield RichLog(id="feed", highlight=False, markup=True, wrap=False)
            table = DataTable(id="companies", zebra_stripes=True)
            table.add_columns("Company", "Domains", "Categories")
            yield table
        with Horizontal(id="panels"):
            fp = Static("—", id="fingerprints", classes="panel")
            fp.border_title = "Fingerprinting"
            yield fp
            ck = Static("—", id="cookies", classes="panel")
            ck.border_title = "Cookies & Storage"
            yield ck
            cat = Static("—", id="categories", classes="panel")
            cat.border_title = "By category"
            yield cat
            sec = Static("—", id="security", classes="panel")
            sec.border_title = "Security headers"
            yield sec
        yield Footer()

    def on_mount(self) -> None:
        self.title = "leakwatch"
        self.sub_title = "scanning " + self._url + " ..."
        self._run_scan()

    def action_rescan(self) -> None:
        self.query_one("#feed", RichLog).clear()
        self.query_one("#companies", DataTable).clear()
        self.query_one("#verdict", Static).update("Scanning " + self._url + " ...")
        for pid in ("#fingerprints", "#cookies", "#categories", "#security"):
            self.query_one(pid, Static).update("—")
        self.sub_title = "scanning " + self._url + " ..."
        self._seen = 0
        self._run_scan()

    @work(exclusive=True)
    async def _run_scan(self) -> None:
        from leakwatch.engine import scan_async

        def emit(request: Request) -> None:
            self.post_message(RequestSeen(request))

        try:
            result = await scan_async(self._url, on_request=emit, **self._scan_kwargs)
        except Exception as exc:  # noqa: BLE001
            result = ScanResult(url=self._url, error=str(exc).splitlines()[0])
        self.post_message(ScanDone(result))

    def on_request_seen(self, message: RequestSeen) -> None:
        request = message.request
        feed = self.query_one("#feed", RichLog)
        if not request.is_third_party:
            return
        self._seen += 1
        self.sub_title = f"scanning ... {self._seen} third-party requests"
        hit = classify_host(request.host)
        if hit is not None:
            color = _CATEGORY_COLOR.get(hit.category, "white")
            tag = hit.category
            label = f"{hit.entity}"
        else:
            color, tag, label = "grey50", "third-party", ""
        flag = " [dim](pre-consent)[/]" if request.before_consent else ""
        feed.write(
            f"[{color}]{request.host:<34}[/] [dim]{request.resource_type:<10}[/] "
            f"[{color}]{tag}[/] {label}{flag}"
        )

    def on_scan_done(self, message: ScanDone) -> None:
        result = message.result
        self._result = result
        self._render_verdict(result)
        self._render_companies(result)
        self._render_panels(result)
        self._render_footer_note(result)

    def _render_verdict(self, result: ScanResult) -> None:
        verdict = result.verdict
        bar = self.query_one("#verdict", Static)
        if result.error and not verdict:
            bar.update(f"[bright_red]scan failed: {result.error}[/]")
            return
        if result.blocked:
            bar.update(f"[bright_red]⚠ blocked — {result.blocked_reason}[/]")
            return
        if verdict is None:
            bar.update("scan complete")
            return
        gauge = _gauge(verdict.score)
        bar.update(
            f"{verdict.headline}    {gauge}  "
            f"{verdict.score}/100 ({verdict.grade})"
        )

    def _render_companies(self, result: ScanResult) -> None:
        table = self.query_one("#companies", DataTable)
        table.clear()
        for company in result.companies:
            place = (
                f"{company.name} [{company.country}]"
                if company.country
                else company.name
            )
            table.add_row(
                place, str(len(company.domains)), ", ".join(company.categories)
            )

    def _render_panels(self, result: ScanResult) -> None:
        self.query_one("#fingerprints", Static).update(_fingerprint_panel(result))
        self.query_one("#cookies", Static).update(_cookies_panel(result))
        self.query_one("#categories", Static).update(_categories_panel(result))
        self.query_one("#security", Static).update(_security_panel(result))

    def _render_footer_note(self, result: ScanResult) -> None:
        feed = self.query_one("#feed", RichLog)
        third = sum(1 for r in result.requests if r.is_third_party)
        tracked = len(result.trackers)
        active_fp = len([f for f in result.fingerprints if f.count > 0])
        feed.write("")
        if result.error:
            feed.write(f"[bright_red]✕ {result.error}[/]")
        if result.blocked:
            feed.write(f"[bright_red]⚠ blocked: {result.blocked_reason}[/]")
        feed.write(f"[dim]consent: {consent_label(result)}[/]")
        feed.write(
            f"[green]✓ scan complete[/] — {third} third-party request(s), "
            f"{tracked} known tracker(s), {active_fp} fingerprinting method(s). "
            f"Press [b]q[/] to quit, [b]r[/] to rescan."
        )
        verdict = result.verdict
        if verdict is not None:
            self.sub_title = (
                f"done · {verdict.score}/100 ({verdict.grade}) "
                f"· consent {consent_label(result)} · q to quit"
            )
        else:
            self.sub_title = "done · q to quit"


def _fingerprint_panel(result: ScanResult) -> str:
    active = [f for f in result.fingerprints if f.count > 0]
    if not active:
        return "[green]none detected[/]"
    return "\n".join(f"[magenta]{f.technique:<10}[/] ×{f.count}" for f in active)


def _cookies_panel(result: ScanResult) -> str:
    cookies = result.cookies
    first = sum(1 for c in cookies if not c.is_third_party)
    third = sum(1 for c in cookies if c.is_third_party)
    secure = sum(1 for c in cookies if c.secure)
    http_only = sum(1 for c in cookies if c.http_only)
    local = sum(1 for s in result.storage if s.kind == "local")
    session = sum(1 for s in result.storage if s.kind == "session")
    return (
        f"cookies: [b]{len(cookies)}[/]  (1st {first} · [yellow]3rd {third}[/])\n"
        f"secure {secure} · httpOnly {http_only}\n"
        f"storage keys: local {local} · session {session}"
    )


def _categories_panel(result: ScanResult) -> str:
    counts = category_counts(result)
    if not counts:
        return "[green]no known trackers[/]"
    lines = []
    for category in CATEGORY_ORDER:
        n = counts.get(category)
        if n:
            color = _CATEGORY_COLOR.get(category, "white")
            lines.append(f"[{color}]{category:<14}[/] {n}")
    return "\n".join(lines)


def _security_panel(result: ScanResult) -> str:
    findings = audit_headers(result.security_headers)
    sev_color = {"high": "red", "medium": "yellow", "low": "grey50"}
    lines = []
    for f in findings:
        if f.present:
            lines.append(f"[green]✓[/] {f.name}")
        else:
            lines.append(f"[{sev_color[f.severity]}]✗ {f.name}[/]")
    return "\n".join(lines)


def _gauge(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    if score <= 25:
        color = "green"
    elif score <= 50:
        color = "yellow"
    elif score <= 75:
        color = "dark_orange"
    else:
        color = "red"
    return f"[{color}]{'█' * filled}[/][grey30]{'░' * (width - filled)}[/]"


def run_dashboard(url: str, scan_kwargs: Optional[dict] = None) -> Optional[ScanResult]:
    app = LeakwatchApp(url, scan_kwargs=scan_kwargs)
    app.run()
    return app._result
