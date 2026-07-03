"""
Core loader logic for the AIC extraction pipeline.

Orchestrates the snapshot path: download the S3 data dump, selectively
extract Tier 1 entities, transform individual JSONs to NDJSON, upload to
Snowflake via PUT + COPY INTO a temp table, MERGE into Bronze, and
soft-delete deaccessioned rows.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import snowflake.connector

from extraction.met.db import load_sql as _met_load_sql, strip_sql_comments
from extraction.met.snowflake_uploader import _snowflake_connect

from .config import (
    AIC_TIER1_ENTITIES,
    BATCH_PREFIX_SNAPSHOT,
    Config,
)

logger = logging.getLogger(__name__)


def _load_sql(name: str) -> str:
    """
    Read a .sql template from the extraction.aic.sql package.
    """
    from importlib import resources
    return resources.files("extraction.aic.sql").joinpath(name).read_text(encoding="utf-8")


def _generate_batch_id() -> str:
    """
    Generate a snapshot batch ID (snap_ + 12-char hex).
    """
    return f"{BATCH_PREFIX_SNAPSHOT}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Step 1: Download the tar.bz2 dump
# ---------------------------------------------------------------------------

def download_dump(config: Config) -> Path:
    """
    Download the AIC data dump tar.bz2 to the configured path.

    Uses streaming download with a simple retry (one attempt). Returns the
    path to the downloaded file.
    """
    tar_path = config.tar_path
    tar_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading AIC data dump from %s", config.dump_url)
    resp = requests.get(config.dump_url, stream=True, timeout=300)
    resp.raise_for_status()

    total_bytes = 0
    with open(tar_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            total_bytes += len(chunk)

    logger.info("Download complete: %s (%.1f MB)", tar_path, total_bytes / 1e6)
    return tar_path


# ---------------------------------------------------------------------------
# Step 2: Selectively extract Tier 1 entity folders
# ---------------------------------------------------------------------------

def extract_entities(config: Config) -> Path:
    """
    Selectively extract Tier 1 entity folders from the tar.bz2.

    Only extracts json/artworks/ and json/agents/ to save disk space.
    Returns the path to the extraction directory.
    """
    extract_dir = config.extract_dir
    extract_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting Tier 1 entities from %s", config.tar_path)
    prefixes = tuple(f"artic-api-data/json/{entity}/" for entity in AIC_TIER1_ENTITIES)

    with tarfile.open(config.tar_path, "r:bz2") as tf:
        members = [m for m in tf.getmembers() if m.name.startswith(prefixes)]
        logger.info("Found %d members to extract (artworks + agents)", len(members))
        tf.extractall(path=extract_dir, members=members)

    logger.info("Extraction complete: %s", extract_dir)
    return extract_dir


# ---------------------------------------------------------------------------
# Step 3: Transform individual JSONs to NDJSON
# ---------------------------------------------------------------------------

def _transform_entity_to_ndjson(
    json_dir: Path,
    output_path: Path,
    entity_name: str,
    id_field: str,
    limit: Optional[int] = None,
) -> int:
    """
    Read individual JSON files and write a single gzipped NDJSON file.

    Each JSON file contains one record. We read it, extract the id, and
    write the full JSON as one line in the NDJSON output.

    Returns the number of records written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_files = sorted(json_dir.glob("*.json"))

    if limit is not None:
        json_files = json_files[:limit]

    count = 0
    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    record = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping malformed file %s: %s", json_file.name, e)
                continue

            entity_id = record.get(id_field)
            if entity_id is None:
                logger.warning("Skipping file %s: missing '%s' field", json_file.name, id_field)
                continue

            out.write(json.dumps(record, ensure_ascii=False))
            out.write("\n")
            count += 1

            if count % 10000 == 0:
                logger.info("[%s] Transformed %d records...", entity_name, count)

    logger.info("[%s] Transform complete: %d records written to %s", entity_name, count, output_path)
    return count


def transform_artworks(config: Config, limit: Optional[int] = None) -> Tuple[Path, int]:
    """
    Transform artworks JSON files to gzipped NDJSON. Returns (path, count).
    """
    json_dir = config.extract_dir / "artic-api-data" / "json" / "artworks"
    output_path = config.data_dir / "aic_artworks.ndjson.gz"
    count = _transform_entity_to_ndjson(json_dir, output_path, "artworks", "id", limit)
    return output_path, count


def transform_agents(config: Config, limit: Optional[int] = None) -> Tuple[Path, int]:
    """
    Transform agents JSON files to gzipped NDJSON. Returns (path, count).
    """
    json_dir = config.extract_dir / "artic-api-data" / "json" / "agents"
    output_path = config.data_dir / "aic_agents.ndjson.gz"
    count = _transform_entity_to_ndjson(json_dir, output_path, "agents", "id", limit)
    return output_path, count


# ---------------------------------------------------------------------------
# Step 4: Upload NDJSON to Snowflake stage via PUT
# ---------------------------------------------------------------------------

def _put_file(
    conn: snowflake.connector.SnowflakeConnection,
    local_path: Path,
    stage_path: str,
) -> None:
    """
    PUT a local file to the Snowflake internal stage.
    """
    put_sql = (
        f"PUT 'file://{local_path}' '{stage_path}' "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    )
    logger.info("PUT %s -> %s", local_path.name, stage_path)
    conn.cursor().execute(put_sql)


# ---------------------------------------------------------------------------
# Step 5: COPY INTO temp staging table + MERGE into Bronze
# ---------------------------------------------------------------------------

def _create_temp_staging_table(
    conn: snowflake.connector.SnowflakeConnection,
    table_name: str,
    id_column: str,
) -> None:
    """
    Create a temporary staging table for COPY INTO.
    """
    sql = f"""
    CREATE TEMPORARY TABLE {table_name} (
        {id_column} INT NOT NULL,
        RAW_PAYLOAD VARIANT NOT NULL,
        _BATCH_ID VARCHAR NOT NULL
    )
    """
    conn.cursor().execute(sql)
    logger.info("Created temporary staging table %s", table_name)


def _copy_into_staging(
    conn: snowflake.connector.SnowflakeConnection,
    staging_table: str,
    stage_path: str,
    id_field: str,
    id_column: str,
    batch_id: str,
) -> int:
    """
    COPY NDJSON from stage into the temporary staging table.

    Parses each NDJSON line as VARIANT and extracts the id field.
    Returns the number of rows loaded.
    """
    sql = f"""
    COPY INTO {staging_table} ({id_column}, RAW_PAYLOAD, _BATCH_ID)
    FROM (
        SELECT
            $1:{id_field}::INT,
            $1,
            '{batch_id}'
        FROM '{stage_path}'
    )
    FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = FALSE COMPRESSION = GZIP)
    PURGE = TRUE
    """
    cur = conn.cursor().execute(sql)
    row = cur.fetchone()
    rows_loaded = row[3] if row and len(row) > 3 else 0
    logger.info("COPY INTO %s: %d rows loaded", staging_table, rows_loaded)
    return rows_loaded


def _merge_into_target(
    conn: snowflake.connector.SnowflakeConnection,
    merge_sql_template: str,
    target_table: str,
    staging_table: str,
) -> Dict[str, int]:
    """
    Execute a MERGE statement and return row counts.
    """
    sql = strip_sql_comments(merge_sql_template).format(
        target=target_table,
        stg=staging_table,
    )
    cur = conn.cursor().execute(sql)
    row = cur.fetchone()
    inserted = row[0] if row else 0
    updated = row[1] if row and len(row) > 1 else 0
    logger.info("MERGE INTO %s: %d inserted, %d updated", target_table, inserted, updated)
    return {"inserted": inserted, "updated": updated}


# ---------------------------------------------------------------------------
# Step 6: Soft-delete deaccessioned rows
# ---------------------------------------------------------------------------

def _soft_delete_deaccessioned(
    conn: snowflake.connector.SnowflakeConnection,
    target_table: str,
    batch_id: str,
) -> int:
    """
    Mark rows not in the current batch as soft-deleted. Returns count.
    """
    template = _load_sql("soft_delete_deaccessioned.sql")
    sql = strip_sql_comments(template).format(
        target=target_table,
        current_batch_id=batch_id,
    )
    cur = conn.cursor().execute(sql)
    row = cur.fetchone()
    deleted_count = row[0] if row else 0
    logger.info("Soft-delete on %s: %d rows marked as deaccessioned", target_table, deleted_count)
    return deleted_count


# ---------------------------------------------------------------------------
# Orchestrator: run_snapshot
# ---------------------------------------------------------------------------

def run_snapshot(
    config: Config,
    refresh: bool = True,
    limit: Optional[int] = None,
    entities: Optional[List[str]] = None,
) -> None:
    """
    Execute the full snapshot pipeline.

    Steps:
      1. Download the tar.bz2 dump (skip if --no-refresh and file exists).
      2. Selectively extract Tier 1 entity folders.
      3. Transform individual JSONs to gzipped NDJSON.
      4. Connect to Snowflake.
      5. For each entity: PUT -> COPY INTO temp -> MERGE into Bronze.
      6. Soft-delete deaccessioned artworks (post-MERGE).
    """
    if entities is None:
        entities = list(AIC_TIER1_ENTITIES)

    batch_id = _generate_batch_id()
    logger.info("Starting AIC snapshot (batch_id=%s, entities=%s, limit=%s)",
                batch_id, entities, limit)

    # Step 1: Download
    if refresh or not config.tar_path.exists():
        download_dump(config)
    else:
        logger.info("Reusing cached tar at %s (--no-refresh)", config.tar_path)

    # Step 2: Extract
    extract_entities(config)

    # Step 3: Transform
    ndjson_files: Dict[str, Tuple[Path, int]] = {}
    if "artworks" in entities:
        ndjson_files["artworks"] = transform_artworks(config, limit=limit)
    if "agents" in entities:
        ndjson_files["agents"] = transform_agents(config, limit=limit)

    # Step 4-6: Upload + Merge + Soft-delete
    conn = _snowflake_connect(config)
    try:
        db_schema = f"{config.snowflake_database}.{config.snowflake_schema}"
        stage = f"@{db_schema}.{config.snowflake_stage}"

        if "artworks" in ndjson_files:
            artworks_path, artworks_count = ndjson_files["artworks"]
            if artworks_count > 0:
                _load_entity(
                    conn=conn,
                    ndjson_path=artworks_path,
                    stage_prefix=f"{stage}/aic/artworks",
                    staging_table_name="AIC_STG_ARTWORKS",
                    target_table=f"{db_schema}.RAW_AIC_ARTWORKS",
                    id_field="id",
                    id_column="ARTWORK_ID",
                    merge_template=_load_sql("merge_aic_artworks.sql"),
                    batch_id=batch_id,
                )
                # Soft-delete after artworks MERGE
                _soft_delete_deaccessioned(
                    conn, f"{db_schema}.RAW_AIC_ARTWORKS", batch_id
                )
            else:
                logger.warning("No artworks records to load; skipping MERGE.")

        if "agents" in ndjson_files:
            agents_path, agents_count = ndjson_files["agents"]
            if agents_count > 0:
                _load_entity(
                    conn=conn,
                    ndjson_path=agents_path,
                    stage_prefix=f"{stage}/aic/agents",
                    staging_table_name="AIC_STG_AGENTS",
                    target_table=f"{db_schema}.RAW_AIC_AGENTS",
                    id_field="id",
                    id_column="AGENT_ID",
                    merge_template=_load_sql("merge_aic_agents.sql"),
                    batch_id=batch_id,
                )
            else:
                logger.warning("No agents records to load; skipping MERGE.")

        logger.info("AIC snapshot complete (batch_id=%s)", batch_id)
    finally:
        conn.close()


def _load_entity(
    conn: snowflake.connector.SnowflakeConnection,
    ndjson_path: Path,
    stage_prefix: str,
    staging_table_name: str,
    target_table: str,
    id_field: str,
    id_column: str,
    merge_template: str,
    batch_id: str,
) -> None:
    """
    PUT + COPY INTO temp + MERGE for a single entity.
    """
    # PUT
    _put_file(conn, ndjson_path, stage_prefix)

    # Create temp staging table
    _create_temp_staging_table(conn, staging_table_name, id_column)

    # COPY INTO staging
    stage_file = f"{stage_prefix}/{ndjson_path.name}"
    _copy_into_staging(conn, staging_table_name, stage_file, id_field, id_column, batch_id)

    # MERGE into target
    _merge_into_target(conn, merge_template, target_table, staging_table_name)
