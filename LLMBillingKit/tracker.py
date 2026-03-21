import uuid
from datetime import datetime, timezone

from .costs import get_cost
from .db import insert_event


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
        model = getattr(response, "model", None)
        if model is None:
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

    except Exception:
        return None
