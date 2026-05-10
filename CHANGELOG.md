# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Open-source project governance files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`).
- GitHub Actions workflows for test automation and PyPI publishing.
- Example script(s) under `examples/`.
- `llmbilling add` CLI command for recording usage events without writing Python.
- `llmbilling update` CLI command for editing the customer or charged amount on
  an existing record (margin is recomputed automatically when `--charged`
  changes).
- `track_usage()` public helper for tracking from raw fields, and a
  `TrackingError` exception with a `raise_errors=True` option on `track()` /
  `track_usage()` for clearer debugging.

### Changed

- Expanded README with architecture, CLI output examples, limitations, and roadmap.
- Improved repository hygiene and launch readiness documentation.

### Fixed

- Pricing lookup now resolves provider-dated model IDs such as
  `gpt-4o-mini-2024-07-18` to their base pricing key, so `track()` no longer
  silently returns `None` for OpenAI responses that include a dated model ID.

## [0.1.0] - 2026-03-25

### Added

- Initial LLMBillingKit release.
- Local tracking via `track()` with bundled model pricing lookups.
- SQLite-backed event storage.
- CLI reporting commands (`report`, `models`, `export`).
