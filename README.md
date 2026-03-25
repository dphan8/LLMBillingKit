# LLMBillingKit

LLMBillingKit helps you measure real profit per LLM call with one line of code and no external infrastructure.

## The problem this solves

When you charge end users for AI features, your real margin can drift quickly because token pricing changes often, model mix shifts over time, and provider-specific pricing rules are easy to miss. Most teams either track only revenue or build ad-hoc spreadsheets that do not stay accurate.

LLMBillingKit gives you a local, auditable ledger of what you charged and what each request likely cost, so you can answer: "Are we making money on this feature?" in seconds.

## Why local SQLite and zero infrastructure are deliberate

- Your usage and customer billing telemetry stays on your machine.
- No hosted service to provision, secure, or pay for.
- No extra API keys, webhooks, queues, or background workers.
- Works offline for local development and incident analysis.

This is a deliberate trade-off: LLMBillingKit is designed to be a lightweight embedded accounting layer, not a hosted analytics platform.

## Install

```bash
pip install llmbillingkit
```

## Quick usage

```python
from openai import OpenAI
from LLMBillingKit import track

client = OpenAI()
response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello!"}],
)

event = track(response, charged=0.05, customer="user_123")
print(event)
```

`track()` works with OpenAI-compatible responses and Anthropic-style usage fields (`input_tokens` / `output_tokens`).

## How it works

1. `track(response, charged, customer)` extracts `model`, token usage, and `request_id` from the response object.
2. It looks up per-token pricing from bundled `costs.json`.
3. It computes:

$$
\mathrm{actual\_cost} = (\mathrm{input\_tokens} \times \mathrm{input\_price}) + (\mathrm{output\_tokens} \times \mathrm{output\_price})
$$

$$
\mathrm{margin} = \mathrm{charged} - \mathrm{actual\_cost}
$$

4. It stores the event in local SQLite (`~/.LLMBillingKit/usage.db`).
5. The CLI reads this table to generate reporting and exports.

If a model is unknown in the pricing table, `track()` returns `None` rather than crashing your app.

## CLI commands and sample output

### `llmbilling report`

```text
$ llmbilling report
Customer      Calls    Charged      Cost    Margin
----------  -------  ---------  --------  --------
acme_corp        84  $4.200000  $0.620000  $3.580000
pro_tier         47  $2.350000  $0.190000  $2.160000
trial_user       23  $0.460000  $0.310000  $0.150000
user_free       312  $0.000000  $1.870000  $-1.870000
```

### `llmbilling models`

```text
$ llmbilling models
Model                          Calls    Charged      Cost    Margin
---------------------------  -------  ---------  --------  --------
gpt-4o                           112  $0.560000  $0.094000  $0.466000
gpt-4o-mini                      289  $0.140000  $0.003000  $0.137000
claude-3-5-sonnet-20241022        65  $0.300000  $0.120000  $0.180000
```

### `llmbilling export --format csv`

```text
$ llmbilling export --format csv
request_id,timestamp,customer,model,input_tokens,output_tokens,actual_cost,charged,margin
chatcmpl-abc,2026-03-25T14:32:10+00:00,acme_corp,gpt-4o,450,120,0.00213,0.05,0.04787
msg-xyz,2026-03-25T14:33:50+00:00,pro_tier,claude-3-5-sonnet-20241022,200,80,0.00105,0.02,0.01895
```

### `llmbilling export --format json`

```text
$ llmbilling export --format json
[
    {
        "request_id": "chatcmpl-abc",
        "timestamp": "2026-03-25T14:32:10+00:00",
        "customer": "acme_corp",
        "model": "gpt-4o",
        "input_tokens": 450,
        "output_tokens": 120,
        "actual_cost": 0.00213,
        "charged": 0.05,
        "margin": 0.04787
    }
]
```

## CLI reference

| Command | Description |
|---------|-------------|
| `llmbilling report` | Margin breakdown by customer |
| `llmbilling report --days 7` | Filter to the last 7 days |
| `llmbilling report --model gpt-4o` | Filter by model |
| `llmbilling models` | Margin breakdown by model |
| `llmbilling models --days 30` | Model report for the last 30 days |
| `llmbilling export` | Export raw events as CSV |
| `llmbilling export --format json` | Export raw events as JSON |

## Supported models

Pricing data lives in `LLMBillingKit/costs.json` and is verified in `PRICING_VERIFICATION.md`.

Current table includes representative models from:

- OpenAI (for example `gpt-4o`, `gpt-4o-mini`, `o3-mini`)
- Anthropic (for example `claude-sonnet-4-20250514`, `claude-3-5-haiku-20241022`)
- Google (for example `gemini-2.5-pro`, `gemini-2.5-flash`)
- Mistral (for example `mistral-large-latest`)

## Limitations

- Cost accuracy depends on the bundled static pricing table and how quickly it is updated.
- Some providers have pricing nuances (for example reasoning tokens or tier-based rates) that may not be fully modeled.
- Unknown models return `None` from `track()` until their pricing is added.
- SQLite is local-first by design, so there is no built-in multi-host sync dashboard.
- `test_e2e.py` requires a real provider API key and network access.

## Roadmap

- Faster pricing table update process and validation automation.
- Optional backends beyond local SQLite for teams that need centralized storage.
- More built-in analytics views (cohort, endpoint, and trend reporting).
- Better tooling around provider-specific pricing edge cases.

## Examples

See `examples/` for runnable scripts that demonstrate tracking and reporting patterns.

## Contributing

Contributions are welcome. Start with `CONTRIBUTING.md` for setup, test, and PR guidance.

## Code of conduct

This project follows the Contributor Covenant. See `CODE_OF_CONDUCT.md`.

## Changelog

Release notes and version history are in `CHANGELOG.md`.

## License

MIT
