# Examples

## track_and_report.py

Demonstrates a typical LLMBillingKit flow:

1. Create response objects that contain model and token usage fields.
2. Track each call with `track(response, charged, customer)`.
3. Query aggregated margin data and print a report table.

Run it from the repository root:

```bash
python examples/track_and_report.py
```

Then compare with CLI output:

```bash
llmbilling report
llmbilling models
```
