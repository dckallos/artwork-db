"""
Phase 2 -- seed BRONZE.MET_ENRICHMENT_CONTROL for a bounded slice of the snapshot.

The full Met collection lands cheaply in MET_CSV_SNAPSHOT (Option B); the COSTLY
work (the per-object API enrichment) is bounded HERE, at the control seed. You pick
a slice -- a department, public-domain only, a highlight subset, or an arbitrary
predicate over the snapshot's VARIANT -- and this inserts one 'pending' control row
per matching object. MET_WORKLIST (control x snapshot) then lights up with exactly
those rows, prioritized, for the enricher to drain.

Design (docs/context/met-deepdive.md DDL-04, PIPE-05):
  - State authority is Snowflake: the control table is the system of record for
    enrichment state. This seed is the only thing that decides "what to work".
  - Idempotent + incremental: MERGE WHEN NOT MATCHED means re-seeding a slice (or
    widening it later) never disturbs rows already pending / leased / done.
  - Injection-safe: the department / arbitrary value travels as a bind parameter;
    only validated identifiers and an int LIMIT are formatted into the SQL text.
  - AUTO-03: the run is recorded in BRONZE.EXTRACTION_LOG (running -> success/failed)
    with a 'met_seed_*' batch_id.

This opens a short-lived Snowflake connection (loader key-pair) and runs one MERGE;
no API calls, no local state.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import snowflake.connector

from .config import Config
from .db import load_sql, strip_sql_comments
from .snowflake_uploader import _snowflake_connect

logger = logging.getLogger(__name__)

SEED_CONTROL_SQL = load_sql("seed_enrichment_control.sql")


def _build_predicate(
    department: Optional[str],
    public_domain_only: bool,
    highlight_only: bool,
    where: Optional[str],
) -> Tuple[str, List[object]]:
    """Compose the slice WHERE predicate over the snapshot VARIANT.

    Returns (predicate_sql, bind_params). The department / no caller-free value is
    ever interpolated into the SQL string -- it is bound via %s. The optional raw
    `where` is an explicit owner-supplied escape hatch (e.g. a culture/period
    filter) and is the ONLY place free SQL text enters; document that responsibility
    at the call site / CLI help.
    """
    parts: List[str] = []
    params: List[object] = []

    if public_domain_only:
        parts.append("raw_payload:is_public_domain::BOOLEAN = TRUE")
    if highlight_only:
        parts.append("raw_payload:is_highlight::BOOLEAN = TRUE")
    if department:
        parts.append("raw_payload:department::STRING = %s")
        params.append(department)
    if where:
        parts.append(f"({where})")

    if not parts:
        # No slice at all would seed the entire collection (~485k pending rows) and
        # unbound the costly enrichment -- exactly what Phase 2 exists to prevent.
        raise ValueError(
            "Refusing to seed an unbounded slice. Pass at least one of "
            "--department / --public-domain-only / --highlight-only / --where "
            "(use --where TRUE only if you really mean the whole collection)."
        )
    return " AND ".join(parts), params


def _log_start(cur: snowflake.connector.cursor.SnowflakeCursor, batch_id: str) -> None:
    """AUTO-03: open an EXTRACTION_LOG row for this seed run."""
    cur.execute(
        "INSERT INTO EXTRACTION_LOG (source_system, batch_id, started_at, status) "
        "VALUES ('met_museum', %s, CURRENT_TIMESTAMP(), 'running')",
        (batch_id,),
    )


def _log_finish(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    batch_id: str,
    status: str,
    records: int,
    error: Optional[str] = None,
) -> None:
    """AUTO-03: close the EXTRACTION_LOG row with outcome + count."""
    cur.execute(
        "UPDATE EXTRACTION_LOG SET completed_at = CURRENT_TIMESTAMP(), status = %s, "
        "records_loaded = %s, error_message = %s "
        "WHERE batch_id = %s AND status = 'running'",
        (status, records, error, batch_id),
    )


def seed_control(
    config: Config,
    department: Optional[str] = None,
    public_domain_only: bool = False,
    highlight_only: bool = False,
    where: Optional[str] = None,
    limit: Optional[int] = None,
) -> int:
    """Seed MET_ENRICHMENT_CONTROL with 'pending' rows for the chosen slice.

    Returns the number of NEW control rows inserted (already-present object_ids are
    left untouched, so a re-seed returns 0).
    """
    predicate, params = _build_predicate(department, public_domain_only, highlight_only, where)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    snapshot = f"{config.snowflake_database}.{config.snowflake_schema}.MET_CSV_SNAPSHOT"
    # Strip -- comments BEFORE binding: the connector pyformat-binds the whole
    # command string, so any stray % in a comment would break `command % params`
    # (see db.strip_sql_comments). The real %s bind in {predicate} survives.
    sql = strip_sql_comments(SEED_CONTROL_SQL).format(
        control=control, snapshot=snapshot, predicate=predicate, limit=limit_clause,
    )

    batch_id = (
        f"met_seed_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    logger.info(
        "Seeding control: predicate=[%s] params=%s limit=%s", predicate, params, limit,
    )

    sf_conn = _snowflake_connect(config)
    cur = sf_conn.cursor()
    try:
        _log_start(cur, batch_id)
        try:
            cur.execute(sql, params)
            result = cur.fetchone()
            # MERGE with only WHEN NOT MATCHED returns one column: rows inserted.
            inserted = int(result[0]) if result and len(result) > 0 else 0
            _log_finish(cur, batch_id, "success", inserted)
            sf_conn.commit()
            logger.info(
                "Control seed complete. batch_id=%s inserted=%s (existing rows untouched)",
                batch_id, f"{inserted:,}",
            )
            return inserted
        except Exception as exc:
            _log_finish(cur, batch_id, "failed", 0, str(exc)[:1000])
            sf_conn.commit()
            raise
    finally:
        cur.close()
        sf_conn.close()
