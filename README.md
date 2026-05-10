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

If a model is unknown in the pricing table, `track()` returns `None` rather than crashing your app. Pass `raise_errors=True` to get an explicit `TrackingError` describing what went wrong:

```python
from LLMBillingKit import TrackingError, track

try:
    track(response, charged=0.01, customer="user_123", raise_errors=True)
except TrackingError as e:
    print(f"could not track: {e}")
```

A small allowlist of dated provider snapshots that are verified to share pricing with a base model (for example `gpt-4o-mini-2024-07-18` → `gpt-4o-mini`) is normalized automatically. Anthropic canonical IDs already include a date in their pricing key (`claude-3-5-sonnet-20241022`) and are matched as-is. Other dated snapshots — including OpenAI ones priced differently from their alias (e.g. `gpt-4o-2024-05-13`) — must be added to `costs.json` with their own prices; they will not be silently collapsed onto another model's rates.

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

### `llmbilling add`

Record a usage event without writing Python — useful for backfills, manual
corrections, or providers that do not return a structured response.

```text
$ llmbilling add \
    --customer acme \
    --model gpt-4o-mini \
    --input-tokens 8 \
    --output-tokens 9 \
    --charged 0.10
Added event:
  request_id: 6a4f...
  customer:   acme
  model:      gpt-4o-mini
  tokens:     in=8 out=9
  charged:    $0.100000
  cost:       $0.000007
  margin:     $0.099993
```

### `llmbilling update`

Edit the customer or charged amount on an existing record. Margin is
recomputed automatically when `--charged` changes.

```text
llmbilling update --request-id chatcmpl-abc --charged 0.25
llmbilling update --request-id chatcmpl-abc --customer acme-enterprise
```

### Bulk-create with `--calls`

`llmbilling add --calls N` records `N` equivalent usage events in one go (each
gets its own UUID). Useful for testing, demos, or backfilling fixed-shape
traffic.

```text
$ llmbilling add \
    --customer Walmart \
    --model gpt-4o-mini \
    --input-tokens 100 \
    --output-tokens 150 \
    --charged 0.15 \
    --calls 10
Added 10 events for customer 'Walmart':
  model:      gpt-4o-mini
  tokens:     in=100 out=150
  per-call:   charged $0.150000 | cost $0.000105 | margin $0.149895
  totals:     charged $1.500000 | cost $0.001050 | margin $1.498950
```

`--request-id` cannot be combined with `--calls > 1` (each event needs a
unique ID).

### `llmbilling customer set-calls`

Set how many usage events a customer has, increasing or decreasing the count
to a target number.

```text
llmbilling customer set-calls --customer Walmart --calls 10
llmbilling customer set-calls --customer Walmart --calls 1 --yes
```

Behavior:

- **Increase** clones the customer's existing event shape using fresh UUIDs
  and current timestamps.
- **Decrease** deletes the *most recent* matching events, preserving the
  oldest history. Requires `--yes` to skip the confirmation prompt.
- If the customer has events of multiple shapes (different
  model / tokens / charged combinations), pass `--model`, `--input-tokens`,
  `--output-tokens`, and `--charged` together to disambiguate which shape
  to adjust.
- A brand-new customer can be created by providing the full shape filter.

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
| `llmbilling add --customer <name> --model <model> --input-tokens <n> --output-tokens <n> --charged <amount>` | Record a usage event from the CLI |
| `llmbilling add ... --calls <N>` | Record N equivalent events in one command |
| `llmbilling update --request-id <id> --charged <amount>` | Update the charged amount on an existing event (recomputes margin) |
| `llmbilling update --request-id <id> --customer <customer>` | Reassign an event to a different customer |
| `llmbilling customer set-calls --customer <name> --calls <N>` | Adjust a customer's event count up or down |

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
