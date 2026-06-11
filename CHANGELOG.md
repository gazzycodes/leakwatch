# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-06-11

### Added

- Security-headers audit: captures the main response's HSTS, CSP, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, and Permissions-Policy, grades the
  posture A–F, and surfaces it in the text report, JSON, and a dashboard panel.
- README overhauled to document the full current feature set (two-phase consent,
  CMP/anti-bot/block detection, ~200-tracker dataset, dashboard panels).

## [0.3.0] - 2026-06-11

### Added

- Expanded the curated tracker dataset to ~200 entries across ad-tech (SSPs,
  DSPs, exchanges, verification), analytics, tag managers, CDPs, session
  recorders, data brokers, social, CDNs, and consent vendors — so far more third
  parties are named and attributed instead of shown as generic "third-party".
- Dashboard panels: live Fingerprinting, Cookies & Storage, and category
  breakdown panels summarising what the engine captures, beneath the request feed
  and company rollup.

## [0.2.0] - 2026-06-11

### Added

- Two-phase consent scan: load as a fresh visitor, then defeat the consent wall
  and record the trackers that only fire after acceptance. Handles consent
  managers rendered in cross-origin iframes (OneTrust, Sourcepoint/TCF,
  Cookiebot, Quantcast, Didomi, TrustArc, Usercentrics, Osano, Google, Complianz)
  and generic accept buttons.
- CMP detection via standard APIs (IAB TCF/GPP, `__uspapi`) and known globals,
  so a consent-gated site is reported as such even when the button cannot be
  clicked — never silently shown as clean (`banner present` state).
- Multilingual accept-button fallback (German, French, Spanish, Italian,
  Portuguese, Dutch, Polish, Russian) for custom, non-CMP banners.
- Anti-bot hardening: realistic user agent, viewport, locale, and timezone, plus
  removal of the `navigator.webdriver` automation tell, so sites serve their real
  page instead of a stripped or challenge version.
- Block detection: flags Cloudflare-style challenge walls, CAPTCHAs, and 401/403/
  429/503 responses instead of reporting a falsely clean site.
- `--show` flag to run with a visible browser window and watch a scan.
- Consent outcome (`accepted` / `no banner` / `skipped`), HTTP status, and block
  reason surfaced in the dashboard, text report, and JSON output.

### Changed

- "Fired before consent" is now only claimed when a banner was actually present
  and accepted, so the headline can no longer be misleading.

## [0.1.0] - 2026-06-10

### Added

- Initial release.
- Headless-Chromium scan engine (Playwright) capturing every request, cookie,
  storage write, and fingerprinting call a page makes.
- Third-party classification against a bundled tracker dataset with rollup to
  parent companies and a 0–100 leakage score.
- Detection of canvas, WebGL, AudioContext, font-enumeration, and navigator
  fingerprinting techniques via an injected instrumentation script.
- Before/after-consent comparison: trackers that fire before any consent click.
- Session-replay detection (Hotjar, FullStory, and similar recorders).
- Live Textual dashboard: verdict bar, streaming request feed, company rollup.
- `batch` leaderboard mode with exportable scorecard (text / markdown / JSON).
- `diff` mode for CI: fail the build when new third parties appear.
- Opt-in `--login` bring-your-own-session scanning (saved `storageState`, never a
  password) for auditing your own authenticated pages.
