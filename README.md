# leakwatch

[![CI](https://github.com/gazzycodes/leakwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gazzycodes/leakwatch/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Scan any website and see — live, in your terminal — every tracker, data broker,
fingerprinting trick, and session recorder watching you, which companies they
report to, and how the site's own security headers hold up.** One brutally simple
verdict on top, full forensics underneath.

```
leakwatch nytimes.com
```

> 🔴 59 trackers · leaks to 8 data brokers · fingerprints you · 12 fired before consent — 100/100 (F)

![demo](docs/demo.gif)

## Why it's different

Most privacy checkers are consumer web apps that hand you a wall of hostnames.
leakwatch is built for engineers and security folks: it loads the page in a real
browser, **defeats the consent wall**, rolls dozens of tracker domains up to the
handful of companies they belong to, and gives you a verdict — then lets you
script it, gate CI on it, or rank a whole category of sites.

- **Dumb surface.** Run it with a URL. A live dashboard fills in. The top line is
  the whole story for most people.
- **Advanced engine.** Every request, cookie, storage write, and fingerprinting
  call is captured, classified, scored, and attributed to a parent company.

## What it does

- **Two-phase consent scan.** Loads as a fresh visitor, then defeats the consent
  wall — including consent managers in cross-origin iframes (OneTrust, Sourcepoint/
  TCF, Cookiebot, Quantcast, Didomi, TrustArc, Usercentrics, Osano, CookieYes,
  Google, Complianz) by their language-independent IDs, with a multilingual text
  fallback — and records the trackers that only fire *after* acceptance.
- **Before/after-consent headline.** "18 trackers fired before you consented."
- **CMP detection.** Even when a button can't be clicked, the IAB `__tcfapi`/`__gpp`
  APIs and known globals reveal the gate, so a consent-walled site is never
  reported as clean.
- **Company rollup.** ~200 curated trackers attributed to parent entities and
  jurisdictions — Google, Meta, Oracle, LiveRamp, The Trade Desk, and the rest.
- **Data brokers & session recorders** called out explicitly ("records your
  screen" — Hotjar, FullStory, Clarity, …).
- **Fingerprinting** via canvas, WebGL, AudioContext, font enumeration, and
  navigator probes.
- **Security-headers audit.** Grades the page on HSTS, CSP, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
- **Block detection.** Flags Cloudflare-style challenge walls, CAPTCHAs, and
  4xx/5xx instead of pretending a site is clean.

## Install

```bash
pip install leakwatch            # once published
# or, from source:
pip install -e .
playwright install chromium      # one-time: leakwatch drives a real browser
```

leakwatch ships a browser engine (Playwright/Chromium), so it is a heavier install
than a pure-Python linter — expected for this class of tool. If the `leakwatch`
command isn't on your PATH, `python -m leakwatch ...` always works.

## Usage

```bash
leakwatch example.com              # live dashboard
leakwatch example.com --show       # run with a visible browser (watch the scan)
leakwatch example.com --no-tui     # plain-text report
leakwatch example.com --json       # machine-readable output

leakwatch batch sites.txt                  # ranked leaderboard scorecard
leakwatch batch sites.txt --format markdown --out report.md

leakwatch diff example.com -b baseline.json    # CI gate: exit non-zero on new trackers
leakwatch diff example.com --save-baseline baseline.json

leakwatch login example.com -o auth.json       # sign in by hand, save the session
leakwatch example.com --storage-state auth.json
```

### Leaderboard mode — the viral artifact

Feed it a list of sites; it ranks them by how badly they leak, as a shareable
scorecard in text, Markdown, or JSON:

```bash
leakwatch batch news-sites.txt --format markdown
```

### CI mode — a tracker linter for your own site

Save a baseline, then fail the build when a new third party appears between
commits — the same idea as a static-analysis linter, for trackers:

```bash
leakwatch diff https://your-site.com -b baseline.json   # exit 1 on new trackers
```

### Auditing pages behind a login

By default leakwatch scans as a fresh anonymous visitor — exactly what you want,
because that's what a first-time visitor leaks. To audit your *own* authenticated
pages, `leakwatch login` opens a visible browser, you sign in by hand, and only
the resulting session blob is saved locally. **leakwatch never sees or stores a
password.** Batch/leaderboard mode is anonymous-only by design.

## How the score works

The leakage score runs 0 (clean) to 100 (worst): a small weight per tracker and
company, with heavier penalties for data brokers, session recorders,
fingerprinting, and trackers that slip through a consent gate. It maps to a grade
from A to F.

## Privacy & scope

leakwatch records **only** the tracking surface — network metadata, cookies,
storage keys, fingerprinting call counts, and response headers. It never
downloads, stores, renders, or serves page content, images, or media. It only
loads pages a normal visitor would, and batch scans are public-only.

## Development

```bash
git clone https://github.com/gazzycodes/leakwatch
cd leakwatch
pip install -e ".[dev]"
playwright install chromium

PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
```

The classification, scoring, security-header, and reporting layers have no browser
dependency, so the test suite runs fast and offline. The dataset under
`src/leakwatch/data` is a curated, license-safe set; `update-data` can fetch
fuller external lists later at your discretion.

## License

MIT — see [LICENSE](LICENSE).
