import sqlite3

from LLMBillingKit.db import _connect, export_all, insert_event, query_by_customer, query_by_model


def _make_event(request_id="req-1", customer="acme", model="gpt-4o",
                input_tokens=100, output_tokens=50, charged=0.01):
    actual_cost = input_tokens * 0.0000025 + output_tokens * 0.00001
    return {
        "request_id": request_id,
        "timestamp": "2026-03-21T00:00:00+00:00",
        "customer": customer,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost": actual_cost,
        "charged": charged,
        "margin": charged - actual_cost,
    }


def test_table_creation(tmp_path):
    db = tmp_path / "test.db"
    conn = _connect(db)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage_events'")
    assert cursor.fetchone() is not None
    conn.close()


def test_insert_and_query(tmp_path):
    db = tmp_path / "test.db"
    insert_event(_make_event(), db_path=db)
    rows = export_all(db_path=db)
    assert len(rows) == 1
    assert rows[0]["customer"] == "acme"


def test_dedup(tmp_path):
    db = tmp_path / "test.db"
    insert_event(_make_event(request_id="dup-1"), db_path=db)
    insert_event(_make_event(request_id="dup-1"), db_path=db)
    rows = export_all(db_path=db)
    assert len(rows) == 1


def test_query_by_customer(tmp_path):
    db = tmp_path / "test.db"
    insert_event(_make_event(request_id="r1", customer="acme"), db_path=db)
    insert_event(_make_event(request_id="r2", customer="acme"), db_path=db)
    insert_event(_make_event(request_id="r3", customer="beta"), db_path=db)
    rows = query_by_customer(db_path=db)
    assert len(rows) == 2
    customers = {r["customer"] for r in rows}
    assert customers == {"acme", "beta"}


def test_query_by_model(tmp_path):
    db = tmp_path / "test.db"
    insert_event(_make_event(request_id="r1", model="gpt-4o"), db_path=db)
    insert_event(_make_event(request_id="r2", model="o3-mini"), db_path=db)
    rows = query_by_model(db_path=db)
    assert len(rows) == 2


def test_query_with_model_filter(tmp_path):
    db = tmp_path / "test.db"
    insert_event(_make_event(request_id="r1", model="gpt-4o"), db_path=db)
    insert_event(_make_event(request_id="r2", model="o3-mini"), db_path=db)
    rows = query_by_customer(model="gpt-4o", db_path=db)
    assert len(rows) == 1
    assert rows[0]["customer"] == "acme"
