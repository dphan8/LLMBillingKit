# LLMBillingKit

Track net margin on every LLM API call. Local-first, zero-config.

## Install

```bash
pip install LLMBillingKit
```

## Quick Start

```python
import LLMBillingKit

# After any OpenAI / Anthropic API call:
result = LLMBillingKit.track(response, charged=0.03, customer="acme")
print(result["margin"])  # revenue minus actual LLM cost
```

`track()` extracts model, token counts, and request ID from the response object,
looks up per-token costs, computes actual cost and margin, and logs everything to
a local SQLite database (`~/.LLMBillingKit/usage.db`).

## CLI

```bash
llmbilling report              # margin by customer
llmbilling report --days 7     # last 7 days
llmbilling models              # margin by model
llmbilling export              # CSV to stdout
llmbilling export --format json
```

## Supported Models

OpenAI (gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, o1, o1-mini, o3, o3-mini, o4-mini),
Anthropic (claude-sonnet-4-20250514, claude-3-5-sonnet, claude-3-5-haiku, claude-3-haiku),
Google (gemini-2.0-flash, gemini-2.5-pro, gemini-2.5-flash),
Mistral (mistral-large-latest, mistral-small-latest).

## License

MIT
