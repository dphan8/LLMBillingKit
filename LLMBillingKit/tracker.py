from __future__ import annotations

import uuid
import re
import logging
from datetime import datetime, timezone

from .costs import get_cost
from .db import insert_event

logger = logging.getLogger(__name__)

def _validate_identifier(value: str, max_length: int = 255) -> bool:
    """Validate customer and model identifiers to prevent DoS/injection."""
    if not isinstance(value, str) or not value:
        return False
    if len(value) > max_length:
        return False
    # Only allow safe characters: alphanumeric, dots, hyphens, underscores, @
    return bool(re.match(r'^[A-Za-z0-9._\-@]+$', value))

def track(response, charged: float, customer: str = "default") -> dict | None:
    """Track an LLM API call and compute margin.

    Args:
        response: An LLM API response object (OpenAI, Anthropic, etc.)
        charged: The amount charged to the customer for this call.
        customer: Customer identifier.

    Returns:
        A dict with cost/margin info, or None if tracking failed.
    """
    try:
        # Validate financial parameters (0 to $10k per call)
        if not isinstance(charged, (int, float)) or charged < 0 or charged > 10000:
            logger.warning(f"Tracker: suspicious or invalid charge amount: {charged}")
            return None

        # Validate customer identifier
        if not _validate_identifier(customer):
            logger.warning(f"Tracker: invalid customer identifier: {customer}")
            return None

        model = getattr(response, "model", None)
        if model is None:
            return None

        # Validate model identifier (if found)
        if model and not _validate_identifier(model):
            logger.warning(f"Tracker: invalid model identifier in response: {model}")
            return None

        usage = getattr(response, "usage", None)
        if usage is None:
            return None

        input_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", 0)

        request_id = getattr(response, "id", None) or str(uuid.uuid4())

        cost_info = get_cost(model)
        if cost_info is None:
            return None

        actual_cost = (input_tokens * cost_info["input"]) + (output_tokens * cost_info["output"])
        margin = charged - actual_cost

        event = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer": customer,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "actual_cost": round(actual_cost, 10),
            "charged": charged,
            "margin": round(margin, 10),
        }

        insert_event(event)
        return event

    except Exception as e:
        logger.error(f"Tracker: failed to track event: {type(e).__name__}")
        return None
