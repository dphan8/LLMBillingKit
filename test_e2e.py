from __future__ import annotations

import os

import pytest

from LLMBillingKit import track


pytestmark = pytest.mark.e2e


def _run_e2e(for_pytest: bool) -> dict | None:
    try:
        import openai
    except ImportError:
        if for_pytest:
            pytest.skip("openai package is not installed")
        raise SystemExit("openai package is not installed. Run: pip install openai")

    if not os.getenv("OPENAI_API_KEY"):
        if for_pytest:
            pytest.skip("OPENAI_API_KEY is not set")
        raise SystemExit("OPENAI_API_KEY is not set")

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
    )
    return track(response, charged=0.01, customer="test_user")


def test_openai_e2e_smoke() -> None:
    result = _run_e2e(for_pytest=True)
    assert result is not None
    assert result["model"] == "gpt-4o-mini"


if __name__ == "__main__":
    result = _run_e2e(for_pytest=False)
    print(result)
