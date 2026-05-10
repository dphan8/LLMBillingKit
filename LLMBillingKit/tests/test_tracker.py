from unittest.mock import patch
from types import SimpleNamespace

import pytest

from LLMBillingKit.tracker import TrackingError, track, track_usage


def _mock_response(model="gpt-4o", prompt_tokens=100, completion_tokens=50, id="resp-1"):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(model=model, usage=usage, id=id)


def _mock_anthropic_response(model="claude-sonnet-4-20250514", input_tokens=100, output_tokens=50, id="msg-1"):
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(model=model, usage=usage, id=id)


@patch("LLMBillingKit.tracker.insert_event")
def test_track_openai(mock_insert):
    resp = _mock_response()
    result = track(resp, charged=0.01)
    assert result is not None
    assert result["model"] == "gpt-4o"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    expected_cost = 100 * 0.0000025 + 50 * 0.00001
    assert abs(result["actual_cost"] - expected_cost) < 1e-12
    assert abs(result["margin"] - (0.01 - expected_cost)) < 1e-12
    mock_insert.assert_called_once()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_anthropic(mock_insert):
    resp = _mock_anthropic_response()
    result = track(resp, charged=0.05, customer="beta")
    assert result is not None
    assert result["customer"] == "beta"
    assert result["model"] == "claude-sonnet-4-20250514"
    expected_cost = 100 * 0.000003 + 50 * 0.000015
    assert abs(result["actual_cost"] - expected_cost) < 1e-12


@patch("LLMBillingKit.tracker.insert_event")
def test_track_missing_usage(mock_insert):
    resp = SimpleNamespace(model="gpt-4o", id="resp-2")
    result = track(resp, charged=0.01)
    assert result is None
    mock_insert.assert_not_called()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_missing_model(mock_insert):
    resp = SimpleNamespace(id="resp-3")
    result = track(resp, charged=0.01)
    assert result is None


@patch("LLMBillingKit.tracker.insert_event")
def test_track_unknown_model(mock_insert):
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=10)
    resp = SimpleNamespace(model="unknown-model", usage=usage, id="resp-4")
    result = track(resp, charged=0.01)
    assert result is None


@patch("LLMBillingKit.tracker.insert_event", side_effect=Exception("db error"))
def test_track_never_crashes(mock_insert):
    resp = _mock_response()
    result = track(resp, charged=0.01)
    assert result is None


@patch("LLMBillingKit.tracker.insert_event")
def test_track_generates_uuid_when_no_id(mock_insert):
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=10)
    resp = SimpleNamespace(model="gpt-4o", usage=usage)
    result = track(resp, charged=0.01)
    assert result is not None
    assert len(result["request_id"]) > 0


@patch("LLMBillingKit.tracker.insert_event")
def test_track_resolves_dated_openai_model(mock_insert):
    # OpenAI sometimes returns dated model IDs that aren't in costs.json.
    resp = _mock_response(model="gpt-4o-mini-2024-07-18")
    result = track(resp, charged=0.10)
    assert result is not None
    assert result["model"] == "gpt-4o-mini"
    expected_cost = 100 * 0.00000015 + 50 * 0.0000006
    assert abs(result["actual_cost"] - expected_cost) < 1e-12


@patch("LLMBillingKit.tracker.insert_event")
def test_track_raise_errors_on_unknown_model(mock_insert):
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=10)
    resp = SimpleNamespace(model="totally-unknown-model", usage=usage, id="r1")
    with pytest.raises(TrackingError, match="Unknown model pricing"):
        track(resp, charged=0.01, raise_errors=True)
    mock_insert.assert_not_called()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_raise_errors_on_missing_usage(mock_insert):
    resp = SimpleNamespace(model="gpt-4o", id="r2")
    with pytest.raises(TrackingError, match="usage"):
        track(resp, charged=0.01, raise_errors=True)


@patch("LLMBillingKit.tracker.insert_event")
def test_track_usage_basic(mock_insert):
    result = track_usage(
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        charged=0.05,
        customer="acme",
    )
    assert result is not None
    assert result["customer"] == "acme"
    assert result["model"] == "gpt-4o"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    expected_cost = 100 * 0.0000025 + 50 * 0.00001
    assert abs(result["actual_cost"] - expected_cost) < 1e-12
    mock_insert.assert_called_once()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_usage_raises_on_unknown_model(mock_insert):
    with pytest.raises(TrackingError, match="Unknown model pricing"):
        track_usage(
            model="bogus-model",
            input_tokens=1,
            output_tokens=1,
            charged=0.01,
            raise_errors=True,
        )
    mock_insert.assert_not_called()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_usage_silent_on_unknown_model(mock_insert):
    result = track_usage(
        model="bogus-model",
        input_tokens=1,
        output_tokens=1,
        charged=0.01,
    )
    assert result is None
    mock_insert.assert_not_called()


@patch("LLMBillingKit.tracker.insert_event")
def test_track_usage_uses_provided_request_id(mock_insert):
    result = track_usage(
        model="gpt-4o",
        input_tokens=1,
        output_tokens=1,
        charged=0.01,
        request_id="custom-id-123",
    )
    assert result["request_id"] == "custom-id-123"
