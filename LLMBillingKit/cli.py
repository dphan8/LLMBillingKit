import csv
import io
import json

import click
from tabulate import tabulate

from .db import export_all, query_by_customer, query_by_model, update_event
from .tracker import TrackingError, track_usage


def _print_event(event: dict) -> None:
    click.echo(f"  request_id: {event['request_id']}")
    click.echo(f"  customer:   {event['customer']}")
    click.echo(f"  model:      {event['model']}")
    click.echo(f"  tokens:     in={event['input_tokens']} out={event['output_tokens']}")
    click.echo(f"  charged:    ${event['charged']:.6f}")
    click.echo(f"  cost:       ${event['actual_cost']:.6f}")
    click.echo(f"  margin:     ${event['margin']:.6f}")


@click.group()
def cli():
    """LLMBillingKit — track net margin on every LLM API call."""


@cli.command()
@click.option("--days", type=int, default=None, help="Filter to last N days.")
@click.option("--model", type=str, default=None, help="Filter to a specific model.")
def report(days, model):
    """Show margin report grouped by customer."""
    rows = query_by_customer(days=days, model=model)
    if not rows:
        click.echo("No data.")
        return
    table = [
        [
            r["customer"],
            r["calls"],
            f"${r['total_charged']:.6f}",
            f"${r['total_cost']:.6f}",
            f"${r['total_margin']:.6f}",
        ]
        for r in rows
    ]
    click.echo(tabulate(table, headers=["Customer", "Calls", "Charged", "Cost", "Margin"]))


@cli.command()
@click.option("--days", type=int, default=None, help="Filter to last N days.")
def models(days):
    """Show margin report grouped by model."""
    rows = query_by_model(days=days)
    if not rows:
        click.echo("No data.")
        return
    table = [
        [
            r["model"],
            r["calls"],
            f"${r['total_charged']:.6f}",
            f"${r['total_cost']:.6f}",
            f"${r['total_margin']:.6f}",
        ]
        for r in rows
    ]
    click.echo(tabulate(table, headers=["Model", "Calls", "Charged", "Cost", "Margin"]))


@cli.command()
@click.option("--days", type=int, default=None, help="Filter to last N days.")
@click.option("--model", type=str, default=None, help="Filter to a specific model.")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv",
              help="Output format.")
def export(days, model, fmt):
    """Export raw usage events to stdout."""
    rows = export_all(days=days, model=model)
    if not rows:
        click.echo("No data.")
        return
    if fmt == "json":
        click.echo(json.dumps(rows, indent=2))
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        click.echo(buf.getvalue().rstrip())


@cli.command()
@click.option("--customer", required=True, help="Customer identifier.")
@click.option("--model", required=True, help="Model name (must exist in pricing table).")
@click.option("--input-tokens", type=int, required=True, help="Prompt/input token count.")
@click.option("--output-tokens", type=int, required=True, help="Completion/output token count.")
@click.option("--charged", type=float, required=True, help="Amount charged to the customer.")
@click.option("--request-id", default=None,
              help="Stable request ID. A UUID is generated if omitted.")
def add(customer, model, input_tokens, output_tokens, charged, request_id):
    """Add a usage event without writing Python code."""
    try:
        event = track_usage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            charged=charged,
            customer=customer,
            request_id=request_id,
            raise_errors=True,
        )
    except TrackingError as e:
        raise click.ClickException(str(e)) from e
    click.echo("Added event:")
    _print_event(event)


@cli.command()
@click.option("--request-id", required=True, help="ID of the event to update.")
@click.option("--customer", default=None, help="New customer identifier.")
@click.option("--charged", type=float, default=None,
              help="New charged amount. Margin is recomputed automatically.")
def update(request_id, customer, charged):
    """Update charged amount or customer for an existing record."""
    if customer is None and charged is None:
        raise click.ClickException("Provide --customer and/or --charged to update.")
    event = update_event(request_id, customer=customer, charged=charged)
    if event is None:
        raise click.ClickException(f"No event found with request_id={request_id!r}.")
    click.echo("Updated event:")
    _print_event(event)
