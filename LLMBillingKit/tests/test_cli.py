from __future__ import annotations

from click.testing import CliRunner

from LLMBillingKit.cli import cli
from LLMBillingKit.db import events_for_customer, insert_event


def _make_event(request_id="req-1", customer="acme", model="gpt-4o"):
    return {
        "request_id": request_id,
        "timestamp": "2026-03-21T00:00:00+00:00",
        "customer": customer,
        "model": model,
        "input_tokens": 100,
        "output_tokens": 50,
        "actual_cost": 0.00075,
        "charged": 0.01,
        "margin": 0.00925,
    }


def test_report_no_data(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("LLMBillingKit.cli.query_by_customer",
                        lambda **kw: [])
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 0
    assert "No data" in result.output


def test_report_with_data(tmp_path, monkeypatch):
    monkeypatch.setattr("LLMBillingKit.cli.query_by_customer",
                        lambda **kw: [{"customer": "acme", "calls": 2,
                                       "total_charged": 0.02, "total_cost": 0.0015,
                                       "total_margin": 0.0185}])
    runner = CliRunner()
    result = runner.invoke(cli, ["report"])
    assert result.exit_code == 0
    assert "acme" in result.output
    assert "Margin" in result.output


def test_models_command(monkeypatch):
    monkeypatch.setattr("LLMBillingKit.cli.query_by_model",
                        lambda **kw: [{"model": "gpt-4o", "calls": 5,
                                       "total_charged": 0.05, "total_cost": 0.003,
                                       "total_margin": 0.047}])
    runner = CliRunner()
    result = runner.invoke(cli, ["models"])
    assert result.exit_code == 0
    assert "gpt-4o" in result.output


def test_export_csv(monkeypatch):
    monkeypatch.setattr("LLMBillingKit.cli.export_all",
                        lambda **kw: [_make_event()])
    runner = CliRunner()
    result = runner.invoke(cli, ["export"])
    assert result.exit_code == 0
    assert "request_id" in result.output
    assert "acme" in result.output


def test_export_json(monkeypatch):
    monkeypatch.setattr("LLMBillingKit.cli.export_all",
                        lambda **kw: [_make_event()])
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--format", "json"])
    assert result.exit_code == 0
    assert '"customer": "acme"' in result.output


def _patch_insert_events(monkeypatch) -> list[dict]:
    """Replace cli.insert_events with a no-op that records the inserted rows."""
    captured: list[dict] = []
    monkeypatch.setattr(
        "LLMBillingKit.cli.insert_events",
        lambda events: captured.extend(events),
    )
    return captured


def test_add_command_inserts_event(monkeypatch):
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add",
        "--customer", "acme",
        "--model", "gpt-4o-mini",
        "--input-tokens", "8",
        "--output-tokens", "9",
        "--charged", "0.10",
    ])
    assert result.exit_code == 0, result.output
    assert "Added event" in result.output
    assert len(inserted) == 1
    assert inserted[0]["customer"] == "acme"
    assert inserted[0]["model"] == "gpt-4o-mini"
    assert inserted[0]["charged"] == 0.10


def test_add_command_normalizes_dated_model(monkeypatch):
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add",
        "--customer", "acme",
        "--model", "gpt-4o-mini-2024-07-18",
        "--input-tokens", "10",
        "--output-tokens", "10",
        "--charged", "0.05",
    ])
    assert result.exit_code == 0, result.output
    assert inserted[0]["model"] == "gpt-4o-mini"


def test_add_command_unknown_model_reports_error(monkeypatch):
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add",
        "--customer", "acme",
        "--model", "totally-unknown-model",
        "--input-tokens", "1",
        "--output-tokens", "1",
        "--charged", "0.01",
    ])
    assert result.exit_code != 0
    assert "Unknown model pricing" in result.output
    # Critically: nothing was inserted (no partial success).
    assert inserted == []


def test_update_command_changes_charged(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.update_event",
        lambda request_id, customer=None, charged=None: {
            **_make_event(request_id=request_id),
            "charged": charged if charged is not None else 0.01,
            "margin": (charged if charged is not None else 0.01) - 0.00075,
        },
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "update", "--request-id", "req-1", "--charged", "0.25",
    ])
    assert result.exit_code == 0, result.output
    assert "Updated event" in result.output
    assert "0.250000" in result.output


def test_update_command_requires_a_field(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--request-id", "req-1"])
    assert result.exit_code != 0
    assert "Provide --customer and/or --charged" in result.output


def test_update_command_unknown_id(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.update_event",
        lambda request_id, customer=None, charged=None: None,
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "update", "--request-id", "missing", "--customer", "x",
    ])
    assert result.exit_code != 0
    assert "No event found" in result.output


def test_add_rejects_negative_tokens(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "acme", "--model", "gpt-4o",
        "--input-tokens", "-1", "--output-tokens", "1", "--charged", "0.01",
    ])
    assert result.exit_code != 0


def test_add_rejects_negative_charged(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "acme", "--model", "gpt-4o",
        "--input-tokens", "1", "--output-tokens", "1", "--charged", "-0.01",
    ])
    assert result.exit_code != 0


def test_add_rejects_duplicate_request_id(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.get_event",
        lambda request_id: _make_event(request_id=request_id),
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "acme", "--model", "gpt-4o",
        "--input-tokens", "1", "--output-tokens", "1", "--charged", "0.01",
        "--request-id", "already-here",
    ])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_add_calls_creates_n_events(monkeypatch):
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "Walmart", "--model", "gpt-4o-mini",
        "--input-tokens", "100", "--output-tokens", "150",
        "--charged", "0.15", "--calls", "10",
    ])
    assert result.exit_code == 0, result.output
    assert len(inserted) == 10
    assert {e["customer"] for e in inserted} == {"Walmart"}
    assert len({e["request_id"] for e in inserted}) == 10
    assert "Added 10 events" in result.output


def test_add_calls_zero_is_rejected(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "x", "--model", "gpt-4o",
        "--input-tokens", "1", "--output-tokens", "1",
        "--charged", "0.01", "--calls", "0",
    ])
    assert result.exit_code != 0


def test_add_rejects_request_id_with_calls_gt_1(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "--customer", "x", "--model", "gpt-4o",
        "--input-tokens", "1", "--output-tokens", "1",
        "--charged", "0.01", "--calls", "3",
        "--request-id", "fixed",
    ])
    assert result.exit_code != 0
    assert "--request-id cannot be combined with --calls > 1" in result.output


def test_set_calls_new_customer_requires_full_shape(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [],
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Newco", "--calls", "5",
    ])
    assert result.exit_code != 0
    assert "No events found" in result.output


def test_set_calls_zero_for_missing_customer_is_noop(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [],
    )
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Nobody", "--calls", "0",
    ])
    assert result.exit_code == 0, result.output
    assert "Nothing to do" in result.output
    assert inserted == []


def test_set_calls_new_customer_partial_shape_rejected(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [],
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Newco", "--calls", "5",
        "--model", "gpt-4o",
    ])
    assert result.exit_code != 0
    assert "must be provided together" in result.output


def test_set_calls_new_customer_creates_events(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [],
    )
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "5",
        "--model", "gpt-4o-mini", "--input-tokens", "100",
        "--output-tokens", "150", "--charged", "0.15",
    ])
    assert result.exit_code == 0, result.output
    assert len(inserted) == 5
    assert "Created 5 events" in result.output


def test_set_calls_existing_single_shape_increase(monkeypatch):
    rows = [
        _make_event(request_id=f"r{i}", customer="Walmart")
        for i in range(3)
    ]
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: rows,
    )
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "10",
    ])
    assert result.exit_code == 0, result.output
    assert len(inserted) == 7  # 10 - 3
    assert "Added 7 events" in result.output


def test_set_calls_existing_single_shape_decrease_keeps_oldest(monkeypatch):
    deleted_ids = []

    def fake_delete(ids):
        deleted_ids.extend(ids)
        return len(ids)

    rows = []
    for i in range(5):
        e = _make_event(request_id=f"r{i}", customer="Walmart")
        e["timestamp"] = f"2026-01-0{i + 1}T00:00:00+00:00"
        rows.append(e)

    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: rows,
    )
    monkeypatch.setattr(
        "LLMBillingKit.cli.delete_events", fake_delete,
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "1", "--yes",
    ])
    assert result.exit_code == 0, result.output
    # Oldest (r0) is kept; r1..r4 get deleted.
    assert deleted_ids == ["r1", "r2", "r3", "r4"]
    assert "Deleted 4 event(s)" in result.output


def test_set_calls_decrease_aborts_without_yes(monkeypatch):
    rows = [
        _make_event(request_id=f"r{i}", customer="Walmart")
        for i in range(3)
    ]
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: rows,
    )
    deleted_ids = []
    monkeypatch.setattr(
        "LLMBillingKit.cli.delete_events",
        lambda ids: deleted_ids.extend(ids) or len(ids),
    )
    runner = CliRunner()
    # Pipe "n" to the confirm prompt.
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "1",
    ], input="n\n")
    assert result.exit_code != 0  # click aborts with non-zero
    assert deleted_ids == []


def test_set_calls_multiple_shapes_requires_filter(monkeypatch):
    e1 = _make_event(request_id="r1", customer="Walmart", model="gpt-4o")
    e2 = _make_event(request_id="r2", customer="Walmart", model="gpt-4o-mini")
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [e1, e2],
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "5",
    ])
    assert result.exit_code != 0
    assert "multiple shapes" in result.output


def test_set_calls_no_op_when_already_at_target(monkeypatch):
    rows = [_make_event(request_id=f"r{i}", customer="Walmart") for i in range(3)]
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: rows,
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "3",
    ])
    assert result.exit_code == 0
    assert "Nothing to do" in result.output


def test_set_calls_resolves_dated_alias_against_canonical_rows(monkeypatch):
    # Customer was tracked via a dated alias; track_usage stored the canonical
    # name. Passing the alias to set-calls must still find the existing rows.
    rows = [
        _make_event(request_id="r1", customer="acme", model="gpt-4o-mini"),
        _make_event(request_id="r2", customer="acme", model="gpt-4o-mini"),
    ]
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: rows,
    )
    inserted = _patch_insert_events(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "acme", "--calls", "5",
        "--model", "gpt-4o-mini-2024-07-18",
        "--input-tokens", "100", "--output-tokens", "50", "--charged", "0.01",
    ])
    assert result.exit_code == 0, result.output
    # Should add 3 events (5 - 2 existing) instead of treating current as 0.
    assert len(inserted) == 3
    assert "Added 3 events" in result.output


def test_set_calls_unknown_model_returns_click_error(monkeypatch):
    monkeypatch.setattr(
        "LLMBillingKit.cli.events_for_customer", lambda c: [],
    )
    runner = CliRunner()
    result = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Newco", "--calls", "1",
        "--model", "totally-unknown-model",
        "--input-tokens", "1", "--output-tokens", "1", "--charged", "0.01",
    ])
    assert result.exit_code != 0
    assert "Unknown model pricing" in result.output
    # Crucially: no Python traceback escaped.
    assert "Traceback" not in result.output


def test_set_calls_end_to_end_against_real_db(tmp_path, monkeypatch):
    """End-to-end: increase from 1 → 10, then back to 1, against a real DB."""
    db_path = tmp_path / "usage.db"
    monkeypatch.setattr("LLMBillingKit.db.DEFAULT_DB", db_path)
    runner = CliRunner()

    add = runner.invoke(cli, [
        "add", "--customer", "Walmart", "--model", "gpt-4o-mini",
        "--input-tokens", "100", "--output-tokens", "150", "--charged", "0.15",
    ])
    assert add.exit_code == 0, add.output
    assert len(events_for_customer("Walmart", db_path=db_path)) == 1

    up = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "10",
    ])
    assert up.exit_code == 0, up.output
    assert len(events_for_customer("Walmart", db_path=db_path)) == 10

    report = runner.invoke(cli, ["report"])
    assert report.exit_code == 0
    assert "Walmart" in report.output
    assert "10" in report.output  # call count

    down = runner.invoke(cli, [
        "customer", "set-calls",
        "--customer", "Walmart", "--calls", "1", "--yes",
    ])
    assert down.exit_code == 0, down.output
    assert len(events_for_customer("Walmart", db_path=db_path)) == 1
