"""Best-effort Snowflake scalar queries for asset attributes and checks.

Shared by both the asset factory and the check factory without importing each other.
Any failure (missing driver in a dev shell, no connectivity) is logged and swallowed for
display data, and surfaced as a WARN for checks -- it never crashes a materialization.

The connection comes from :mod:`artwork_orchestration._connection` (the shared dbt
profile), so this module is fully source-agnostic -- it does not import any museum's
extraction package.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ._connection import connect
from .config import BRONZE


def render(sql: str, partition_value: str = "") -> str:
    """Fill ``{db}``/``{schema}``/``{partition_value}`` tokens in a SourceSpec query.

    Uses ``str.replace`` (not ``str.format``) so literal braces elsewhere in the SQL
    are never misinterpreted. ``partition_value`` is single-quote-escaped because it
    is a data value interpolated into a WHERE clause.
    """
    return (
        sql.replace("{db}", BRONZE.database)
        .replace("{schema}", BRONZE.schema)
        .replace("{partition_value}", partition_value.replace("'", "''"))
    )


def sf_scalars(context, queries: Mapping[str, str]) -> Dict[str, Any]:
    """Run ``label -> SQL`` scalar queries; return ``{label: int_value}``.

    Best-effort: returns whatever succeeded, ``{}`` on connection/driver failure.
    """
    results: Dict[str, Any] = {}
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            for label, sql in queries.items():
                try:
                    cur.execute(sql)
                    row = cur.fetchone()
                    results[label] = int(row[0]) if row and row[0] is not None else 0
                except Exception as exc:  # per-query best-effort
                    context.log.warning("attribute query %r failed: %s", label, exc)
            cur.close()
        finally:
            conn.close()
    except Exception as exc:  # connection / driver best-effort
        context.log.warning("attribute collection skipped: %s", exc)
    return results


def sf_scalar(context, sql: str) -> Optional[int]:
    """Convenience: run a single scalar query; ``None`` if it could not be run."""
    return sf_scalars(context, {"_": sql}).get("_")
