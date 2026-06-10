# leakwatch

[![CI](https://github.com/gazzycodes/leakwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gazzycodes/leakwatch/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/leakwatch.svg)](https://pypi.org/project/leakwatch/)

**Scan any website and see — live, in your terminal — every tracker, data broker,
fingerprinting trick, and session recorder watching you.** One brutally simple
verdict on top, full forensics underneath.

```
leakwatch nytimes.com
```

> 🔴 41 trackers · leaks to 3 data brokers · records your screen · fingerprints you 4 ways

![demo](docs/demo.gif)

## Why

Most "privacy checkers" hand you a wall of hostnames. leakwatch does the opposite:
it loads the page in a real browser, watches everything it does, rolls 50 tracker
domains up to the five companies they actually belong to, and tells you in one line
how exposed you are — then lets you drill into the details if you want them.

It is dumb to use and serious underneath:

- **Dumb surface.** Run it with a URL. A live dashboard fills in. The top line is
  the whole story for most people. No config, no manual.
- **Advanced engine.** Every request, cookie, storage write, and fingerprinting
  call is captured, classified, scored, and attributed to a parent company.

## What it detects

- Third-party requests classified against well-known tracker datasets, grouped by
  parent company and jurisdiction.
- **Data brokers** and **session recorders** (Hotjar, FullStory, Clarity, …) called
  out explicitly — "this site was recording your screen."
- **Fingerprinting** via canvas, WebGL, AudioContext, font enumeration, and
  high-entropy navigator probes.
- **Pre-consent tracking** — trackers that fire *before* you click "Accept."
- Cookies (first vs third party) and local/session storage writes.

## Install

```bash
pip install leakwatch
playwright install chromium   # one-time: leakwatch drives a real browser
```

leakwatch ships a browser engine (Playwright/Chromium), so it is a heavier install
than a pure-Python linter — that is expected for this class of tool.

## Usage

```bash
leakwatch example.com              # live dashboard for one site
leakwatch example.com --no-tui     # plain-text report
leakwatch example.com --json       # machine-readable output

leakwatch batch sites.txt                  # ranked leaderboard scorecard
leakwatch batch sites.txt --format markdown --out report.md

leakwatch diff example.com -b baseline.json    # CI gate: exit non-zero on new trackers
leakwatch diff example.com --save-baseline baseline.json

leakwatch login example.com -o auth.json       # sign in by hand, save the session
leakwatch example.com --storage-state auth.json
```

### Leaderboard mode

Feed it a list of sites and it ranks them by how badly they leak — a shareable
scorecard in text, Markdown, or JSON:

```bash
leakwatch batch news-sites.txt --format markdown
```

### CI mode

Save a baseline for your own site, then fail the build when a new third party
sneaks in between commits — the same "linter in your pipeline" idea, for trackers:

```bash
leakwatch diff https://your-site.com -b baseline.json   # exit 1 if new trackers appear
```

### Auditing pages behind a login

By default leakwatch scans as a fresh anonymous visitor — which is exactly what you
want, because that is what a first-time visitor leaks. For auditing your *own*
authenticated pages, `leakwatch login` opens a visible browser, you sign in by hand,
and only the resulting session blob is saved locally. **leakwatch never sees or
stores a password.** Batch/leaderboard mode is anonymous-only by design.

## How the score works

The leakage score runs 0 (clean) to 100 (worst): a small weight per tracker and
company, with heavier penalties for the things that matter — data brokers, session
recorders, fingerprinting, and trackers that fire before consent. It maps to a grade
from A to F.

## Privacy & scope

leakwatch records **only** the tracking surface — network metadata, cookies, storage
keys, and fingerprinting call counts. It never downloads, stores, renders, or serves
page content, images, or media. It only loads pages a normal visitor would, and
batch scans are rate-limited and public-only.

## Development

```bash
git clone https://github.com/gazzycodes/leakwatch
cd leakwatch
pip install -e ".[dev]"
playwright install chromium

PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
```

The classification, scoring, and reporting layers have no browser dependency, so the
test suite runs fast and offline. The dataset under `src/leakwatch/data` is a curated
seed; a full DuckDuckGo Tracker Radar refresh is planned.

## License

MIT — see [LICENSE](LICENSE).
