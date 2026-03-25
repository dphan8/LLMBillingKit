# Contributing to LLMBillingKit

Thanks for your interest in contributing.

## Ways to contribute

- Report bugs and pricing inaccuracies.
- Improve docs and examples.
- Add or update model pricing data in `LLMBillingKit/costs.json`.
- Add tests for bug fixes and new behavior.

## Reporting issues

When opening an issue, include:

- What you expected to happen.
- What actually happened.
- Steps to reproduce.
- Python version and OS.
- Relevant logs, traceback, and command output.

Use a minimal reproducible example whenever possible.

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Make focused changes with clear commit messages.
3. Add or update tests for behavior changes.
4. Run tests locally before submitting.
5. Open a PR with:
   - Summary of changes
   - Motivation/context
   - Test evidence (commands + results)

Small, targeted PRs are preferred over large multi-topic changes.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests locally

Unit tests:

```bash
pytest LLMBillingKit/tests -q
```

End-to-end smoke test (requires API key):

```bash
OPENAI_API_KEY=your_key_here python test_e2e.py
```

## Coding conventions

- Follow existing style and keep modules small.
- Use clear names and straightforward control flow.
- Add type hints where practical.
- Keep behavior backward compatible unless discussed.
- Avoid broad refactors in feature/fix PRs.
- Add docstrings for non-trivial public functions.

## Pricing data updates

If you update `LLMBillingKit/costs.json`:

- Cite sources in `PRICING_VERIFICATION.md`.
- Keep values in per-token units expected by runtime code.
- Add/adjust tests that exercise affected models.

## Release notes

User-facing changes should include a short entry in `CHANGELOG.md` under `Unreleased`.

By participating, you agree to follow the project Code of Conduct.
