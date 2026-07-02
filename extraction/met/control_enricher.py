"""
Phase 3 -- Snowflake-authoritative Met enrichment (lease-claim -> local fetch ->
server-side Bronze assembly -> status callback). This is the Option-B / PIPE-06
replacement for the legacy SQLite enrich+upload pair.

One `enrich` invocation drains MET_WORKLIST in bounded batches. Per batch:
  1. CLAIM  -- lease the top {batch_size} prioritized object_ids (claim_worklist.sql),
             then read back exactly the rows this batch owns.
  2. FETCH  -- locally, connection-free, call the Met API for each claimed object
             (reusing image_enricher._fetch_one + _RateLimiter). Only the small image
             block crosses the wire; the 47 CSV columns stay in Snowflake (Option B).
  3. STAGE  -- write one JSON block per object, PUT to the Bronze stage, COPY into a
             session TEMPORARY table.
  4. ASSEMBLE -- MERGE RAW_MET_OBJECTS = MET_CSV_SNAPSHOT x image block, server-side,
             for 'done' rows only (assemble_raw_met_objects.sql).
  5. CALLBACK -- MERGE every claimed row's outcome into MET_ENRICHMENT_CONTROL and
             release the lease (callback_enrichment_control.sql).
  6. AUTO-03 -- record the batch in BRONZE.EXTRACTION_LOG.

Why short-lived connections around a connection-free fetch (PIPE-06 hybrid): the
API fetch is egress-bound and must run on the Mac; ARTWORK_WH is X-Small with
AUTO_SUSPEND=60 / AUTO_RESUME=true, so an idle connection during the fetch costs
nothing. Resumability: a crash mid-batch leaves rows leased; MET_LEASE_RECLAIM_TASK
frees them after the 30-min TTL, and re-running `enrich` picks them back up.
"""
from __future__ import annotations

import gzip
import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import snowflake.connector

from .config import Config
from .db import load_sql, strip_sql_comments
from .image_enricher import _RateLimiter, _ThrottleGate, _fetch_one
from .snowflake_uploader import _snowflake_connect

logger = logging.getLogger(__name__)

CLAIM_WORKLIST_SQL = strip_sql_comments(load_sql("claim_worklist.sql"))
COPY_INTO_BLOCK_STG_SQL = load_sql("copy_into_image_block_stg.sql")
ASSEMBLE_RAW_SQL = load_sql("assemble_raw_met_objects.sql")
CALLBACK_CONTROL_SQL = load_sql("callback_enrichment_control.sql")

# Session-scoped staging table for one batch of image blocks (auto-dropped on
# disconnect; TRUNCATEd between batches). Needs only the loader's CREATE TABLE on
# BRONZE, so it stays out of make iac.
_STG_TABLE = "MET_IMAGE_BLOCK_STG"


# --------------------------------------------------------------------------- diag
def _classify_error(msg: Optional[str]) -> str:
    """P-D2: bucket a per-row enrichment_error string into a stable error class.

    The class names are the labels that show up in the per-batch histogram log.
    Buckets are derived from the shapes _fetch_one (image_enricher.py) emits:
      - "HTTP <status>: <body>"      non-retryable 4xx other than 404 -> http_4xx_<code>
                                     non-retryable 5xx (rare path)    -> http_5xx_<code>
      - "HTTP <status>"              retry-exhausted 429/5xx          -> http_<class>_<code>
      - "ConnectionError: ..."                                        -> connect
      - "ConnectTimeout: ..."                                         -> connect
      - "Timeout: ..." / "ReadTimeout: ..."                           -> timeout
      - "ChunkedEncodingError: ..."                                   -> payload
      - "ContentDecodingError: ..." / "JSONDecodeError: ..."          -> parse
      - "max retries exceeded"                                        -> retries_exhausted
      - everything else                                               -> other:<head>
    The bucket is intentionally low-cardinality: it shows up unsorted in INFO logs,
    so we want a tight enum, not a free-text histogram.
    """
    if not msg:
        return "none"
    if msg.startswith("HTTP "):
        # Either "HTTP 410: <body>" or "HTTP 503". Either way: "HTTP {code}..."
        rest = msg[5:]
        # Code is digits up to the first non-digit (':' or end-of-string).
        code = ""
        for ch in rest:
            if ch.isdigit():
                code += ch
            else:
                break
        if code:
            klass = "4xx" if code.startswith("4") else ("5xx" if code.startswith("5") else "xxx")
            return f"http_{klass}_{code}"
        return "http_unknown"
    # requests.ConnectionError or its subclass ConnectTimeout (which is also a Timeout).
    if msg.startswith("ConnectionError") or msg.startswith("ConnectTimeout"):
        return "connect"
    # requests.Timeout and its subclasses: ReadTimeout, ConnectTimeout (caught above).
    if "Timeout" in msg.split(":", 1)[0]:
        return "timeout"
    if msg.startswith("ChunkedEncodingError"):
        return "payload"
    if msg.startswith("ContentDecodingError") or msg.startswith("JSONDecodeError"):
        return "parse"
    if msg == "max retries exceeded":
        return "retries_exhausted"
    # Last resort: keep the leading exception class for visibility, drop the body.
    head = msg.split(":", 1)[0]
    return f"other:{head[:32]}"


def _histogram(blocks: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return {error_class: count} over the rows whose status == 'error'."""
    hist: Dict[str, int] = {}
    for b in blocks:
        if b.get("enrichment_status") != "error":
            continue
        klass = _classify_error(b.get("enrichment_error"))
        hist[klass] = hist.get(klass, 0) + 1
    return hist


# --------------------------------------------------------------------------- claim
def _claim_batch(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    config: Config,
    batch_id: str,
    batch_size: int,
    department: Optional[str] = None,
) -> List[int]:
    """Lease up to batch_size prioritized rows; return the claimed object_ids.

    When `department` is given, the claim is narrowed to that department slice so
    that concurrent workers (one per department partition) lease DISJOINT rows and
    never collide -- the lease already guarantees safety, the filter just partitions
    the worklist so throughput can be spread across departments.
    """
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    worklist = f"{config.snowflake_database}.{config.snowflake_schema}.MET_WORKLIST"
    # batch_id ALWAYS binds first (SET clause); department binds second when present
    # (subquery WHERE). Order matches the %s appearance order in claim_worklist.sql.
    if department is not None:
        dept_filter = "WHERE department = %s"
        params: Tuple[Any, ...] = (batch_id, department)
    else:
        dept_filter = ""
        params = (batch_id,)
    cur.execute(
        CLAIM_WORKLIST_SQL.format(
            control=control, worklist=worklist, limit=int(batch_size), dept_filter=dept_filter,
        ),
        params,
    )
    cur.execute(
        f"SELECT object_id FROM {control} WHERE claimed_by_batch = %s ORDER BY object_id",
        (batch_id,),
    )
    return [int(r[0]) for r in cur.fetchall()]


# --------------------------------------------------------------------------- fetch
def _fetch_blocks(
    config: Config,
    object_ids: List[int],
    progress_every: int = 100,
    processed_offset: int = 0,
    total_label: str = "?",
) -> Tuple[List[Dict[str, Any]], _RateLimiter]:
    """Fetch image data for the claimed ids via synchronous requests.

    Returns (blocks, rate_limiter). The limiter is returned so the caller can
    read its throttle counters into the per-batch INFO log -- P-T2.

    Emits a live "Progress" INFO line every `progress_every` completed API calls
    so the operator sees the running enriched total advance during the fetch.
    `processed_offset` is the count already done in prior batches and `total_label`
    the worklist denominator, so the line reads e.g. `Progress: 300/1,827 done=.. no_image=..`.
    """
    rate_limiter = _RateLimiter(config.api_requests_per_second)
    throttle_gate = _ThrottleGate()
    timeout = float(config.api_request_timeout_seconds)
    blocks: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {"done": 0, "no_image": 0, "error": 0}

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.api_user_agent,
        "Accept": "application/json",
    })
    try:
        for oid in object_ids:
            object_id, status, payload, error = _fetch_one(
                session, rate_limiter, throttle_gate,
                config.api_base, oid, config.api_max_retries,
                timeout=timeout,
            )
            additional = (payload or {}).get("additionalImages") or [] if payload else []
            block = {
                "object_id":           object_id,
                "enrichment_status":   status,            # done | no_image | error
                "has_primary_image":   status == "done",
                "primary_image":       (payload or {}).get("primaryImage") if payload else None,
                "primary_image_small": (payload or {}).get("primaryImageSmall") if payload else None,
                "additional_images":   additional,
                "enrichment_error":    (error or "")[:500] or None,
            }
            blocks.append(block)
            counts[status] = counts.get(status, 0) + 1
            done_in_batch = len(blocks)
            # Live heartbeat: log as each Nth API call completes.
            if done_in_batch % progress_every == 0:
                logger.info(
                    "Progress: %s/%s done=%s no_image=%s error=%s",
                    f"{processed_offset + done_in_batch:,}", total_label,
                    counts["done"], counts["no_image"], counts["error"],
                )
    finally:
        session.close()

    return blocks, rate_limiter


# --------------------------------------------------------------------------- stage
def _write_blocks_ndjson(blocks: List[Dict[str, Any]], batch_id: str, target_dir: Path) -> Path:
    """Write the batch's image blocks as one gzipped NDJSON file; return its path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"met_enrich_{batch_id}.ndjson.gz"
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        for block in blocks:
            f.write(json.dumps(block, ensure_ascii=False))
            f.write("\n")
    return file_path


def _stage_blocks(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    file_path: Path,
    config: Config,
    batch_id: str,
) -> None:
    """PUT the NDJSON file to the stage and COPY it into the TEMP staging table."""
    stage = f"@{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_stage}"
    cur.execute(f"TRUNCATE TABLE {_STG_TABLE}")
    cur.execute(
        f"PUT file://{file_path.as_posix()} {stage}/met_enrich/{batch_id}/ "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    )
    cur.execute(
        COPY_INTO_BLOCK_STG_SQL.format(
            stg=_STG_TABLE, stage=stage, batch_id=batch_id, filename=file_path.name,
        )
    )


# ------------------------------------------------------------------ assemble/callback
def _assemble_and_callback(
    cur: snowflake.connector.cursor.SnowflakeCursor, config: Config, batch_id: str,
) -> int:
    """Server-side assemble RAW_MET_OBJECTS, then callback the control table.

    Returns the number of Bronze rows assembled (inserted + updated 'done' rows).
    """
    raw = f"{config.snowflake_database}.{config.snowflake_schema}.RAW_MET_OBJECTS"
    snapshot = f"{config.snowflake_database}.{config.snowflake_schema}.MET_CSV_SNAPSHOT"
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"

    cur.execute(ASSEMBLE_RAW_SQL.format(raw=raw, snapshot=snapshot, stg=_STG_TABLE, batch_id=batch_id))
    result = cur.fetchone()
    inserted = int(result[0]) if result and len(result) > 0 else 0
    updated = int(result[1]) if result and len(result) > 1 else 0

    cur.execute(CALLBACK_CONTROL_SQL.format(control=control, stg=_STG_TABLE))
    return inserted + updated


# --------------------------------------------------------------------------- log
def _log_start(cur: snowflake.connector.cursor.SnowflakeCursor, batch_id: str) -> None:
    """AUTO-03: open an EXTRACTION_LOG row for one enrich batch."""
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


def _release_unfinished(
    cur: snowflake.connector.cursor.SnowflakeCursor, config: Config, batch_id: str,
) -> None:
    """Best-effort: free any rows still leased to a failed batch so they re-queue."""
    control = f"{config.snowflake_database}.{config.snowflake_schema}.MET_ENRICHMENT_CONTROL"
    cur.execute(
        f"UPDATE {control} SET claimed_by_batch = NULL, claimed_at = NULL "
        f"WHERE claimed_by_batch = %s",
        (batch_id,),
    )


# --------------------------------------------------------------------------- driver
def _process_one_batch(
    sf_conn: snowflake.connector.SnowflakeConnection, config: Config, batch_size: int,
    progress_every: int = 100, processed_offset: int = 0, total_label: str = "?",
    department: Optional[str] = None,
) -> Tuple[int, Dict[str, int]]:
    """Claim, fetch, assemble, and callback one batch.

    Returns (claimed_count, status_counts). claimed_count == 0 means the worklist is
    drained (caller stops). `processed_offset`/`total_label` thread through to the
    live per-fetch progress line emitted inside `_fetch_blocks`. `department`, when
    given, narrows the claim to a single department partition.
    """
    batch_id = (
        f"met_enrich_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    cur = sf_conn.cursor()
    try:
        claimed = _claim_batch(cur, config, batch_id, batch_size, department)
        if not claimed:
            sf_conn.commit()
            return 0, {}

        _log_start(cur, batch_id)
        try:
            blocks, rate_limiter = _fetch_blocks(
                config, claimed, progress_every, processed_offset, total_label
            )
            counts: Dict[str, int] = {"done": 0, "no_image": 0, "error": 0}
            for b in blocks:
                counts[b["enrichment_status"]] = counts.get(b["enrichment_status"], 0) + 1

            with tempfile.TemporaryDirectory(prefix="met_enrich_") as tmp:
                fp = _write_blocks_ndjson(blocks, batch_id, Path(tmp))
                _stage_blocks(cur, fp, config, batch_id)

            assembled = _assemble_and_callback(cur, config, batch_id)
            _log_finish(cur, batch_id, "success", assembled)
            sf_conn.commit()
            # P-D2: per-batch error histogram alongside the status counts so the
            # failure modes show up in the same INFO line we already write.
            # P-T2: throttle counters from the rate limiter so the operator can
            # tell "104 went error because of 403 throttling that ran out of
            # retries" from "104 went error because the API returned bad data".
            hist = _histogram(blocks)
            hist_repr = (
                "{" + ", ".join(
                    f"{k!r}: {v}"
                    for k, v in sorted(hist.items(), key=lambda kv: -kv[1])
                ) + "}"
            ) if hist else "{}"
            logger.debug(
                "Batch %s: claimed=%s done=%s no_image=%s error=%s assembled=%s "
                "err_breakdown=%s throttles={'403': %s, '429': %s, 'other': %s} "
                "backoff_s=%.1f rps_end=%.2f",
                batch_id, len(claimed), counts["done"], counts["no_image"],
                counts["error"], assembled, hist_repr,
                rate_limiter.throttle_403, rate_limiter.throttle_429,
                rate_limiter.throttle_other, rate_limiter.backoff_seconds,
                rate_limiter.rps,
            )
            return len(claimed), counts
        except Exception as exc:
            _log_finish(cur, batch_id, "failed", 0, str(exc)[:1000])
            _release_unfinished(cur, config, batch_id)
            sf_conn.commit()
            raise
    finally:
        cur.close()


def _create_staging_table(sf_conn: snowflake.connector.SnowflakeConnection) -> None:
    """Create the session-scoped image-block staging table once per connection."""
    cur = sf_conn.cursor()
    try:
        cur.execute(
            f"CREATE TEMPORARY TABLE IF NOT EXISTS {_STG_TABLE} ("
            "  object_id NUMBER  NOT NULL,"
            "  block     VARIANT NOT NULL"
            ")"
        )
    finally:
        cur.close()


def enrich_from_control(
    config: Config,
    batch_size: int = 2000,
    max_batches: Optional[int] = None,
    progress_every: int = 100,
    total_expected: Optional[int] = None,
    department: Optional[str] = None,
) -> Dict[str, int]:
    """Drain MET_WORKLIST in bounded batches. Returns aggregate status counts.

    Args:
        batch_size:   rows leased + fetched per batch.
        max_batches:  stop after this many batches (None = drain the whole worklist).
        progress_every: emit one INFO progress line every N items processed.
        total_expected: if known, show "X/total" in progress lines; otherwise "X/?".
        department:   restrict claiming to a single department slice (partition). When
                      set, concurrent per-department workers process DISJOINT rows.
    """
    totals: Dict[str, int] = {"done": 0, "no_image": 0, "error": 0, "claimed": 0}
    total_label = f"{total_expected:,}" if total_expected else "?"

    sf_conn = _snowflake_connect(config)
    try:
        _create_staging_table(sf_conn)
        # Query the worklist size for the progress denominator if not provided.
        if total_expected is None:
            cur = sf_conn.cursor()
            try:
                worklist = f"{config.snowflake_database}.{config.snowflake_schema}.MET_WORKLIST"
                if department is not None:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {worklist} WHERE department = %s",
                        (department,),
                    )
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {worklist}")
                row = cur.fetchone()
                total_label = f"{int(row[0]):,}" if row else "?"
            finally:
                cur.close()

        batch_no = 0
        while max_batches is None or batch_no < max_batches:
            # Progress now streams live from inside _fetch_blocks as each API call
            # completes; pass the running offset + denominator so the line reads
            # against the whole worklist (e.g. "300/1,827").
            claimed, counts = _process_one_batch(
                sf_conn, config, batch_size,
                progress_every=progress_every,
                processed_offset=totals["claimed"],
                total_label=total_label,
                department=department,
            )
            if claimed == 0:
                break
            totals["claimed"] += claimed
            for k in ("done", "no_image", "error"):
                totals[k] += counts.get(k, 0)
            batch_no += 1
    finally:
        sf_conn.close()

    logger.info(
        "Enrichment complete%s. claimed=%s done=%s no_image=%s error=%s",
        f" (department={department!r})" if department else "",
        f"{totals['claimed']:,}", totals["done"], totals["no_image"], totals["error"],
    )
    return totals
