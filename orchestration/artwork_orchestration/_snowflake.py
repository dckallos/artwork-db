"""
Best-effort Snowflake scalar queries for asset attributes and checks.

Shared by both the asset factory and the check factory without importing each other.
Any failure (missing driver in a dev shell, no connectivity) is logged and swallowed for
display data, and surfaced as a WARN for checks -- it never crashes a materialization.

The connection comes from :mod:`artwork_orchestration._connection` (the shared dbt
profile), so this module is fully source-agnostic -- it does not import any museum's
extraction package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

from ._connection import connect
from .config import BRONZE


@dataclass(frozen=True)
class ScalarResults:
    """
    Typed result of a batch of ``label -> scalar`` queries.

    Replaces the bare ``dict`` previously returned by :func:`sf_scalars`. Supports the
    mapping operations the factories rely on -- ``in``, ``results[label]``,
    ``results.get(label)``, and ``{**results}`` unpacking into metadata -- while also
    recording which labels failed to run (best-effort collection).
    """

    values: Mapping[str, int] = field(default_factory=dict)
    failed: Tuple[str, ...] = ()

    def keys(self):
        return self.values.keys()

    def get(self, label: str, default: Any = None) -> Any:
        return self.values.get(label, default)

    def __contains__(self, label: object) -> bool:
        return label in self.values

    def __getitem__(self, label: str) -> int:
        return self.values[label]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def render(sql: str, partition_value: str = "") -> str:
    """
    Fill ``{db}``/``{schema}``/``{partition_value}`` tokens in a SourceSpec query.

    Uses ``str.replace`` (not ``str.format``) so literal braces elsewhere in the SQL
    are never misinterpreted. ``partition_value`` is single-quote-escaped because it
    is a data value interpolated into a WHERE clause.
    """
    return (
        sql.replace("{db}", BRONZE.database)
        .replace("{schema}", BRONZE.schema)
        .replace("{partition_value}", partition_value.replace("'", "''"))
    )


def sf_scalars(context, queries: Mapping[str, str]) -> ScalarResults:
    """
    Run ``label -> SQL`` scalar queries; return a :class:`ScalarResults`.

    Best-effort: returns whatever succeeded (with the failed labels recorded), or an
    empty result on connection/driver failure.
    """
    results: Dict[str, int] = {}
    failed: list = []
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
                    failed.append(label)
                    context.log.warning("attribute query %r failed: %s", label, exc)
            cur.close()
        finally:
            conn.close()
    except Exception as exc:  # connection / driver best-effort
        failed = list(queries.keys())
        context.log.warning("attribute collection skipped: %s", exc)
    return ScalarResults(values=results, failed=tuple(failed))


def sf_scalar(context, sql: str) -> Optional[int]:
    """
    Convenience: run a single scalar query; ``None`` if it could not be run.
    """
    return sf_scalars(context, {"_": sql}).get("_")
