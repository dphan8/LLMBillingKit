import json
from pathlib import Path

from LLMBillingKit.costs import get_cost, resolve_model


def test_costs_json_structure():
    costs_file = Path(__file__).parent.parent / "costs.json"
    data = json.loads(costs_file.read_text())
    assert isinstance(data, dict)
    for model, prices in data.items():
        assert isinstance(model, str)
        assert "input" in prices
        assert "output" in prices
        assert isinstance(prices["input"], (int, float))
        assert isinstance(prices["output"], (int, float))
        assert prices["input"] > 0
        assert prices["output"] > 0


def test_get_cost_known_model():
    cost = get_cost("gpt-4o")
    assert cost is not None
    assert cost["input"] == 0.0000025
    assert cost["output"] == 0.00001


def test_get_cost_unknown_model():
    assert get_cost("nonexistent-model-xyz") is None


def test_resolve_model_strips_iso_date_suffix():
    assert resolve_model("gpt-4o-mini-2024-07-18") == "gpt-4o-mini"
    assert resolve_model("gpt-4o-2024-08-06") == "gpt-4o"


def test_get_cost_resolves_dated_model():
    cost = get_cost("gpt-4o-mini-2024-07-18")
    assert cost == get_cost("gpt-4o-mini")


def test_resolve_model_keeps_canonical_dated_id():
    # Anthropic IDs already include a date in their canonical key.
    assert resolve_model("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet-20241022"


def test_resolve_model_unknown_returns_none():
    assert resolve_model("totally-made-up-model-2099-01-01") is None
