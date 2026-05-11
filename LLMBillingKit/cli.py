from __future__ import annotations

import csv
import io
import json

import click
from tabulate import tabulate

from .costs import resolve_model
from .db import (
    delete_events,
    events_for_customer,
    export_all,
    get_event,
    insert_events,
    query_by_customer,
    query_by_model,
    update_event,
)
from .tracker import TrackingError, build_event


def _build_and_insert_or_click(*, count: int, request_id: str | None = None,
                               **fields) -> list[dict]:
    """Build ``count`` events and insert them in a single transaction.

    The first event uses ``request_id`` (if given); subsequent events get
    fresh UUIDs. ``TrackingError`` is converted to ``click.ClickException``
    *before* anything is inserted, so a bad model never produces a partial
    success.
    """
    events: list[dict] = []
    for i in range(count):
        try:
            event = build_event(
                request_id=request_id if i == 0 else None,
                **fields,
            )
        except TrackingError as e:
            raise click.ClickException(str(e)) from e
        events.append(event)
    insert_events(events)
    return events


_SHAPE_FIELDS = ("model", "input_tokens", "output_tokens", "charged")


def _shape_of(row: dict) -> tuple:
    return tuple(row[f] for f in _SHAPE_FIELDS)


def _validate_shape_args(model, input_tokens, output_tokens, charged) -> bool:
    """Return True if all four shape args are provided, False if all are None.

    Raises ClickException if a partial set is given.
    """
    provided = [v is not None for v in (model, input_tokens, output_tokens, charged)]
    if all(provided):
        return True
    if not any(provided):
        return False
    raise click.ClickException(
        "Shape filters must be provided together: --model, --input-tokens, "
        "--output-tokens, --charged."
    )


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
@click.option("--model", required=True,
              help="Model name. Must exist in the pricing table or resolve via "
                   "an alias (for example dated OpenAI snapshots like "
                   "`gpt-4o-mini-2024-07-18`).")
@click.option("--input-tokens", type=click.IntRange(min=0), required=True,
              help="Prompt/input token count.")
@click.option("--output-tokens", type=click.IntRange(min=0), required=True,
              help="Completion/output token count.")
@click.option("--charged", type=click.FloatRange(min=0.0), required=True,
              help="Amount charged to the customer.")
@click.option("--calls", type=click.IntRange(min=1), default=1, show_default=True,
              help="Create N equivalent events. Each gets its own UUID.")
@click.option("--request-id", default=None,
              help="Stable request ID. A UUID is generated if omitted. "
                   "Cannot be combined with --calls > 1.")
def add(customer, model, input_tokens, output_tokens, charged, calls, request_id):
    """Add one or more usage events without writing Python code."""
    if request_id is not None and calls > 1:
        raise click.ClickException(
            "--request-id cannot be combined with --calls > 1; each event must "
            "have a unique ID. Omit --request-id to auto-generate UUIDs."
        )
    if request_id is not None and get_event(request_id) is not None:
        raise click.ClickException(
            f"An event with request_id={request_id!r} already exists. "
            "Use `llmbilling update` to modify it."
        )

    events = _build_and_insert_or_click(
        count=calls,
        request_id=request_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        charged=charged,
        customer=customer,
    )

    if calls == 1:
        click.echo("Added event:")
        _print_event(events[0])
    else:
        first = events[0]
        click.echo(f"Added {calls} events for customer {customer!r}:")
        click.echo(f"  model:      {first['model']}")
        click.echo(f"  tokens:     in={first['input_tokens']} out={first['output_tokens']}")
        click.echo(f"  per-call:   charged ${first['charged']:.6f} | "
                   f"cost ${first['actual_cost']:.6f} | "
                   f"margin ${first['margin']:.6f}")
        click.echo(f"  totals:     charged ${first['charged'] * calls:.6f} | "
                   f"cost ${first['actual_cost'] * calls:.6f} | "
                   f"margin ${first['margin'] * calls:.6f}")


@cli.command()
@click.option("--request-id", required=True, help="ID of the event to update.")
@click.option("--customer", default=None, help="New customer identifier.")
@click.option("--charged", type=click.FloatRange(min=0.0), default=None,
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


@cli.group("customer")
def customer_group():
    """Customer-level operations."""


@customer_group.command(name="set-calls")
@click.option("--customer", "customer_name", required=True,
              help="Customer identifier.")
@click.option("--calls", type=click.IntRange(min=0), required=True,
              help="Target number of usage events for this customer (matching "
                   "the chosen shape). 0 means delete all matching events.")
@click.option("--model", default=None,
              help="Restrict to events with this model. Required (with the "
                   "other shape options) when the customer has events of "
                   "multiple shapes, or when creating events for a customer "
                   "that does not exist yet.")
@click.option("--input-tokens", type=click.IntRange(min=0), default=None,
              help="Restrict to events with this input-token count.")
@click.option("--output-tokens", type=click.IntRange(min=0), default=None,
              help="Restrict to events with this output-token count.")
@click.option("--charged", type=click.FloatRange(min=0.0), default=None,
              help="Restrict to events with this charged amount.")
@click.option("--yes", is_flag=True, default=False,
              help="Skip confirmation when deleting events.")
def set_calls(customer_name, calls, model, input_tokens, output_tokens,
              charged, yes):
    """Set how many usage events a customer has.

    Increasing the count clones the customer's existing event shape (or the
    shape provided via the filter options) using fresh UUIDs and current
    timestamps. Decreasing the count deletes the most-recent matching events
    first, keeping the oldest history intact.
    """
    has_shape = _validate_shape_args(model, input_tokens, output_tokens, charged)
    if has_shape:
        canonical_model = resolve_model(model)
        if canonical_model is None:
            raise click.ClickException(f"Unknown model pricing: {model!r}")
        model = canonical_model
    rows = events_for_customer(customer_name)

    if not rows:
        # Asking a nonexistent customer to have 0 events is a no-op.
        if calls == 0:
            click.echo(
                f"Customer {customer_name!r} already has 0 calls. Nothing to do."
            )
            return
        # Brand-new customer with calls > 0: must supply a full shape.
        if not has_shape:
            raise click.ClickException(
                f"No events found for customer {customer_name!r}. To create "
                "events, also pass --model, --input-tokens, --output-tokens, "
                "and --charged."
            )
        _build_and_insert_or_click(
            count=calls,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            charged=charged,
            customer=customer_name,
        )
        click.echo(f"Created {calls} events for customer {customer_name!r}.")
        return

    # Existing customer.
    if has_shape:
        target_shape = (model, input_tokens, output_tokens, charged)
        matching = [r for r in rows if _shape_of(r) == target_shape]
    else:
        shapes = {_shape_of(r) for r in rows}
        if len(shapes) > 1:
            raise click.ClickException(
                f"Customer {customer_name!r} has events with multiple shapes; "
                "specify which to adjust with --model, --input-tokens, "
                "--output-tokens, and --charged."
            )
        target_shape = next(iter(shapes))
        matching = rows

    current = len(matching)
    delta = calls - current

    if delta == 0:
        click.echo(
            f"Customer {customer_name!r} already has {calls} matching call(s). "
            "Nothing to do."
        )
        return

    if delta > 0:
        m, in_t, out_t, ch = target_shape
        _build_and_insert_or_click(
            count=delta,
            model=m,
            input_tokens=in_t,
            output_tokens=out_t,
            charged=ch,
            customer=customer_name,
        )
        click.echo(
            f"Added {delta} events. Customer {customer_name!r} now has "
            f"{calls} matching call(s)."
        )
        return

    # Decrease: matching is sorted oldest-first; delete the newest -delta.
    n_to_delete = -delta
    to_delete = matching[calls:]
    if not yes:
        click.confirm(
            f"This will delete {n_to_delete} event(s) for customer "
            f"{customer_name!r}. Continue?",
            abort=True,
        )
    deleted = delete_events([r["request_id"] for r in to_delete])
    click.echo(
        f"Deleted {deleted} event(s). Customer {customer_name!r} now has "
        f"{calls} matching call(s)."
    )
