import json
import re
from pathlib import Path

_COSTS_FILE = Path(__file__).parent / "costs.json"
_costs: dict | None = None

_DATE_SUFFIX_RE = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def _load() -> dict:
    global _costs
    if _costs is None:
        with open(_COSTS_FILE) as f:
            _costs = json.load(f)
    return _costs


def resolve_model(model: str) -> str | None:
    """Return the canonical pricing key for a model, or None if unknown.

    Tries an exact match first, then strips a trailing ISO date suffix
    (e.g. ``gpt-4o-mini-2024-07-18`` -> ``gpt-4o-mini``) so providers that
    return dated model IDs still resolve to a known price.
    """
    costs = _load()
    if model in costs:
        return model
    stripped = _DATE_SUFFIX_RE.sub("", model)
    if stripped != model and stripped in costs:
        return stripped
    return None


def get_cost(model: str) -> dict | None:
    """Return {"input": float, "output": float} for a model, or None."""
    resolved = resolve_model(model)
    if resolved is None:
        return None
    return _load()[resolved]
