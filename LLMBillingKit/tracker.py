import uuid
from datetime import datetime, timezone

from .costs import get_cost
from .db import insert_event


def _build_event(
    response,
    charged: float,
    customer: str,
    extras: dict | None = None,
) -> dict | None:
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
    if extras:
        event.update(extras)
    return event


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
        event = _build_event(response, charged, customer)
        if event is None:
            return None
        insert_event(event)
        return event
    except Exception:
        return None


def _extract_prompt_size(
    request_payload: dict | list | None,
) -> tuple[int | None, int | None]:
    """Return (input_chars, prompt_messages) for a request payload.

    Accepts an OpenAI-style messages list, an OpenAI-style dict with a
    'messages' key, or an Anthropic-style dict with 'system' + 'messages'.
    Returns (None, None) when no payload is supplied or extraction fails,
    so the DB column stays NULL instead of being reported as zero.
    """
    if request_payload is None:
        return (None, None)

    try:
        chars = 0
        count = 0

        if isinstance(request_payload, list):
            messages = request_payload
            system = None
        elif isinstance(request_payload, dict):
            messages = request_payload.get("messages", []) or []
            system = request_payload.get("system")
        else:
            return (None, None)

        if isinstance(system, str):
            chars += len(system)
            count += 1
        elif isinstance(system, list):
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text":
                    chars += len(block.get("text", ""))
                    count += 1

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        chars += len(part.get("text", ""))
            count += 1

        return (chars, count)
    except Exception:
        return (None, None)


def wrap(
    provider_call,
    *,
    feature: str,
    session_id: str | None = None,
    priority: str | None = None,
    customer: str = "default",
    charged: float = 0.0,
    request_payload: dict | list | None = None,
    **call_kwargs,
):
    """Invoke a provider callable, then log the result with metadata.

    Args:
        provider_call: Callable that issues the actual API request.
        feature: Feature name that owns this call (required for attribution).
        session_id: Optional session/user identifier.
        priority: Optional free-form priority tier (e.g. 'low'|'normal'|'high').
        customer: Customer identifier (matches track()).
        charged: Amount charged to the customer.
        request_payload: OpenAI-style messages list, OpenAI-style dict with
            'messages', or Anthropic-style {'system', 'messages'}. Used to
            record prompt size before the call is forwarded.
        **call_kwargs: Forwarded to provider_call.

    Returns:
        The provider's response object, unchanged.

    Provider exceptions propagate. Tracking errors are swallowed.
    """
    input_chars, prompt_messages = _extract_prompt_size(request_payload)
    response = provider_call(**call_kwargs)
    try:
        event = _build_event(
            response,
            charged,
            customer,
            extras={
                "feature": feature,
                "session_id": session_id,
                "priority": priority,
                "input_chars": input_chars,
                "prompt_messages": prompt_messages,
            },
        )
        if event is not None:
            insert_event(event)
    except Exception:
        pass
    return response
