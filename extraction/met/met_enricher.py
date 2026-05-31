"""
Phase 3 (Section C): worklist-driven Met image enrichment, Snowflake-authoritative.

This is the Option B + PIPE-06 "hybrid" path (docs/context/met-deepdive.md PIPE-06,
PIPE-05, DDL-04/05; session-3-progress-log.md). It supersedes the legacy SQLite
image_enricher.py + snowflake_uploader.py pair for the Met source: state lives in
BRONZE.MET_ENRICHMENT_CONTROL, the queue is BRONZE.MET_WORKLIST, and the wide Bronze
row is assembled server-side from MET_CSV_SNAPSHOT x the fetched image block (the 47
descriptive columns are never shipped up -- they already live in Snowflake).

Run shape (short-lived Snowflake connections around a connection-free local fetch):
  1. CLAIM a bounded batch off MET_WORKLIST -> lease (committed immediately so an
     abandoned lease is durable for MET_LEASE_RECLAIM_TASK).
  2. FETCH image URLs from the Met API locally/async (no Snowflake connection held
     open during egress-bound work -- ARTWORK_WH AUTO_SUSPENDs anyway, so an idle
     connection would cost nothing, but we keep the pattern clean).
  3. STAGE the per-object image blocks -> TEMP table via PUT + COPY.
  4. ASSEMBLE done rows into RAW_MET_OBJECTS server-side (snapshot x staging).
  5. CALLBACK: one batch-grained UPDATE settles status + has_primary_image + clears
     the lease (PIPE-05: never per-row).
  6. AUTO-03: the run is recorded in BRONZE.EXTRACTION_LOG.
Assembly + callback commit together; on failure the lease is released so the batch
retries immediately.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import snowflake.connector

from .config import Config
from .db import load_sql
# Reuse the connection-free fetch primitives (rate limiter + single-object fetch).
from .image_enricher import _RateLimiter, _fetch_one
from .snowflake_uploader import _snowflake_connect

logger = logging.getLogger(__name__)

CLAIM_WORKLIST_SQL = load_sql("claim_worklist.sql")
COPY_INTO_ENRICH_STG_SQL = load_sql("copy_into_enrich_stg.sql")
ASSEMBLE_RAW_SQL = load_sql("assemble_raw_met_objects.sql")
CALLBACK_CONTROL_SQL = load_sql("callback_enrichment_control.sql")
RELEASE_LEASE_SQL = load_sql("release_lease.sql")

# Session-scoped staging table (auto-dropped on disconnect); CREATE TABLE on BRONZE.
_STG_TABLE = "MET_ENRICH_RESULT_STG"


def _log_start(cur: snowflake.connector.cursor.SnowflakeCursor, batch_id: str) -> None:
    """AUTO-03: open an EXTRACTION_LOG row for this enrich run."""
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
    """AUTO-03: close the EXTRACTION_LOG row with outcome + counts."""
    cur.execute(
        "UPDATE EXTRACTION_LOG SET completed_at = CURRENT_TIMESTAMP(), status = %s, "
        "records_loaded = %s, error_message = %s "
        "WHERE batch_id = %s AND status = 'running'",
        (status, records, error, batch_id),
    )


def _claim_batch(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    config: Config,
    batch_id: str,
    limit: Optional[int],
) -> List[int]:
    """Lease up to `limit` objects off the worklist; return the claimed object_ids."""
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    worklist = f"{config.snowflake_database}.{config.snowflake_schema}.MET_WORKLIST"
    limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
    cur.execute(CLAIM_WORKLIST_SQL.format(
        control=control, worklist=worklist, batch_id=batch_id, limit_clause=limit_clause,
    ))
    cur.execute(
        f"SELECT object_id FROM {control} WHERE claimed_by_batch = %s ORDER BY object_id",
        (batch_id,),
    )
    return [int(r[0]) for r in cur.fetchall()]


async def _fetch_images(config: Config, object_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch image blocks for the claimed ids (connection-free, async, rate-limited).

    Returns one dict per object: {object_id, status, primary_image,
    primary_image_small, additional_images}. status is 'done' | 'no_image' | 'error'.
    """
    rate_limiter = _RateLimiter(config.api_requests_per_second)
    semaphore = asyncio.Semaphore(config.api_max_concurrency)
    timeout = aiohttp.ClientTimeout(
        total=None, connect=15, sock_read=config.api_request_timeout_seconds,
    )
    headers = {"User-Agent": config.api_user_agent, "Accept": "application/json"}
    results: List[Dict[str, Any]] = []
    counters = {"done": 0, "no_image": 0, "error": 0}
    results_lock = asyncio.Lock()

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:

        async def worker(oid: int) -> None:
            async with semaphore:
                object_id, status, payload, _error = await _fetch_one(
                    session, rate_limiter, config.api_base, oid, config.api_max_retries,
                )
            if status == "done" and payload is not None:
                block = {
                    "object_id": object_id,
                    "status": "done",
                    "primary_image": payload.get("primaryImage") or None,
                    "primary_image_small": payload.get("primaryImageSmall") or None,
                    "additional_images": payload.get("additionalImages") or [],
                }
            else:
                block = {
                    "object_id": object_id,
                    "status": status,
                    "primary_image": None,
                    "primary_image_small": None,
                    "additional_images": [],
                }
            async with results_lock:
                results.append(block)
                counters[status] = counters.get(status, 0) + 1
                done = len(results)
                if done % 500 == 0:
                    logger.info(
                        "Fetch progress: %s/%s (done=%s no_image=%s error=%s)",
                        f"{done:,}", f"{len(object_ids):,}",
                        counters["done"], counters["no_image"], counters["error"],
                    )

        await asyncio.gather(*(worker(oid) for oid in object_ids))

    logger.info(
        "Fetch complete. done=%s no_image=%s error=%s",
        counters["done"], counters["no_image"], counters["error"],
    )
    return results


def _create_result_stg(cur: snowflake.connector.cursor.SnowflakeCursor) -> None:
    """Create the session-scoped enrich-result staging table."""
    cur.execute(
        f"CREATE TEMPORARY TABLE {_STG_TABLE} ("
        "  object_id           NUMBER  NOT NULL,"
        "  status              VARCHAR NOT NULL,"
        "  primary_image       VARCHAR,"
        "  primary_image_small VARCHAR,"
        "  additional_images   VARIANT"
        ")"
    )


def _stage_results(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    results: List[Dict[str, Any]],
    config: Config,
    batch_id: str,
) -> None:
    """Write image blocks as gzipped NDJSON, PUT to the stage, COPY into the TEMP table."""
    stage = f"@{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_stage}"
    with tempfile.TemporaryDirectory(prefix="met_enrich_") as tmp:
        target_dir = Path(tmp)
        chunk_size = config.upload_chunk_size
        chunk_index = 0
        for start in range(0, len(results), chunk_size):
            chunk = results[start:start + chunk_size]
            file_path = target_dir / f"met_enrich_{batch_id}_{chunk_index:05d}.ndjson.gz"
            with gzip.open(file_path, "wt", encoding="utf-8") as f:
                for block in chunk:
                    f.write(json.dumps(block, ensure_ascii=False))
                    f.write("\n")
            put_sql = (
                f"PUT file://{file_path.as_posix()} {stage}/met_enrich/{batch_id}/ "
                f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
            )
            logger.info("PUT %s -> %s/met_enrich/%s/", file_path.name, stage, batch_id)
            cur.execute(put_sql)
            cur.execute(COPY_INTO_ENRICH_STG_SQL.format(
                stg=_STG_TABLE, stage=stage, batch_id=batch_id, filename=file_path.name,
            ))
            chunk_index += 1


def _assemble_raw(
    cur: snowflake.connector.cursor.SnowflakeCursor, config: Config, batch_id: str,
) -> int:
    """MERGE done rows into RAW_MET_OBJECTS (snapshot x staging); return rows affected."""
    target = f"{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_table}"
    snapshot = f"{config.snowflake_database}.{config.snowflake_schema}.MET_CSV_SNAPSHOT"
    cur.execute(ASSEMBLE_RAW_SQL.format(
        target=target, snapshot=snapshot, stg=_STG_TABLE, batch_id=batch_id,
    ))
    result = cur.fetchone()
    # MERGE result: (inserted, updated); sum is the rows assembled into Bronze.
    inserted = int(result[0]) if result and len(result) > 0 else 0
    updated = int(result[1]) if result and len(result) > 1 else 0
    return inserted + updated


def _callback(cur: snowflake.connector.cursor.SnowflakeCursor, config: Config, batch_id: str) -> None:
    """Batch-grained status + lease-release UPDATE on the control table."""
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    cur.execute(CALLBACK_CONTROL_SQL.format(control=control, stg=_STG_TABLE, batch_id=batch_id))


def _release_lease(cur: snowflake.connector.cursor.SnowflakeCursor, config: Config, batch_id: str) -> None:
    """Failure path: free this batch's lease without altering enrichment_status."""
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    cur.execute(RELEASE_LEASE_SQL.format(control=control, batch_id=batch_id))


def enrich_met(config: Config, limit: Optional[int] = None) -> Dict[str, int]:
    """Claim, fetch, assemble, and settle one enrichment batch.

    Args:
        limit: max objects to claim+enrich this run (the batch bound). None = the
               entire current worklist.

    Returns counts: {claimed, assembled}. Per-status counts are logged.
    """
    batch_id = (
        f"met_enrich_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid.uuid4().hex[:6]}"
    )

    sf_conn = _snowflake_connect(config)
    cur = sf_conn.cursor()
    try:
        _log_start(cur, batch_id)
        sf_conn.commit()

        # 1. Claim a batch; commit the lease so it is durable for the reclaim task.
        claimed = _claim_batch(cur, config, batch_id, limit)
        sf_conn.commit()
        if not claimed:
            logger.info("Worklist empty -- nothing to enrich.")
            _log_finish(cur, batch_id, "success", 0)
            sf_conn.commit()
            return {"claimed": 0, "assembled": 0}
        logger.info("Claimed %s objects (batch_id=%s).", f"{len(claimed):,}", batch_id)

        try:
            # 2. Connection-free local fetch.
            results = asyncio.run(_fetch_images(config, claimed))

            # 3. Stage image blocks into a TEMP table.
            _create_result_stg(cur)
            _stage_results(cur, results, config, batch_id)

            # 4 + 5. Assemble Bronze + settle control in one transaction.
            assembled = _assemble_raw(cur, config, batch_id)
            _callback(cur, config, batch_id)
            _log_finish(cur, batch_id, "success", len(claimed))
            sf_conn.commit()

            logger.info(
                "Enrichment batch complete. batch_id=%s claimed=%s assembled=%s",
                batch_id, f"{len(claimed):,}", f"{assembled:,}",
            )
            return {"claimed": len(claimed), "assembled": assembled}
        except Exception as exc:
            # Free the lease so the batch retries immediately; record the failure.
            _release_lease(cur, config, batch_id)
            _log_finish(cur, batch_id, "failed", 0, str(exc)[:1000])
            sf_conn.commit()
            raise
    finally:
        cur.close()
        sf_conn.close()
