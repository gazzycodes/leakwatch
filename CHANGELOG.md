# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

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
