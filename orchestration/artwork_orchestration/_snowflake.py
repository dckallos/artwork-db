"""Best-effort Snowflake scalar queries for asset metadata and checks.

Moved out of ``assets_extraction`` so both the asset factory and the check factory
share it without importing each other (breaks the old observability -> assets
coupling). Any failure (missing driver in a dev shell, no connectivity) is logged
and swallowed for metadata, and surfaced as a WARN for checks -- it never crashes a
materialization.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, Mapping, Optional

from .config import BRONZE, REPO_ROOT


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

    Lazily imports the extraction package (importable because assets already shell
    ``python -m extraction...`` from REPO_ROOT). Best-effort: returns whatever
    succeeded, ``{}`` on connection/import failure.
    """
    results: Dict[str, Any] = {}
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from extraction.met.config import Config  # type: ignore
        from extraction.met.snowflake_uploader import _snowflake_connect  # type: ignore

        conn = _snowflake_connect(Config())
        try:
            cur = conn.cursor()
            for label, sql in queries.items():
                try:
                    cur.execute(sql)
                    row = cur.fetchone()
                    results[label] = int(row[0]) if row and row[0] is not None else 0
                except Exception as exc:  # per-query best-effort
                    context.log.warning("metadata query %r failed: %s", label, exc)
            cur.close()
        finally:
            conn.close()
    except Exception as exc:  # connection / import best-effort
        context.log.warning("metadata collection skipped: %s", exc)
    return results


def sf_scalar(context, sql: str) -> Optional[int]:
    """Convenience: run a single scalar query; ``None`` if it could not be run."""
    return sf_scalars(context, {"_": sql}).get("_")
