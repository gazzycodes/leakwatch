"""The scan engine: drive headless Chromium and record the tracking surface.

Only network metadata, cookies, storage keys, and fingerprinting call counts are
collected. The engine never downloads, stores, renders, or serves page content,
images, or media — by design, so a sensitive site in a batch only ever yields
tracker metadata.

The scan runs in two phases so the before/after-consent comparison is real:

1.  Load the page as a fresh anonymous visitor and record everything that fires.
2.  Defeat the consent wall (including consent managers rendered in cross-origin
    iframes) and record the trackers that only appear *after* acceptance.

Consent handling targets the ~dozen consent-management platforms that run the web
by their stable, language-independent IDs — not individual sites — with a
multilingual text fallback, and detects the CMP via standard APIs so a gated site
is never reported as clean even when the button cannot be clicked.

Playwright is imported lazily inside the functions so the rest of the package
(classification, scoring, reporting) imports and tests without a browser.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, List, Optional, Tuple

from leakwatch.classify import (
    classify_hosts,
    host_from_url,
    is_third_party,
    registrable_domain,
)
from leakwatch.instrument import (
    CMP_DETECT_EXPRESSION,
    INIT_SCRIPT,
    REPORT_EXPRESSION,
    STORAGE_EXPRESSION,
)
from leakwatch.model import (
    CONSENT_ACCEPTED,
    CONSENT_NONE,
    CONSENT_PRESENT,
    CONSENT_SKIPPED,
    Cookie,
    Fingerprint,
    Request,
    ScanResult,
    StorageWrite,
)
from leakwatch.score import compute_verdict

RequestCallback = Optional[Callable[[Request], None]]

# Present as a normal, current desktop Chrome so sites do not serve a stripped
# or challenge page to an obvious bot.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
_VIEWPORT = {"width": 1366, "height": 768}
_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]

# Hide the most obvious automation tell before any page script runs.
_STEALTH_SCRIPT = """
(() => {
  try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); }
  catch (e) {}
})();
"""

# Consent managers, by name, with the selector that accepts everything. Searched
# across the main frame and every child frame (many CMPs render in an iframe).
# These IDs/classes are framework-level and identical across every language.
_CMP_SELECTORS: List[Tuple[str, str]] = [
    ("OneTrust", "#onetrust-accept-btn-handler"),
    ("OneTrust", "#accept-recommended-btn-handler"),
    ("Cookiebot", "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"),
    ("Cookiebot", "#CybotCookiebotDialogBodyButtonAccept"),
    ("Quantcast", ".qc-cmp2-summary-buttons button[mode='primary']"),
    ("Didomi", "#didomi-notice-agree-button"),
    ("TrustArc", "#truste-consent-button"),
    ("Osano", ".osano-cm-accept-all"),
    ("Usercentrics", "button[data-testid='uc-accept-all-button']"),
    ("CookieYes", ".cky-btn-accept"),
    ("Sourcepoint", "button[title='Accept all']"),
    ("Sourcepoint", "button[title='Accept All']"),
    ("Google", ".fc-cta-consent"),
    ("Complianz", ".cmplz-accept"),
    ("Generic", "button[aria-label*='accept all' i]"),
    ("Generic", "button[aria-label*='accept' i]"),
    ("Generic", "[data-testid*='accept-all' i]"),
]

# Accept-everything button labels across common web languages (matched
# case-insensitively, substring). Used only as a fallback for custom banners
# that are not one of the known CMP frameworks above.
_CONSENT_LABELS = [
    # English
    "Accept all", "Accept all cookies", "Allow all", "Allow all cookies",
    "I accept", "I agree", "Agree and close", "Yes, I agree",
    "Accept and continue", "Accept cookies", "Allow cookies", "Got it",
    # German
    "Alle akzeptieren", "Alle zulassen", "Alle Cookies akzeptieren",
    "Zustimmen", "Einverstanden",
    # French
    "Tout accepter", "Tout autoriser", "J'accepte", "Accepter et continuer",
    "Tout accepter et fermer",
    # Spanish
    "Aceptar todo", "Aceptar todas", "Permitir todo", "Acepto",
    # Italian
    "Accetta tutto", "Accetta tutti", "Acconsento",
    # Portuguese
    "Aceitar tudo", "Aceitar todos", "Aceito",
    # Dutch
    "Alles accepteren", "Alles toestaan", "Akkoord",
    # Polish
    "Zaakceptuj wszystko", "Akceptuje",
    # Russian
    "Принять все", "Принять и закрыть",
]

# Page-title markers that indicate a bot/challenge wall (metadata only).
_BLOCK_TITLE_MARKERS = [
    "just a moment",
    "attention required",
    "access denied",
    "are you a human",
    "are you a robot",
    "verifying you are human",
    "captcha",
    "request blocked",
]
_BLOCK_STATUSES = {401, 403, 407, 429, 503}


async def scan_async(
    url: str,
    *,
    timeout_ms: int = 30000,
    settle_ms: int = 1500,
    post_consent_ms: int = 3000,
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
        browser = await pw.chromium.launch(headless=not headed, args=_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport=_VIEWPORT,
            locale="en-US",
            timezone_id="America/New_York",
            storage_state=storage_state if storage_state else None,
        )
        await context.add_init_script(_STEALTH_SCRIPT)
        await context.add_init_script(INIT_SCRIPT)
        page = await context.new_page()
        page.on("request", handle_request)

        # --- Phase 1: load as a fresh anonymous visitor -----------------------
        try:
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=timeout_ms
            )
            if response is not None:
                result.status_code = response.status
        except Exception as exc:  # noqa: BLE001 - report, don't crash the scan
            result.error = str(exc).splitlines()[0]
        try:
            await page.wait_for_load_state("load", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(settle_ms)

        # --- Block / bot-wall detection (metadata only) -----------------------
        title = ""
        try:
            title = await page.title()
        except Exception:  # noqa: BLE001
            pass
        blocked, reason = _looks_blocked(result.status_code, title)
        result.blocked = blocked
        result.blocked_reason = reason

        # --- Phase 2: defeat the consent wall and record the surge ------------
        cmp_present, cmp_detected = await _detect_cmp(page)
        if not detect_consent:
            result.consent_state = CONSENT_SKIPPED
        elif not blocked:
            clicked, cmp_clicked = await _accept_consent(page)
            if clicked:
                consented["value"] = True
                result.consent_state = CONSENT_ACCEPTED
                result.consent_cmp = cmp_detected or cmp_clicked
                await page.wait_for_timeout(post_consent_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
            elif cmp_present:
                result.consent_state = CONSENT_PRESENT
                result.consent_cmp = cmp_detected
            else:
                result.consent_state = CONSENT_NONE

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
        browser = await pw.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = await browser.new_context(user_agent=_USER_AGENT, viewport=_VIEWPORT)
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


async def _detect_cmp(page) -> Tuple[bool, str]:
    """Detect a consent platform via standard APIs / globals. (present, name)."""

    try:
        info = await page.evaluate(CMP_DETECT_EXPRESSION)
    except Exception:  # noqa: BLE001
        return False, ""
    if isinstance(info, dict) and info.get("present"):
        return True, str(info.get("cmp") or "consent manager")
    return False, ""


async def _accept_consent(page) -> Tuple[bool, str]:
    """Try to accept the consent banner in any frame. Returns (clicked, cmp)."""

    for frame in page.frames:
        for cmp_name, selector in _CMP_SELECTORS:
            try:
                locator = frame.locator(selector)
                if await locator.count() == 0:
                    continue
                first = locator.first
                if await first.is_visible():
                    await first.click(timeout=1500)
                    return True, cmp_name
            except Exception:  # noqa: BLE001 - frame may detach; keep trying
                continue
    for frame in page.frames:
        for label in _CONSENT_LABELS:
            try:
                button = frame.get_by_role("button", name=label, exact=False)
                if await button.count() == 0:
                    continue
                first = button.first
                if await first.is_visible():
                    await first.click(timeout=1500)
                    return True, "Generic"
            except Exception:  # noqa: BLE001
                continue
    return False, ""


def _looks_blocked(status: Optional[int], title: str) -> Tuple[bool, str]:
    if status in _BLOCK_STATUSES:
        return True, f"server returned HTTP {status}"
    low = (title or "").lower()
    for marker in _BLOCK_TITLE_MARKERS:
        if marker in low:
            return True, f"bot/challenge wall ('{title.strip()}')"
    return False, ""


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
