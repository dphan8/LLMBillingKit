# LLMBillingKit

Know your margin on every LLM call. One line of code. Zero infrastructure.

## Install

```
pip install llmbillingkit
```

## Usage

```python
from openai import OpenAI
from llmbillingkit import track

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)

track(response, charged=0.05, customer="user_123")
```

Works with OpenAI, LiteLLM, and any library that returns OpenAI-compatible response objects.

## See your margins

```
$ llmbilling report

Customer     Requests   Revenue     Cost     Margin   Margin %
───────────────────────────────────────────────────────────────
acme_corp          84    $4.20    $0.62     $3.58     85.2%
user_free         312    $0.00    $1.87    -$1.87       —
pro_tier           47    $2.35    $0.19     $2.16     91.9%
trial_user         23    $0.46    $0.31     $0.15     32.6%
───────────────────────────────────────────────────────────────
TOTAL             466    $7.01    $2.99     $4.02     57.3%
```

```
$ llmbilling models

Model                        Requests   Avg Rev   Avg Cost   Avg Margin   Margin %
──────────────────────────────────────────────────────────────────────────────────
gpt-4o                            112    $0.05    $0.0094      $0.041      81.2%
gpt-4o-mini                       289    $0.01    $0.0003      $0.010      97.0%
claude-3-5-sonnet-20241022         65    $0.03    $0.0120      $0.018      60.0%
──────────────────────────────────────────────────────────────────────────────────
```

```
$ llmbilling export --format csv > usage.csv
```

## How it works

`track()` extracts token counts and model name from the response object, looks up the provider's per-token cost from a bundled pricing table, and calculates:

```
margin = price_you_charged - (prompt_tokens × input_cost + completion_tokens × output_cost)
```

Everything is stored locally in SQLite at `~/.llmbillingkit/usage.db`. No servers, no API calls, no data leaves your machine.

## Supported models

**OpenAI:** gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, o1-mini, o3-mini, o4-mini

**Anthropic:** claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022, claude-3-haiku-20240307

**Google:** gemini-2.0-flash, gemini-2.5-pro, gemini-2.5-flash

**Mistral:** mistral-large-latest, mistral-small-latest

Unknown models are still tracked — you'll see revenue and token counts, just not cost or margin. A warning tells you which model is missing.

## CLI reference

| Command | Description |
|---------|-------------|
| `llmbilling report` | Margin breakdown by customer |
| `llmbilling report --days 7` | Last 7 days only |
| `llmbilling report --model gpt-4o` | Filter to one model |
| `llmbilling models` | Margin breakdown by model |
| `llmbilling export` | Dump raw data as CSV |
| `llmbilling export --format json` | Dump as JSON |

## Contributing

Model pricing changes frequently. PRs updating `costs.json` are always welcome — it's the single most valuable contribution you can make.

## License

MIT
