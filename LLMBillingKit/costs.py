from __future__ import annotations

import json
import re
from pathlib import Path

_COSTS_FILE = Path(__file__).parent / "costs.json"
_costs: dict | None = None
_OPENAI_VERSIONED_SUFFIX = re.compile(r"^(?P<base>.+)-\d{4}-\d{2}-\d{2}$")


def _load() -> dict:
    global _costs
    if _costs is None:
        with open(_COSTS_FILE) as f:
            _costs = json.load(f)
    return _costs


def get_cost(model: str) -> dict | None:
    """Return {"input": float, "output": float} for a model, or None."""
    val = _load().get(model)
    if val is None:
        match = _OPENAI_VERSIONED_SUFFIX.match(model)
        if match:
            val = _load().get(match.group("base"))
    if not isinstance(val, dict):
        return None
    inp = val.get("input")
    out = val.get("output")
    if not isinstance(inp, (int, float)) or isinstance(inp, bool):
        return None
    if not isinstance(out, (int, float)) or isinstance(out, bool):
        return None
    return val
