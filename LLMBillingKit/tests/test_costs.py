import json
from pathlib import Path

from LLMBillingKit.costs import get_cost


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
