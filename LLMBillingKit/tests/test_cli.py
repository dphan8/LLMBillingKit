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
