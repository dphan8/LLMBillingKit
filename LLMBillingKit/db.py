from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".LLMBillingKit" / "usage.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS usage_events (
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


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


_INSERT_SQL = (
    "INSERT OR IGNORE INTO usage_events "
    "(request_id, timestamp, customer, model, input_tokens, output_tokens, "
    "actual_cost, charged, margin) VALUES (?,?,?,?,?,?,?,?,?)"
)


def _row_for(event: dict) -> tuple:
    return (
        event["request_id"],
        event["timestamp"],
        event["customer"],
        event["model"],
        event["input_tokens"],
        event["output_tokens"],
        event["actual_cost"],
        event["charged"],
        event["margin"],
    )


def insert_event(event: dict, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(_INSERT_SQL, _row_for(event))
        conn.commit()
    finally:
        conn.close()


def insert_events(events: list[dict], db_path: Path | None = None) -> None:
    """Insert many events on a single connection in one transaction."""
    if not events:
        return
    conn = _connect(db_path)
    try:
        conn.executemany(_INSERT_SQL, [_row_for(e) for e in events])
        conn.commit()
    finally:
        conn.close()


def get_event(request_id: str, db_path: Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM usage_events WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def update_event(
    request_id: str,
    customer: str | None = None,
    charged: float | None = None,
    db_path: Path | None = None,
) -> dict | None:
    """Update an existing event's customer and/or charged amount.

    When ``charged`` is provided, ``margin`` is recomputed against the
    stored ``actual_cost``; otherwise ``margin`` is left untouched (so a
    customer-only update can't introduce floating-point drift). Returns
    the updated event dict, or None if no record matched the given
    ``request_id``.
    """
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM usage_events WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None

        if customer is None and charged is None:
            return dict(row)

        new_customer = customer if customer is not None else row["customer"]
        if charged is not None:
            new_charged = charged
            new_margin = round(charged - row["actual_cost"], 10)
        else:
            new_charged = row["charged"]
            new_margin = row["margin"]

        conn.execute(
            "UPDATE usage_events SET customer = ?, charged = ?, margin = ? "
            "WHERE request_id = ?",
            (new_customer, new_charged, new_margin, request_id),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM usage_events WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return dict(updated)
    finally:
        conn.close()


def query_by_customer(days: int | None = None, model: str | None = None,
                      db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        sql = (
            "SELECT customer, "
            "SUM(charged) as total_charged, "
            "SUM(actual_cost) as total_cost, "
            "SUM(margin) as total_margin, "
            "COUNT(*) as calls "
            "FROM usage_events WHERE 1=1"
        )
        params: list = []
        if days:
            sql += " AND timestamp >= datetime('now', ?)"
            params.append(f"-{days} days")
        if model:
            sql += " AND model = ?"
            params.append(model)
        sql += " GROUP BY customer ORDER BY total_margin DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_by_model(days: int | None = None, db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        sql = (
            "SELECT model, "
            "SUM(charged) as total_charged, "
            "SUM(actual_cost) as total_cost, "
            "SUM(margin) as total_margin, "
            "COUNT(*) as calls "
            "FROM usage_events WHERE 1=1"
        )
        params: list = []
        if days:
            sql += " AND timestamp >= datetime('now', ?)"
            params.append(f"-{days} days")
        sql += " GROUP BY model ORDER BY total_margin DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_all(days: int | None = None, model: str | None = None,
               db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        sql = "SELECT * FROM usage_events WHERE 1=1"
        params: list = []
        if days:
            sql += " AND timestamp >= datetime('now', ?)"
            params.append(f"-{days} days")
        if model:
            sql += " AND model = ?"
            params.append(model)
        sql += " ORDER BY timestamp DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def events_for_customer(
    customer: str,
    db_path: Path | None = None,
) -> list[dict]:
    """Return every event for a customer, oldest first.

    Uses ``rowid`` as a stable tiebreaker so timestamp ties produce the same
    ordering across runs (important for ``customer set-calls`` determinism).
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM usage_events WHERE customer = ? "
            "ORDER BY timestamp ASC, rowid ASC",
            (customer,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


_DELETE_CHUNK = 500


def delete_events(request_ids: list[str], db_path: Path | None = None) -> int:
    """Delete the given events. Returns the number of rows actually removed.

    The deletion is chunked to stay well below SQLite's ``IN (...)`` variable
    limit (default 999, sometimes lower on older builds) and runs as a single
    transaction so a partial failure rolls back cleanly.
    """
    if not request_ids:
        return 0
    conn = _connect(db_path)
    try:
        deleted = 0
        for start in range(0, len(request_ids), _DELETE_CHUNK):
            chunk = request_ids[start:start + _DELETE_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            cursor = conn.execute(
                f"DELETE FROM usage_events WHERE request_id IN ({placeholders})",  # noqa: S608
                tuple(chunk),
            )
            deleted += cursor.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()
