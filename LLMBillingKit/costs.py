import json
from pathlib import Path

_COSTS_FILE = Path(__file__).parent / "costs.json"
_costs: dict | None = None


def _load() -> dict:
    global _costs
    if _costs is None:
        with open(_COSTS_FILE) as f:
            _costs = json.load(f)
    return _costs


def get_cost(model: str) -> dict | None:
    """Return {"input": float, "output": float} for a model, or None."""
    return _load().get(model)
