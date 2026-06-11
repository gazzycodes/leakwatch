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

## Why I built it

Privacy tools tell you a site is "bad" without showing the receipts, and security
recon usually means digging through browser devtools by hand. leakwatch does both
in one pass and makes the result *legible*: it loads the page in a real browser,
defeats the consent wall, and turns the chaos of fifty tracker domains into a
plain answer — who is watching you here, how badly, and what data leaves the page.

It's built for people who want the truth quickly: engineers auditing their own
sites, security folks profiling a target's third-party surface, privacy
researchers ranking a whole category, and anyone who just wants to point a tool at
a URL and get a verdict.

## Dumb surface, advanced engine

- **Dumb to use.** Run it with a URL. A live dashboard fills in. The top line is
  the whole story for most people. No config, no manual.
- **Advanced underneath.** Every request, cookie, storage write, and fingerprinting
  call is captured, classified, scored, and attributed to a parent company.

## What it does

- **Two-phase consent scan.** Loads as a fresh visitor, then defeats the consent
  wall — including consent managers in cross-origin iframes (OneTrust, Sourcepoint/
  TCF, Cookiebot, Quantcast, Didomi, TrustArc, Usercentrics, Osano, CookieYes,
  Google, Complianz) by their language-independent IDs, with a multilingual text
  fallback — and records the trackers that only fire *after* acceptance.
- **Before/after-consent headline.** "18 trackers fired before you consented" —
  the legally interesting part, and only claimed when a banner truly existed.
- **CMP detection.** Even when a button can't be clicked, the IAB `__tcfapi`/`__gpp`
  APIs and known globals reveal the gate, so a consent-walled site is never falsely
  reported as clean.
- **Company rollup.** ~200 curated trackers attributed to parent entities and
  jurisdictions — Google, Meta, Oracle, LiveRamp, The Trade Desk, and the rest.
- **Data brokers & session recorders** called out explicitly ("records your
  screen" — Hotjar, FullStory, Clarity, …).
- **Fingerprinting** via canvas, WebGL, AudioContext, font enumeration, and
  navigator probes.
- **Security-headers audit.** Grades the page A–F on HSTS, CSP, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
- **Block detection.** Flags Cloudflare-style challenge walls, CAPTCHAs, and 4xx/5xx
  instead of pretending a site is clean.
- **Anti-bot context.** Realistic user agent, viewport, locale, and no `webdriver`
  tell, so sites serve their real page.

## Install

```bash
pip install leakwatch            # once published
# or, from source:
pip install -e .
playwright install chromium      # one-time: leakwatch drives a real browser
```

leakwatch ships a browser engine (Playwright/Chromium), so it's a heavier install
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

In the dashboard: type a domain in the top bar and press **Enter** (or `n` to focus
it) to scan a new site without quitting · `r` re-runs the current site · `q` quits.

### Leaderboard mode — the shareable artifact

Give it a list of sites (one per line); it ranks them by leakage into a scorecard
in text, Markdown, or JSON:

```bash
leakwatch batch examples/news-sites.txt --format markdown --out leaderboard.md
```

Real run across 15 major news sites (top of the list shown):

| # | Site | Leakage | Trackers | Brokers | Records screen | Fingerprinting |
|--:|------|:--------|--------:|--------:|:--------------:|:--------------:|
| 1 | foxnews.com | 🔴 100 (F) | 116 | 11 | no | yes |
| 2 | usatoday.com | 🔴 100 (F) | 116 | 11 | no | yes |
| 3 | forbes.com | 🔴 100 (F) | 113 | 11 | no | yes |
| 4 | thesun.co.uk | 🔴 100 (F) | 113 | 14 | no | yes |
| 5 | businessinsider.com | 🔴 100 (F) | 109 | 19 | no | yes |
| 6 | cnn.com | 🔴 100 (F) | 108 | 13 | no | yes |
| 7 | buzzfeed.com | 🔴 100 (F) | 96 | 15 | no | yes |
| 8 | theguardian.com | 🔴 100 (F) | 81 | 12 | no | yes |
| 9 | nbcnews.com | 🔴 100 (F) | 58 | 5 | no | yes |
| 10 | cnbc.com | 🔴 100 (F) | 48 | 5 | no | yes |

*Sites behind hard bot-walls or unaccepted consent gates (e.g. Reuters, Bloomberg)
are flagged in a `Note` column as under-measured, never ranked as clean.*

### CI mode — a tracker linter for your own site

Save a baseline, then fail the build when a new third party appears between commits:

```bash
leakwatch diff https://your-site.com -b baseline.json   # exit 1 on new trackers
```

### Auditing pages behind a login

By default leakwatch scans as a fresh anonymous visitor — exactly what you want,
because that's what a first-time visitor leaks. To audit your *own* authenticated
pages, `leakwatch login` opens a visible browser, you sign in by hand, and only the
resulting session blob is saved locally. **leakwatch never sees or stores a
password.** Batch/leaderboard mode is anonymous-only by design.

## How the score works

The leakage score runs 0 (clean) to 100 (worst): a small weight per tracker and
company, with heavier penalties for data brokers, session recorders, fingerprinting,
and trackers that slip through a consent gate. It maps to a grade from A to F.

## Privacy & scope

leakwatch records **only** the tracking surface — network metadata, cookies, storage
keys, fingerprinting call counts, and response headers. It never downloads, stores,
renders, or serves page content, images, or media. It only loads pages a normal
visitor would, and batch scans are public-only.

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
`src/leakwatch/data` is a curated, license-safe set; `update-data` can fetch fuller
external lists later at your discretion.

## License

MIT — see [LICENSE](LICENSE).
