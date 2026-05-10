# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

## [0.1.1] - 2026-05-10

### Added

- Open-source project governance files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`).
- GitHub Actions workflows for test automation and PyPI publishing.
- Example script(s) under `examples/`.
- `llmbilling add` CLI command for recording usage events without writing Python.
- `llmbilling update` CLI command for editing the customer or charged amount on
  an existing record (margin is recomputed automatically when `--charged`
  changes).
- `track_usage()` public helper for tracking from raw fields, and a
  `TrackingError` exception with a keyword-only `raise_errors=True` option on
  `track()` / `track_usage()` for clearer debugging.

### Changed

- Expanded README with architecture, CLI output examples, limitations, and roadmap.
- Improved repository hygiene and launch readiness documentation.
- `update_event()` no longer recomputes `margin` on customer-only updates, and
  short-circuits when neither `--customer` nor `--charged` is provided.
- CLI `add` / `update` reject negative token counts and charged amounts at the
  argument boundary, and `add` refuses a duplicate `--request-id` instead of
  silently no-oping the underlying `INSERT OR IGNORE`.

### Fixed

- Pricing lookup now resolves a small allowlist of verified-equivalent dated
  provider snapshots (e.g. `gpt-4o-mini-2024-07-18` → `gpt-4o-mini`) so
  `track()` no longer silently returns `None` for OpenAI responses that include
  a dated model ID. Snapshots not in the allowlist still return `None` rather
  than silently inheriting a different model's price.
- Added `from __future__ import annotations` so the project's declared
  `requires-python = ">=3.9"` actually works at runtime (PEP 604 unions in
  module/function annotations no longer break import on Python 3.9).

## [0.1.0] - 2026-03-25

### Added

- Initial LLMBillingKit release.
- Local tracking via `track()` with bundled model pricing lookups.
- SQLite-backed event storage.
- CLI reporting commands (`report`, `models`, `export`).
