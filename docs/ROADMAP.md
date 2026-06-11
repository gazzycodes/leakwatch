# leakwatch — roadmap & status

Living document. Tracks what is shipped, what is in flight, and the decisions
behind the design so the project stays coherent as it grows.

## Current release: v0.6.1

A terminal-native website privacy scanner: drive headless Chromium, record the
full tracking surface, classify it, and present a one-line verdict over deep
forensics. Built for engineers — scriptable, CI-friendly, local.

## Shipped

- Anonymous scan engine (Playwright): requests, cookies, storage keys,
  fingerprinting call counts. Bounded load wait so scans stay fast.
- Classification against a curated tracker dataset; rollup to parent companies
  with jurisdiction; 0–100 leakage score and A–F grade.
- Pre-consent detection (third parties firing before any consent click).
- Session-replay detection (Hotjar, FullStory, Clarity, …).
- Fingerprinting detection (canvas, WebGL, AudioContext, fonts, navigator).
- Live Textual dashboard: verdict bar + score gauge, colour-coded streaming
  request feed, company rollup, completion cue, in-app rescan.
- Modes: single scan, `batch` leaderboard (text/markdown/json), `diff` CI gate,
  `--json`, `--no-tui`, opt-in `--login` / `login` (bring-your-own-session;
  never stores a password), `--storage-state`.
- Two-phase consent scan with cross-origin CMP handling; anti-bot context
  (real UA/viewport/locale, no webdriver tell); block detection for
  challenge walls and 4xx/5xx; consent/HTTP status surfaced everywhere.
- Tests (offline, logic layers), GitHub Actions CI, packaging, README.

## Next (visual depth — dashboard shows less than the engine captures)

- Fingerprinting panel in the TUI.
- Cookies & storage panel (populates on nearly every site).
- Data-flow map: domains -> companies -> countries.
- Row drill-down: select a company to expand its domains / cookies.

## Backlog

- Expand the tracker dataset (bigger curated set, then wire `update-data` to pull
  the full DuckDuckGo Tracker Radar).
- `--pages N`: shallow same-origin crawl (homepage + a deep page) for coverage.
- Richer scorecard export (HTML/PNG card for sharing).
- Audience polish: enterprise (CI gates, self-audit), solo engineers, security.

## Design decisions

- **Name:** leakwatch (one identical name on GitHub, CLI, and PyPI).
- **Login:** in v1 as opt-in bring-your-own-session; batch/leaderboard stays
  anonymous/public-only.
- **Dataset:** ship a curated seed in v1; full Tracker Radar refresh later.
- **Ethics:** record only tracking metadata — never page content, images, or
  media. Only load pages a normal visitor would; rate-limit batch scans.

## Positioning

Prior art is consumer-facing (Blacklight, Webbkoll, webxray) or browser blockers
(uBlock, Privacy Badger, Ghostery). leakwatch's wedge is the engineer-shaped one:
a scriptable terminal scanner with `--json`, a CI `diff` gate ("tracker linter"),
and a batch leaderboard — local, account-free, metadata-only.

## Field notes (observed during testing)

- **Consent walls hide the real stack.** Sites with a CMP (e.g. The Guardian /
  Sourcepoint TCF iframe) gate ads and trackers behind "Accept." Our current
  auto-accept misses iframe-based CMPs, so such sites under-report. Priority:
  robust consent handling (incl. cross-origin CMP iframes), which also makes the
  before/after-consent comparison the headline feature.
- **First-party-owned CDNs read as third-party.** A site's own asset domain on a
  different registrable domain (e.g. guim.co.uk for theguardian.com) is flagged
  third-party. Add a "first-party CDN / same-owner" heuristic so the verdict is
  not diluted by a site's own infrastructure.
- **Late-loading trackers.** Ad/measurement scripts often fire seconds after load
  (and after consent). The bounded load wait helps; revisit timing alongside
  consent handling and an optional networkidle pass.
- **Dataset coverage.** The v0.1.0 seed (~80 trackers) means lighter/own-CDN-heavy
  sites match little. Expanding the dataset is a top backlog item.
