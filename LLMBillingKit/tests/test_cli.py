from click.testing import CliRunner

from LLMBillingKit.cli import cli
from LLMBillingKit.db import insert_event


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


def test_add_command_inserts_event(monkeypatch):
    captured = {}

    def fake_insert(event):
        captured["event"] = event

    monkeypatch.setattr("LLMBillingKit.tracker.insert_event", fake_insert)
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
    assert captured["event"]["customer"] == "acme"
    assert captured["event"]["model"] == "gpt-4o-mini"
    assert captured["event"]["charged"] == 0.10


def test_add_command_normalizes_dated_model(monkeypatch):
    captured = {}

    def fake_insert(event):
        captured["event"] = event

    monkeypatch.setattr("LLMBillingKit.tracker.insert_event", fake_insert)
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
    assert captured["event"]["model"] == "gpt-4o-mini"


def test_add_command_unknown_model_reports_error(monkeypatch):
    monkeypatch.setattr("LLMBillingKit.tracker.insert_event",
                        lambda event: None)
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
