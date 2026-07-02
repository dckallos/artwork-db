"""
Land the full Met OpenAccess CSV into BRONZE.MET_CSV_SNAPSHOT (Option B).

This is the Snowflake-authoritative descriptive truth for the enrichment worklist
(docs/context/met-deepdive.md DDL-05, PIPE-05). It is intentionally INDEPENDENT of
the SQLite bootstrap path: under Option B the 47 CSV descriptive columns live only
in Snowflake, RAW_MET_OBJECTS is assembled server-side from the snapshot x the
fetched image block, and SQLite is demoted to disposable per-batch fetch scratch.

Strategy (cheap: no API calls, one COPY+MERGE):
  1. Download + DATA-06-validate the CSV (shared guard in csv_bootstrap).
  2. Stream rows, mapping each to a faithful snake_case JSON document (one VARIANT
     row per Object ID; raw string values, empty -> null).
  3. Write gzipped NDJSON chunks, PUT each to the Bronze stage, COPY INTO a
     TEMPORARY staging table.
  4. MERGE the staging table into MET_CSV_SNAPSHOT keyed on object_id (PK 1:1
     guarantee + idempotent re-runs + DATA-01 diff substrate).
  5. AUTO-03: record the run in BRONZE.EXTRACTION_LOG (running -> success/failed).

The bound on a first seed lives downstream in the CONTROL seed, not here: the
snapshot is the full collection so the profile SQL can rank every department.
"""
from __future__ import annotations

import gzip
import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import snowflake.connector

from .config import Config
from .csv_bootstrap import assert_real_met_csv, download_csv, _iter_csv_rows
from .db import load_sql
from .snowflake_uploader import _snowflake_connect

logger = logging.getLogger(__name__)

COPY_INTO_STG_SQL = load_sql("copy_into_snapshot_stg.sql")
MERGE_SNAPSHOT_SQL = load_sql("merge_csv_snapshot.sql")

# Session-scoped staging table (auto-dropped on disconnect); needs the loader's
# CREATE TABLE on BRONZE only -- no persistent infra, so it stays out of make iac.
_STG_TABLE = "MET_CSV_SNAPSHOT_STG"

# CSV header -> snake_case JSON key. Mirrors csv_bootstrap._map_row so the snapshot
# VARIANT keys match the SQLite/Silver vocabulary exactly. Values are kept as raw
# trimmed strings (empty -> null): the snapshot is a faithful raw mirror; typing is
# deferred to Silver. The worklist view casts is_public_domain/is_highlight::BOOLEAN
# (TO_BOOLEAN handles 'True'/'False'; JSON null stays null -> safe) and department/
# metadata_date::STRING.
_CSV_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("Object Number", "object_number"),
    ("Is Highlight", "is_highlight"),
    ("Is Public Domain", "is_public_domain"),
    ("Department", "department"),
    ("AccessionYear", "accession_year"),
    ("Object Name", "object_name"),
    ("Title", "title"),
    ("Culture", "culture"),
    ("Period", "period"),
    ("Dynasty", "dynasty"),
    ("Reign", "reign"),
    ("Portfolio", "portfolio"),
    ("Artist Role", "artist_role"),
    ("Artist Display Name", "artist_display_name"),
    ("Artist Display Bio", "artist_display_bio"),
    ("Artist Alpha Sort", "artist_alpha_sort"),
    ("Artist Nationality", "artist_nationality"),
    ("Artist Begin Date", "artist_begin_date"),
    ("Artist End Date", "artist_end_date"),
    ("Artist Gender", "artist_gender"),
    ("Artist ULAN URL", "artist_ulan_url"),
    ("Artist Wikidata URL", "artist_wikidata_url"),
    ("Object Date", "object_date"),
    ("Object Begin Date", "object_begin_date"),
    ("Object End Date", "object_end_date"),
    ("Medium", "medium"),
    ("Dimensions", "dimensions"),
    ("Credit Line", "credit_line"),
    ("Geography Type", "geography_type"),
    ("City", "city"),
    ("State", "state"),
    ("County", "county"),
    ("Country", "country"),
    ("Region", "region"),
    ("Subregion", "subregion"),
    ("Locale", "locale"),
    ("Locus", "locus"),
    ("Excavation", "excavation"),
    ("River", "river"),
    ("Classification", "classification"),
    ("Rights and Reproduction", "rights_and_reproduction"),
    ("Link Resource", "link_resource"),
    ("Object Wikidata URL", "object_wikidata_url"),
    ("Metadata Date", "metadata_date"),
    ("Repository", "repository"),
    ("Tags", "tags"),
    ("Tags AAT URL", "tags_aat_url"),
    ("Tags Wikidata URL", "tags_wikidata_url"),
)


def _clean(value: Optional[str]) -> Optional[str]:
    """Trim a CSV cell; empty/whitespace -> None (so VARIANT stores JSON null)."""
    if value is None:
        return None
    s = value.strip()
    return s if s else None


def _object_id(row: Dict[str, str]) -> Optional[int]:
    """Parse the Object ID, tolerating floats/whitespace; None if unusable."""
    raw = row.get("Object ID")
    if raw is None or not raw.strip():
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _map_snapshot_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Build the faithful snake_case JSON document for one CSV row.

    Returns None for rows without a valid Object ID (skipped).
    """
    object_id = _object_id(row)
    if object_id is None:
        return None
    payload: Dict[str, Any] = {"object_id": object_id}
    for header, key in _CSV_FIELDS:
        payload[key] = _clean(row.get(header))
    return payload


def _write_ndjson_chunk(
    payloads: List[Dict[str, Any]],
    batch_id: str,
    chunk_index: int,
    target_dir: Path,
) -> Path:
    """Write one gzipped NDJSON file of snapshot payloads; return its path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"met_snapshot_{batch_id}_{chunk_index:05d}.ndjson.gz"
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        for payload in payloads:
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")
    return file_path


def _iter_payloads(config: Config, limit: Optional[int]) -> Iterator[Dict[str, Any]]:
    """Yield snapshot payloads from the local CSV, optionally capped at `limit`."""
    emitted = 0
    for row in _iter_csv_rows(config.csv_local_path):
        payload = _map_snapshot_row(row)
        if payload is None:
            continue
        yield payload
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def _create_staging_table(cur: snowflake.connector.cursor.SnowflakeCursor) -> None:
    """Create the session-scoped staging table (auto-dropped on disconnect)."""
    cur.execute(
        f"CREATE TEMPORARY TABLE {_STG_TABLE} ("
        "  object_id   NUMBER  NOT NULL,"
        "  raw_payload VARIANT NOT NULL,"
        "  _batch_id   VARCHAR NOT NULL"
        ")"
    )


def _put_and_copy_stg(
    cur: snowflake.connector.cursor.SnowflakeCursor,
    file_path: Path,
    config: Config,
    batch_id: str,
) -> int:
    """PUT one NDJSON file to the stage, COPY it into the staging table."""
    stage = f"@{config.snowflake_database}.{config.snowflake_schema}.{config.snowflake_stage}"
    put_sql = (
        f"PUT file://{file_path.as_posix()} {stage}/met_snapshot/{batch_id}/ "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    )
    logger.info("PUT %s -> %s/met_snapshot/%s/", file_path.name, stage, batch_id)
    cur.execute(put_sql)
    copy_sql = COPY_INTO_STG_SQL.format(
        stg=_STG_TABLE, stage=stage, batch_id=batch_id, filename=file_path.name,
    )
    cur.execute(copy_sql)
    result = cur.fetchall()
    # COPY INTO result column index 3 is rows_loaded.
    return sum(int(r[3]) for r in result) if result else 0


def _merge_into_snapshot(
    cur: snowflake.connector.cursor.SnowflakeCursor, config: Config,
) -> Tuple[int, int]:
    """MERGE the staging table into MET_CSV_SNAPSHOT; return (inserted, updated)."""
    target = f"{config.snowflake_database}.{config.snowflake_schema}.MET_CSV_SNAPSHOT"
    cur.execute(MERGE_SNAPSHOT_SQL.format(target=target, stg=_STG_TABLE))
    result = cur.fetchone()
    # MERGE result columns: number of rows inserted, number of rows updated.
    inserted = int(result[0]) if result and len(result) > 0 else 0
    updated = int(result[1]) if result and len(result) > 1 else 0
    return inserted, updated


def _log_start(cur: snowflake.connector.cursor.SnowflakeCursor, batch_id: str) -> None:
    """AUTO-03: open an EXTRACTION_LOG row for this snapshot run."""
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


def load_snapshot(config: Config, refresh_csv: bool = True, limit: Optional[int] = None) -> int:
    """Load the Met CSV into BRONZE.MET_CSV_SNAPSHOT via stage -> COPY -> MERGE.

    Args:
        refresh_csv: re-download the CSV (else reuse + revalidate the local copy).
        limit: cap the number of objects loaded (smoke testing); None = full file.

    Returns the number of rows MERGEd (inserted + updated).
    """
    config.ensure_paths()
    if refresh_csv or not config.csv_local_path.exists():
        download_csv(config.csv_url, config.csv_local_path)
    else:
        logger.info("Reusing existing CSV at %s", config.csv_local_path)
        assert_real_met_csv(config.csv_local_path)

    batch_id = (
        f"met_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    staged_rows = 0

    sf_conn = _snowflake_connect(config)
    cur = sf_conn.cursor()
    try:
        _log_start(cur, batch_id)
        try:
            _create_staging_table(cur)
            with tempfile.TemporaryDirectory(prefix="met_snapshot_") as tmp:
                target_dir = Path(tmp)
                chunk_index = 0
                chunk: List[Dict[str, Any]] = []
                for payload in _iter_payloads(config, limit):
                    chunk.append(payload)
                    if len(chunk) >= config.upload_chunk_size:
                        fp = _write_ndjson_chunk(chunk, batch_id, chunk_index, target_dir)
                        staged_rows += _put_and_copy_stg(cur, fp, config, batch_id)
                        logger.info("Staged chunk %s (%s rows total)", chunk_index, f"{staged_rows:,}")
                        chunk_index += 1
                        chunk.clear()
                if chunk:
                    fp = _write_ndjson_chunk(chunk, batch_id, chunk_index, target_dir)
                    staged_rows += _put_and_copy_stg(cur, fp, config, batch_id)
                    logger.info("Staged final chunk %s (%s rows total)", chunk_index, f"{staged_rows:,}")

            inserted, updated = _merge_into_snapshot(cur, config)
            merged = inserted + updated
            _log_finish(cur, batch_id, "success", merged)
            sf_conn.commit()
            logger.info(
                "Snapshot load complete. batch_id=%s staged=%s inserted=%s updated=%s",
                batch_id, f"{staged_rows:,}", f"{inserted:,}", f"{updated:,}",
            )
            return merged
        except Exception as exc:
            _log_finish(cur, batch_id, "failed", staged_rows, str(exc)[:1000])
            sf_conn.commit()
            raise
    finally:
        cur.close()
        sf_conn.close()
