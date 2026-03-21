# costs.json Pricing Verification — March 2026

All prices below are per-token in USD, derived from per-1M-token rates on official pricing pages and pricepertoken.com (last checked March 21, 2026).

## Verified Prices (use these)

| Model | Input/token | Output/token | Source | Per 1M (input/output) |
|-------|-------------|--------------|--------|----------------------|
| gpt-4o | 0.0000025 | 0.00001 | pricepertoken.com | $2.50 / $10.00 |
| gpt-4o-mini | 0.00000015 | 0.0000006 | pricepertoken.com | $0.15 / $0.60 |
| gpt-4.1 | 0.000002 | 0.000008 | pricepertoken.com | $2.00 / $8.00 |
| gpt-4.1-mini | 0.0000002 | 0.0000008 | pricepertoken.com | $0.20 / $0.80 |
| gpt-4.1-nano | 0.0000001 | 0.0000004 | pricepertoken.com | $0.10 / $0.40 |
| o1-mini | 0.00000055 | 0.0000022 | pricepertoken.com | $0.55 / $2.20 |
| o3-mini | 0.00000055 | 0.0000022 | pricepertoken.com | $0.55 / $2.20 |
| o4-mini | 0.00000055 | 0.0000022 | pricepertoken.com | $0.55 / $2.20 |
| claude-sonnet-4-20250514 | 0.000003 | 0.000015 | Anthropic docs | $3.00 / $15.00 |
| claude-3-5-sonnet-20241022 | 0.000003 | 0.000015 | Anthropic docs | $3.00 / $15.00 |
| claude-3-5-haiku-20241022 | 0.000001 | 0.000005 | Anthropic docs | $1.00 / $5.00 |
| claude-3-haiku-20240307 | 0.00000025 | 0.00000125 | Anthropic docs | $0.25 / $1.25 |
| gemini-2.0-flash | 0.0000001 | 0.0000004 | pricepertoken.com | $0.10 / $0.40 |
| gemini-2.5-pro | 0.00000125 | 0.00001 | Google AI docs | $1.25 / $10.00 |
| gemini-2.5-flash | 0.0000003 | 0.0000025 | TLDL.io, MetaCTO | $0.30 / $2.50 |
| mistral-large-latest | 0.000002 | 0.000006 | pricepertoken.com | $2.00 / $6.00 |
| mistral-small-latest | 0.0000001 | 0.0000003 | pricepertoken.com | $0.10 / $0.30 |

## Models REMOVED from original plan (couldn't verify current pricing)

| Model | Issue |
|-------|-------|
| o1 | Originally $15/$60 per 1M. Has been reduced but exact current price unclear. OpenAI pricing page now focuses on GPT-5.x. Add back when verified. |
| o3 | Was reportedly reduced 80% to ~$2/$8 per 1M, then further reduced. Conflicting sources. Add back when verified. |

## Notes

- o-series models (o1, o3, o4-mini) use hidden "reasoning tokens" billed as output tokens. Actual cost can be 2-5x the visible output tokens. LLMBillingKit tracks visible tokens only, so margins on o-series may appear higher than reality. Consider adding a warning in docs.
- Gemini 2.5 Pro has tiered pricing: $1.25/$10.00 under 200K context, $2.50/$20.00 over 200K. costs.json uses the standard rate.
- "mistral-large-latest" currently maps to Mistral Large 3 (Dec 2025). "mistral-small-latest" maps to Mistral Small 3.2 (Jun 2025).
- Google has deprecated Gemini 2.0 Flash (shutdown June 1, 2026). Consider adding gemini-3-pro and gemini-3-flash when they hit GA.
- Anthropic now has Claude Opus 4.6 ($5/$25) and Sonnet 4.6 ($3/$15). Add these model IDs when their exact API strings are confirmed.

## How to update

Replace `LLMBillingKit/costs.json` with the verified costs.json, then run tests:

```
cp costs.json LLMBillingKit/costs.json
pytest LLMBillingKit/tests/test_costs.py -v
```
