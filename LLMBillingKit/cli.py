import csv
import io
import json

import click
from tabulate import tabulate

from .db import export_all, query_by_customer, query_by_feature, query_by_model


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
def features(days):
    """Show margin report grouped by feature tag."""
    rows = query_by_feature(days=days)
    if not rows:
        click.echo("No data.")
        return
    table = [
        [
            r["feature"],
            r["calls"],
            r["total_input_tokens"],
            r["total_input_chars"],
            f"${r['total_charged']:.6f}",
            f"${r['total_cost']:.6f}",
            f"${r['total_margin']:.6f}",
        ]
        for r in rows
    ]
    click.echo(tabulate(
        table,
        headers=["Feature", "Calls", "Input tokens", "Input chars",
                 "Charged", "Cost", "Margin"],
    ))


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
