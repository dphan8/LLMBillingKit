from __future__ import annotations

import json
from pathlib import Path

_COSTS_FILE = Path(__file__).parent / "costs.json"
_costs: dict | None = None

# Dated provider snapshots that are verified to share pricing with a
# canonical key in costs.json. Only add an entry once you have confirmed
# the snapshot is priced identically to its alias target — snapshots with
# different rates (e.g. ``gpt-4o-2024-05-13`` vs ``gpt-4o``) must be added
# as their own entry in costs.json with their own prices instead.
_MODEL_ALIASES: dict[str, str] = {
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
}


def _load() -> dict:
    global _costs
    if _costs is None:
        with open(_COSTS_FILE) as f:
            _costs = json.load(f)
    return _costs


def resolve_model(model: str) -> str | None:
    """Return the canonical pricing key for a model, or None if unknown.

    Tries an exact match first, then a small allowlist of verified-equivalent
    dated snapshots (see ``_MODEL_ALIASES``). Unknown dated IDs return
    ``None`` rather than silently reusing another model's price.
    """
    costs = _load()
    if model in costs:
        return model
    alias = _MODEL_ALIASES.get(model)
    if alias is not None and alias in costs:
        return alias
    return None


def get_cost(model: str) -> dict | None:
    """Return {"input": float, "output": float} for a model, or None."""
    resolved = resolve_model(model)
    if resolved is None:
        return None
    return _load()[resolved]
