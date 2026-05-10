from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .costs import get_cost, resolve_model
from .db import insert_event


class TrackingError(ValueError):
    """Raised when an event cannot be tracked and ``raise_errors`` is enabled."""


def track_usage(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    charged: float,
    customer: str = "default",
    request_id: str | None = None,
    timestamp: str | None = None,
    raise_errors: bool = False,
) -> dict | None:
    """Track an LLM API call from raw fields (no response object required).

    Returns the persisted event dict, or ``None`` if tracking failed and
    ``raise_errors`` is False. With ``raise_errors=True`` a
    :class:`TrackingError` is raised instead of silently returning None.
    """
    try:
        if not model:
            raise TrackingError("Missing model name.")

        canonical = resolve_model(model)
        if canonical is None:
            raise TrackingError(f"Unknown model pricing: {model!r}")

        cost_info = get_cost(canonical)
        actual_cost = (input_tokens * cost_info["input"]) + (output_tokens * cost_info["output"])
        margin = charged - actual_cost

        event = {
            "request_id": request_id or str(uuid.uuid4()),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "customer": customer,
            "model": canonical,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "actual_cost": round(actual_cost, 10),
            "charged": charged,
            "margin": round(margin, 10),
        }

        insert_event(event)
        return event

    except TrackingError:
        if raise_errors:
            raise
        return None
    except Exception as e:
        if raise_errors:
            raise TrackingError(str(e)) from e
        return None


def track(
    response,
    charged: float,
    customer: str = "default",
    raise_errors: bool = False,
) -> dict | None:
    """Track an LLM API call and compute margin.

    Args:
        response: An LLM API response object (OpenAI, Anthropic, etc.)
        charged: The amount charged to the customer for this call.
        customer: Customer identifier.
        raise_errors: When True, raise :class:`TrackingError` on failure
            instead of silently returning None. Defaults to False for
            backwards compatibility.

    Returns:
        A dict with cost/margin info, or None if tracking failed.
    """
    try:
        model = getattr(response, "model", None)
        if model is None:
            raise TrackingError("Response is missing a 'model' attribute.")

        usage = getattr(response, "usage", None)
        if usage is None:
            raise TrackingError("Response is missing a 'usage' attribute.")

        input_tokens = getattr(usage, "prompt_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "output_tokens", 0)

        request_id = getattr(response, "id", None)

        return track_usage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            charged=charged,
            customer=customer,
            request_id=request_id,
            raise_errors=raise_errors,
        )

    except TrackingError:
        if raise_errors:
            raise
        return None
    except Exception as e:
        if raise_errors:
            raise TrackingError(str(e)) from e
        return None
