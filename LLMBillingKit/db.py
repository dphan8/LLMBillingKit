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


def insert_event(event: dict, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO usage_events "
            "(request_id, timestamp, customer, model, input_tokens, output_tokens, "
            "actual_cost, charged, margin) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event["request_id"],
                event["timestamp"],
                event["customer"],
                event["model"],
                event["input_tokens"],
                event["output_tokens"],
                event["actual_cost"],
                event["charged"],
                event["margin"],
            ),
        )
        conn.commit()
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
