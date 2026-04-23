import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from LLMBillingKit import wrap
from LLMBillingKit.db import _connect, export_all
from LLMBillingKit.tracker import _extract_prompt_size


def _openai_response(model="gpt-4o", prompt_tokens=100, completion_tokens=50, id="resp-1"):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(model=model, usage=usage, id=id)


def _anthropic_response(model="claude-sonnet-4-20250514", input_tokens=100, output_tokens=50, id="msg-1"):
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(model=model, usage=usage, id=id)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point the library's default DB path at a tmp file so wrap() writes here."""
    db = tmp_path / "test.db"
    monkeypatch.setattr("LLMBillingKit.db.DEFAULT_DB", db)
    return db


# ---- wrap() happy paths & metadata ---------------------------------------


def test_wrap_happy_path_openai_response(isolated_db):
    resp = _openai_response(id="wrap-1")
    wrap(lambda **kw: resp,
         feature="summarize",
         session_id="sess-42",
         priority="high",
         charged=0.01,
         customer="acme")
    rows = export_all(db_path=isolated_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["feature"] == "summarize"
    assert row["session_id"] == "sess-42"
    assert row["priority"] == "high"
    assert row["customer"] == "acme"
    assert row["model"] == "gpt-4o"
    assert row["input_tokens"] == 100
    assert row["output_tokens"] == 50


def test_wrap_happy_path_anthropic_response(isolated_db):
    resp = _anthropic_response(id="wrap-2")
    wrap(lambda **kw: resp, feature="classify", charged=0.02)
    rows = export_all(db_path=isolated_db)
    assert len(rows) == 1
    assert rows[0]["feature"] == "classify"
    assert rows[0]["model"] == "claude-sonnet-4-20250514"
    expected_cost = 100 * 0.000003 + 50 * 0.000015
    assert abs(rows[0]["actual_cost"] - expected_cost) < 1e-10


def test_wrap_defaults_when_session_and_priority_omitted(isolated_db):
    resp = _openai_response(id="wrap-3")
    wrap(lambda **kw: resp, feature="only-feature", charged=0.01)
    rows = export_all(db_path=isolated_db)
    assert len(rows) == 1
    assert rows[0]["feature"] == "only-feature"
    assert rows[0]["session_id"] is None
    assert rows[0]["priority"] is None


def test_wrap_returns_provider_response_unchanged(isolated_db):
    resp = _openai_response(id="wrap-4")
    returned = wrap(lambda **kw: resp, feature="x")
    assert returned is resp


def test_wrap_forwards_kwargs_to_provider_call(isolated_db):
    received = {}

    def spy(**kwargs):
        received.update(kwargs)
        return _openai_response(id="wrap-5")

    wrap(spy,
         feature="x",
         model="gpt-4o",
         messages=[{"role": "user", "content": "hi"}],
         temperature=0.2)
    assert received["model"] == "gpt-4o"
    assert received["messages"] == [{"role": "user", "content": "hi"}]
    assert received["temperature"] == 0.2
    # Metadata kwargs must NOT leak into the provider call.
    assert "feature" not in received
    assert "charged" not in received
    assert "request_payload" not in received


def test_wrap_does_not_swallow_provider_errors(isolated_db):
    def boom(**kw):
        raise RuntimeError("429 rate limited")

    with pytest.raises(RuntimeError, match="429"):
        wrap(boom, feature="x")
    assert export_all(db_path=isolated_db) == []


def test_wrap_tracking_error_is_swallowed(isolated_db):
    resp = _openai_response(id="wrap-6")
    with patch("LLMBillingKit.tracker.insert_event", side_effect=RuntimeError("db down")):
        returned = wrap(lambda **kw: resp, feature="x", charged=0.01)
    assert returned is resp


def test_wrap_untrackable_response_does_not_raise(isolated_db):
    resp = SimpleNamespace(model="gpt-4o", id="wrap-7")  # no .usage
    returned = wrap(lambda **kw: resp, feature="x", charged=0.01)
    assert returned is resp
    assert export_all(db_path=isolated_db) == []


# ---- _extract_prompt_size -------------------------------------------------


def test_prompt_size_openai_messages_list():
    payload = [
        {"role": "system", "content": "hi"},
        {"role": "user", "content": "hello"},
    ]
    assert _extract_prompt_size(payload) == (7, 2)


def test_prompt_size_openai_dict_with_messages_key():
    payload = {"messages": [{"role": "user", "content": "abc"}]}
    assert _extract_prompt_size(payload) == (3, 1)


def test_prompt_size_anthropic_system_string_plus_messages():
    payload = {
        "system": "sys",
        "messages": [{"role": "user", "content": "hi"}],
    }
    assert _extract_prompt_size(payload) == (5, 2)


def test_prompt_size_anthropic_system_list_text_blocks():
    payload = {
        "system": [
            {"type": "text", "text": "alpha"},
            {"type": "text", "text": "beta"},
        ],
        "messages": [{"role": "user", "content": "hi"}],
    }
    # 5 + 4 (system) + 2 (user) = 11 chars; 2 system blocks + 1 user = 3 messages.
    assert _extract_prompt_size(payload) == (11, 3)


def test_prompt_size_multimodal_content_skips_images():
    payload = [
        {"role": "user", "content": [
            {"type": "text", "text": "hi"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]},
    ]
    assert _extract_prompt_size(payload) == (2, 1)


def test_prompt_size_none_payload_returns_none_none():
    assert _extract_prompt_size(None) == (None, None)


def test_prompt_size_persisted_in_db(isolated_db):
    resp = _openai_response(id="wrap-8")
    payload = [{"role": "user", "content": "hello world"}]
    wrap(lambda **kw: resp, feature="x", charged=0.01, request_payload=payload)
    rows = export_all(db_path=isolated_db)
    assert len(rows) == 1
    assert rows[0]["input_chars"] == 11
    assert rows[0]["prompt_messages"] == 1


# ---- migration ------------------------------------------------------------


_OLD_CREATE_TABLE = """
CREATE TABLE usage_events (
    request_id   TEXT PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    customer     TEXT NOT NULL,
    model        TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    actual_cost  REAL NOT NULL,
    charged      REAL NOT NULL,
    margin       REAL NOT NULL
)
"""


def _make_legacy_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute(_OLD_CREATE_TABLE)
    conn.execute(
        "INSERT INTO usage_events VALUES (?,?,?,?,?,?,?,?,?)",
        ("old-1", "2026-01-01T00:00:00+00:00", "acme", "gpt-4o",
         10, 5, 0.0001, 0.001, 0.0009),
    )
    conn.commit()
    conn.close()


def test_migration_from_pre_v02_schema(tmp_path):
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)

    _connect(db).close()

    raw = sqlite3.connect(str(db))
    cols = {row[1] for row in raw.execute("PRAGMA table_info(usage_events)")}
    raw.close()
    assert {"feature", "session_id", "priority",
            "input_chars", "prompt_messages"} <= cols

    from LLMBillingKit.db import insert_event
    insert_event({
        "request_id": "new-1",
        "timestamp": "2026-04-01T00:00:00+00:00",
        "customer": "beta",
        "model": "gpt-4o",
        "input_tokens": 5,
        "output_tokens": 5,
        "actual_cost": 0.00005,
        "charged": 0.001,
        "margin": 0.00095,
        "feature": "summarize",
        "session_id": "s1",
        "priority": "high",
        "input_chars": 42,
        "prompt_messages": 3,
    }, db_path=db)

    rows = export_all(db_path=db)
    assert len(rows) == 2
    by_id = {r["request_id"]: r for r in rows}
    assert by_id["old-1"]["feature"] is None
    assert by_id["old-1"]["input_chars"] is None
    assert by_id["new-1"]["feature"] == "summarize"
    assert by_id["new-1"]["input_chars"] == 42


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)
    _connect(db).close()
    _connect(db).close()  # second connect must not fail

    raw = sqlite3.connect(str(db))
    cols = [row[1] for row in raw.execute("PRAGMA table_info(usage_events)")]
    raw.close()
    # Each new column appears exactly once.
    for col in ("feature", "session_id", "priority", "input_chars", "prompt_messages"):
        assert cols.count(col) == 1
