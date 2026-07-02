"""
Bulk-upload enriched Met artworks to the Snowflake Bronze layer.

Strategy:
  1. Stream every row with enrichment_status='done' AND bronze_uploaded_at IS NULL
     out of SQLite.
  2. Build a JSON payload per row that combines the CSV-sourced descriptive
     fields and API-sourced image URLs under a single nested object.
  3. Write rows as gzipped newline-delimited JSON (NDJSON) to chunked local files.
  4. PUT each NDJSON file to the Bronze internal stage, then COPY INTO
     raw_met_objects with PARSE_JSON, mapping object_id, raw_payload, and
     _batch_id. _extracted_at and _source_system default at the table level.
  5. Mark uploaded rows with bronze_batch_id / bronze_uploaded_at so subsequent
     runs are fully idempotent.

This avoids the well-known write_pandas/VARIANT pitfalls by going through stage
+ COPY INTO, which is the canonical Snowflake bulk-load pattern for JSON.
"""
from __future__ import annotations

import gzip
import json
import logging
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import snowflake.connector

from .config import Config
from .db import connect, initialize_database, load_sql

logger = logging.getLogger(__name__)

# COPY INTO template lives in extraction/met/sql/copy_into_bronze.sql.
# Loaded once at import time; placeholders are filled in per chunk via str.format().
COPY_INTO_SQL = load_sql("copy_into_bronze.sql")

# Columns surfaced to Bronze under the "csv" sub-object of raw_payload.
_CSV_PAYLOAD_COLUMNS: Tuple[str, ...] = (
    "object_number", "is_highlight", "is_public_domain", "department",
    "accession_year", "object_name", "title", "culture", "period", "dynasty",
    "reign", "portfolio", "artist_role", "artist_display_name",
    "artist_display_bio", "artist_alpha_sort", "artist_nationality",
    "artist_begin_date", "artist_end_date", "artist_gender", "artist_ulan_url",
    "artist_wikidata_url", "object_date", "object_begin_date",
    "object_end_date", "medium", "dimensions", "credit_line", "geography_type",
    "city", "state", "county", "country", "region", "subregion", "locale",
    "locus", "excavation", "river", "classification",
    "rights_and_reproduction", "link_resource", "object_wikidata_url",
    "metadata_date", "repository", "tags", "tags_aat_url", "tags_wikidata_url",
)


def _iter_upload_rows(conn: sqlite3.Connection) -> Iterator[sqlite3.Row]:
    """Yield rows ready for Bronze upload (done, not yet uploaded)."""
    cur = conn.execute(
        "SELECT * FROM met_artworks "
        "WHERE enrichment_status = 'done' "
        "AND bronze_uploaded_at IS NULL "
        "ORDER BY object_id"
    )
    while True:
        rows = cur.fetchmany(5000)
        if not rows:
            return
        for row in rows:
            yield row


def _build_payload(row: sqlite3.Row, batch_id: str) -> Dict[str, Any]:
    """Build the JSON document stored in raw_payload (VARIANT)."""
    additional_raw = row["additional_image_urls"]
    try:
        additional = json.loads(additional_raw) if additional_raw else []
    except (TypeError, json.JSONDecodeError):
        additional = []

    csv_block = {col: row[col] for col in _CSV_PAYLOAD_COLUMNS}

    return {
        "object_id": row["object_id"],
        "csv":       csv_block,
        "api_images": {
            "primary_image":       row["primary_image_url"],
            "primary_image_small": row["primary_image_small_url"],
            "additional_images":   additional,
        },
        "_meta": {
            "source_system": "met_museum",
            "csv_loaded_at": row["csv_loaded_at"],
            "enriched_at":   row["enriched_at"],
            "batch_id":      batch_id,
        },
    }


def _write_ndjson_chunk(
    rows: List[sqlite3.Row],
    batch_id: str,
    chunk_index: int,
    target_dir: Path,
) -> Tuple[Path, List[int]]:
    """Write one gzipped NDJSON file; return its path and the object_ids it contains."""
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"met_bronze_{batch_id}_{chunk_index:05d}.ndjson.gz"
    object_ids: List[int] = []
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        for row in rows:
            payload = _build_payload(row, batch_id)
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")
            object_ids.append(row["object_id"])
    return file_path, object_ids


def _snowflake_connect(config: Config) -> snowflake.connector.SnowflakeConnection:
    """Open a Snowflake connection using key-pair auth.

    ARTWORK_LOADER_SVC is a TYPE = SERVICE user with no password; the connector
    authenticates with the private key registered by
    scripts/snowflake_cli/06_setup_loader_keypair.sh.
    """
    if not (config.snowflake_account and config.snowflake_user and config.snowflake_private_key_file):
        raise RuntimeError(
            "Snowflake credentials missing. Set SNOWFLAKE_ACCOUNT, "
            "SNOWFLAKE_USER, and SNOWFLAKE_PRIVATE_KEY_FILE (path to the loader "
            ".p8 private key) in your .env."
        )
    # The connector does not expand '~'; resolve it ourselves.
    private_key_file = str(Path(config.snowflake_private_key_file).expanduser())
    connect_kwargs: Dict[str, Any] = dict(
        account=config.snowflake_account,
        user=config.snowflake_user,
        private_key_file=private_key_file,
        role=config.snowflake_role,
        warehouse=config.snowflake_warehouse,
        database=config.snowflake_database,
        schema=config.snowflake_schema,
    )
    # Only set when the key is an encrypted PKCS#8 file.
    if config.snowflake_private_key_file_pwd:
        connect_kwargs["private_key_file_pwd"] = config.snowflake_private_key_file_pwd
    return snowflake.connector.connect(**connect_kwargs)


def _put_and_copy(
    sf_conn: snowflake.connector.SnowflakeConnection,
    file_path: Path,
    config: Config,
    batch_id: str,
) -> int:
    """PUT the local NDJSON file to the stage, then COPY INTO Bronze.

    Returns the number of rows loaded according to COPY INTO's result.
    """
    stage = f"@{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_stage}"
    table = f"{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_table}"

    cur = sf_conn.cursor()
    try:
        # 1. Upload the gzipped NDJSON to the internal stage.
        #    AUTO_COMPRESS=FALSE because the file is already gzipped.
        put_sql = (
            f"PUT file://{file_path.as_posix()} {stage}/met/{batch_id}/ "
            f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        )
        logger.info("PUT %s -> %s/met/%s/", file_path.name, stage, batch_id)
        cur.execute(put_sql)

        # 2. Load JSON rows into raw_met_objects. PARSE_JSON happens implicitly
        #    via the JSON file format; we extract object_id from the payload
        #    and supply _batch_id directly. PURGE=TRUE removes the staged file
        #    on success so the stage stays clean. SQL body lives in
        #    extraction/met/sql/copy_into_bronze.sql.
        copy_sql = COPY_INTO_SQL.format(
            table=table,
            stage=stage,
            batch_id=batch_id,
            filename=file_path.name,
        )
        logger.info("COPY INTO %s (batch_id=%s)", table, batch_id)
        cur.execute(copy_sql)
        result = cur.fetchall()
        # COPY INTO result columns: file, status, rows_parsed, rows_loaded, ...
        # Index 3 is rows_loaded.
        rows_loaded = sum(int(r[3]) for r in result) if result else 0
        return rows_loaded
    finally:
        cur.close()


def _mark_uploaded(
    conn: sqlite3.Connection,
    object_ids: List[int],
    batch_id: str,
) -> None:
    """Update SQLite so uploaded rows are not re-sent on the next run."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "UPDATE met_artworks "
        "SET bronze_batch_id = ?, bronze_uploaded_at = ? "
        "WHERE object_id = ?",
        [(batch_id, now_iso, oid) for oid in object_ids],
    )
    conn.commit()


def upload(config: Config) -> int:
    """Upload every fully-enriched, not-yet-uploaded row to Snowflake Bronze.

    Returns the total number of rows uploaded across all chunks.
    """
    initialize_database(config.sqlite_path)

    batch_id = (
        f"met_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    run_started = datetime.now(timezone.utc).isoformat()
    run_id = uuid.uuid4().hex[:12]
    total_uploaded = 0

    with connect(config.sqlite_path) as sqlite_conn:
        sqlite_conn.execute(
            "INSERT INTO extraction_runs (run_id, phase, started_at, status) "
            "VALUES (?, 'upload', ?, 'running')",
            (run_id, run_started),
        )
        sqlite_conn.commit()

        try:
            sf_conn = _snowflake_connect(config)
            try:
                with tempfile.TemporaryDirectory(prefix="met_bronze_") as tmp:
                    target_dir = Path(tmp)
                    chunk_index = 0
                    chunk: List[sqlite3.Row] = []
                    for row in _iter_upload_rows(sqlite_conn):
                        chunk.append(row)
                        if len(chunk) >= config.upload_chunk_size:
                            file_path, ids = _write_ndjson_chunk(
                                chunk, batch_id, chunk_index, target_dir,
                            )
                            loaded = _put_and_copy(sf_conn, file_path, config, batch_id)
                            _mark_uploaded(sqlite_conn, ids, batch_id)
                            total_uploaded += loaded
                            logger.info(
                                "Uploaded chunk %s: %s rows (total %s)",
                                chunk_index, loaded, f"{total_uploaded:,}",
                            )
                            chunk_index += 1
                            chunk.clear()
                    if chunk:
                        file_path, ids = _write_ndjson_chunk(
                            chunk, batch_id, chunk_index, target_dir,
                        )
                        loaded = _put_and_copy(sf_conn, file_path, config, batch_id)
                        _mark_uploaded(sqlite_conn, ids, batch_id)
                        total_uploaded += loaded
                        logger.info(
                            "Uploaded final chunk %s: %s rows (total %s)",
                            chunk_index, loaded, f"{total_uploaded:,}",
                        )
            finally:
                sf_conn.close()

            sqlite_conn.execute(
                "UPDATE extraction_runs SET completed_at=?, status='success', "
                "records_processed=?, notes=? WHERE run_id=?",
                (
                    datetime.now(timezone.utc).isoformat(),
                    total_uploaded,
                    json.dumps({"batch_id": batch_id}),
                    run_id,
                ),
            )
            sqlite_conn.commit()
        except Exception as exc:
            sqlite_conn.execute(
                "UPDATE extraction_runs SET completed_at=?, status='failed', "
                "records_processed=?, notes=? WHERE run_id=?",
                (
                    datetime.now(timezone.utc).isoformat(),
                    total_uploaded,
                    str(exc),
                    run_id,
                ),
            )
            sqlite_conn.commit()
            raise

    logger.info(
        "Bronze upload complete. batch_id=%s rows=%s",
        batch_id, total_uploaded,
    )
    return total_uploaded
