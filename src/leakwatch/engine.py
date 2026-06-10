"""The scan engine: drive headless Chromium and record the tracking surface.

Only network metadata, cookies, storage keys, and fingerprinting call counts are
collected. The engine never downloads, stores, renders, or serves page content,
images, or media — by design, so a sensitive site in a batch only ever yields
tracker metadata.

Playwright is imported lazily inside the functions so the rest of the package
(classification, scoring, reporting) imports and tests without a browser.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, List, Optional

from leakwatch.classify import (
    classify_hosts,
    host_from_url,
    is_third_party,
    registrable_domain,
)
from leakwatch.instrument import INIT_SCRIPT, REPORT_EXPRESSION, STORAGE_EXPRESSION
from leakwatch.model import (
    Cookie,
    Fingerprint,
    Request,
    ScanResult,
    StorageWrite,
)
from leakwatch.score import compute_verdict

RequestCallback = Optional[Callable[[Request], None]]

# Selectors and labels that commonly accept a consent / cookie banner.
_CONSENT_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "button#accept-recommended-btn-handler",
    "button[aria-label*='accept' i]",
    "[data-testid*='accept' i]",
]
_CONSENT_LABELS = [
    "Accept all",
    "Accept All",
    "I accept",
    "Allow all",
    "Agree",
    "Got it",
]


async def scan_async(
    url: str,
    *,
    timeout_ms: int = 30000,
    settle_ms: int = 1500,
    storage_state: Optional[str] = None,
    headed: bool = False,
    detect_consent: bool = True,
    on_request: RequestCallback = None,
) -> ScanResult:
    """Scan a single URL and return a fully classified :class:`ScanResult`."""

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "playwright install chromium"
        ) from exc

    url = _normalise_url(url)
    site_domain = registrable_domain(host_from_url(url))
    requests: List[Request] = []
    consented = {"value": False}
    start = time.monotonic()
    result = ScanResult(url=url)

    def handle_request(req) -> None:
        host = host_from_url(req.url)
        record = Request(
            url=req.url,
            host=host,
            method=req.method,
            resource_type=req.resource_type,
            is_third_party=is_third_party(host, site_domain),
            elapsed_ms=int((time.monotonic() - start) * 1000),
            before_consent=not consented["value"],
        )
        requests.append(record)
        if on_request is not None:
            on_request(record)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        context = await browser.new_context(
            storage_state=storage_state if storage_state else None
        )
        await context.add_init_script(INIT_SCRIPT)
        page = await context.new_page()
        page.on("request", handle_request)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the scan
            result.error = str(exc).splitlines()[0]
        # Give late-firing trackers a bounded window. Wait for "load", but do
        # not hang on sites that keep a long-polling analytics socket open.
        try:
            await page.wait_for_load_state("load", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(settle_ms)

        if detect_consent:
            if await _try_accept_consent(page):
                consented["value"] = True
                await page.wait_for_timeout(2000)

        fingerprints = await _read_fingerprints(page)
        storage = await _read_storage(page)
        cookies = await _read_cookies(context, site_domain)
        result.final_url = page.url

        await context.close()
        await browser.close()

    result.duration_ms = int((time.monotonic() - start) * 1000)
    result.requests = requests
    result.fingerprints = fingerprints
    result.storage = storage
    result.cookies = cookies

    third_party_hosts = [r.host for r in requests if r.is_third_party]
    result.trackers, result.companies = classify_hosts(third_party_hosts, site_domain)
    result.verdict = compute_verdict(result)
    return result


def scan(url: str, **kwargs) -> ScanResult:
    """Synchronous wrapper around :func:`scan_async`."""

    return asyncio.run(scan_async(url, **kwargs))


async def capture_login(url: str, out_path: str, *, timeout_ms: int = 0) -> None:
    """Open a visible browser so the user can sign in; save the session blob.

    leakwatch never sees or stores a password — only the resulting Playwright
    ``storageState`` (cookies + localStorage), written locally to ``out_path``.
    """

    from playwright.async_api import async_playwright

    url = _normalise_url(url)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="load", timeout=timeout_ms or 60000)
        print(
            "A browser window is open. Sign in there, then press Enter here to "
            "save the session..."
        )
        await asyncio.get_event_loop().run_in_executor(None, input)
        await context.storage_state(path=out_path)
        await context.close()
        await browser.close()
    print(f"Saved authenticated session to {out_path}")


async def _try_accept_consent(page) -> bool:
    for selector in _CONSENT_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                await element.click(timeout=2000)
                return True
        except Exception:  # noqa: BLE001
            continue
    for label in _CONSENT_LABELS:
        try:
            button = page.get_by_role("button", name=label, exact=False)
            if await button.count() > 0:
                await button.first.click(timeout=2000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _read_fingerprints(page) -> List[Fingerprint]:
    try:
        raw = await page.evaluate(REPORT_EXPRESSION)
    except Exception:  # noqa: BLE001
        return []
    out: List[Fingerprint] = []
    for item in raw or []:
        out.append(
            Fingerprint(
                technique=item.get("technique", ""),
                api=item.get("api", ""),
                count=int(item.get("count", 0)),
            )
        )
    return out


async def _read_storage(page) -> List[StorageWrite]:
    try:
        raw = await page.evaluate(STORAGE_EXPRESSION)
    except Exception:  # noqa: BLE001
        return []
    return [
        StorageWrite(
            kind=item.get("kind", ""),
            key=item.get("key", ""),
            origin=item.get("origin", ""),
        )
        for item in raw or []
    ]


async def _read_cookies(context, site_domain: str) -> List[Cookie]:
    try:
        raw = await context.cookies()
    except Exception:  # noqa: BLE001
        return []
    out: List[Cookie] = []
    for c in raw:
        domain = (c.get("domain") or "").lstrip(".")
        out.append(
            Cookie(
                name=c.get("name", ""),
                domain=domain,
                is_third_party=is_third_party(domain, site_domain),
                http_only=bool(c.get("httpOnly")),
                secure=bool(c.get("secure")),
                same_site=str(c.get("sameSite") or ""),
                session=c.get("expires", -1) in (-1, None),
            )
        )
    return out


def _normalise_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url
