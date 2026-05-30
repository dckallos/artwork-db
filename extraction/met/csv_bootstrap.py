"""
Download the Met OpenAccess CSV and load it into SQLite.

The CSV from github.com/metmuseum/openaccess contains essentially all the
descriptive metadata we need (everything except image URLs). We download it
once, parse it, and upsert into the met_artworks table. Rows start with
enrichment_status='pending' and stay there until image_enricher fills in
the API image URLs.

Re-running bootstrap is safe: existing rows have their CSV columns refreshed,
but image URLs and enrichment state are preserved.
"""
from __future__ import annotations

import csv
import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import requests

from .config import Config
from .db import connect, initialize_database, load_sql

logger = logging.getLogger(__name__)

# Multi-column UPSERT lives in extraction/met/sql/upsert_artwork.sql.
# Loaded once at import time so we don't pay the I/O cost per batch.
UPSERT_SQL = load_sql("upsert_artwork.sql")


def _coalesce_str(value: Optional[str]) -> Optional[str]:
    """Return None for empty/whitespace strings, otherwise trimmed string."""
    if value is None:
        return None
    s = value.strip()
    return s if s else None


def _coalesce_bool(value: Optional[str]) -> int:
    """Translate a truthy CSV string into 1/0; default 0."""
    if value is None:
        return 0
    return 1 if value.strip().lower() in ("1", "true", "yes") else 0


def _coalesce_int(value: Optional[str]) -> Optional[int]:
    """Parse an int from a CSV cell, tolerating floats/whitespace/empties."""
    if value is None or not value.strip():
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _map_row(row: Dict[str, str], loaded_at: str) -> Optional[Dict[str, Any]]:
    """Translate a raw CSV row dict into our SQLite parameter dict.

    Returns None for rows without a valid object_id (these are skipped).
    """
    object_id = _coalesce_int(row.get("Object ID"))
    if object_id is None:
        return None
    return {
        "object_id":               object_id,
        "object_number":           _coalesce_str(row.get("Object Number")),
        "is_highlight":            _coalesce_bool(row.get("Is Highlight")),
        "is_public_domain":        _coalesce_bool(row.get("Is Public Domain")),
        "department":              _coalesce_str(row.get("Department")),
        "accession_year":          _coalesce_str(row.get("AccessionYear")),
        "object_name":             _coalesce_str(row.get("Object Name")),
        "title":                   _coalesce_str(row.get("Title")),
        "culture":                 _coalesce_str(row.get("Culture")),
        "period":                  _coalesce_str(row.get("Period")),
        "dynasty":                 _coalesce_str(row.get("Dynasty")),
        "reign":                   _coalesce_str(row.get("Reign")),
        "portfolio":               _coalesce_str(row.get("Portfolio")),
        "artist_role":             _coalesce_str(row.get("Artist Role")),
        "artist_display_name":     _coalesce_str(row.get("Artist Display Name")),
        "artist_display_bio":      _coalesce_str(row.get("Artist Display Bio")),
        "artist_alpha_sort":       _coalesce_str(row.get("Artist Alpha Sort")),
        "artist_nationality":      _coalesce_str(row.get("Artist Nationality")),
        "artist_begin_date":       _coalesce_str(row.get("Artist Begin Date")),
        "artist_end_date":         _coalesce_str(row.get("Artist End Date")),
        "artist_gender":           _coalesce_str(row.get("Artist Gender")),
        "artist_ulan_url":         _coalesce_str(row.get("Artist ULAN URL")),
        "artist_wikidata_url":     _coalesce_str(row.get("Artist Wikidata URL")),
        "object_date":             _coalesce_str(row.get("Object Date")),
        "object_begin_date":       _coalesce_int(row.get("Object Begin Date")),
        "object_end_date":         _coalesce_int(row.get("Object End Date")),
        "medium":                  _coalesce_str(row.get("Medium")),
        "dimensions":              _coalesce_str(row.get("Dimensions")),
        "credit_line":             _coalesce_str(row.get("Credit Line")),
        "geography_type":          _coalesce_str(row.get("Geography Type")),
        "city":                    _coalesce_str(row.get("City")),
        "state":                   _coalesce_str(row.get("State")),
        "county":                  _coalesce_str(row.get("County")),
        "country":                 _coalesce_str(row.get("Country")),
        "region":                  _coalesce_str(row.get("Region")),
        "subregion":               _coalesce_str(row.get("Subregion")),
        "locale":                  _coalesce_str(row.get("Locale")),
        "locus":                   _coalesce_str(row.get("Locus")),
        "excavation":              _coalesce_str(row.get("Excavation")),
        "river":                   _coalesce_str(row.get("River")),
        "classification":          _coalesce_str(row.get("Classification")),
        "rights_and_reproduction": _coalesce_str(row.get("Rights and Reproduction")),
        "link_resource":           _coalesce_str(row.get("Link Resource")),
        "object_wikidata_url":     _coalesce_str(row.get("Object Wikidata URL")),
        "metadata_date":           _coalesce_str(row.get("Metadata Date")),
        "repository":              _coalesce_str(row.get("Repository")),
        "tags":                    _coalesce_str(row.get("Tags")),
        "tags_aat_url":            _coalesce_str(row.get("Tags AAT URL")),
        "tags_wikidata_url":       _coalesce_str(row.get("Tags Wikidata URL")),
        "csv_loaded_at":           loaded_at,
    }


def download_csv(csv_url: str, target_path: Path, chunk_bytes: int = 1024 * 1024) -> None:
    """Stream the Met CSV from GitHub to a local file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading Met CSV from %s -> %s", csv_url, target_path)
    with requests.get(csv_url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(target_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_bytes):
                if chunk:
                    f.write(chunk)
    logger.info(
        "Downloaded %s (%.1f MB)",
        target_path, target_path.stat().st_size / 1e6,
    )


def _iter_csv_rows(csv_path: Path) -> Iterator[Dict[str, str]]:
    """Yield rows from the CSV with a forgiving field-size limit."""
    csv.field_size_limit(sys.maxsize)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield row


def _start_run(conn: sqlite3.Connection, phase: str) -> str:
    """Insert a row in extraction_runs and return its run_id."""
    run_id = uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO extraction_runs (run_id, phase, started_at, status) "
        "VALUES (?, ?, ?, 'running')",
        (run_id, phase, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return run_id


def _finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    records: int,
    notes: Optional[str] = None,
) -> None:
    """Mark an extraction run finished with the given status and counts."""
    conn.execute(
        "UPDATE extraction_runs "
        "SET completed_at = ?, status = ?, records_processed = ?, notes = ? "
        "WHERE run_id = ?",
        (datetime.now(timezone.utc).isoformat(), status, records, notes, run_id),
    )
    conn.commit()


def bootstrap(
    config: Config,
    refresh_csv: bool = True,
    batch_size: int = 5000,
) -> int:
    """Download (optionally) the CSV, then upsert every row into SQLite.

    Returns the number of rows inserted/updated.
    """
    config.ensure_paths()
    initialize_database(config.sqlite_path)

    if refresh_csv or not config.csv_local_path.exists():
        download_csv(config.csv_url, config.csv_local_path)
    else:
        logger.info("Reusing existing CSV at %s", config.csv_local_path)

    loaded_at = datetime.now(timezone.utc).isoformat()
    processed = 0

    with connect(config.sqlite_path) as conn:
        run_id = _start_run(conn, phase="bootstrap")
        try:
            cursor = conn.cursor()
            batch: list = []
            for row in _iter_csv_rows(config.csv_local_path):
                mapped = _map_row(row, loaded_at)
                if mapped is None:
                    continue
                batch.append(mapped)
                if len(batch) >= batch_size:
                    cursor.executemany(UPSERT_SQL, batch)
                    conn.commit()
                    processed += len(batch)
                    logger.info("Bootstrap: %s rows upserted", f"{processed:,}")
                    batch.clear()
            if batch:
                cursor.executemany(UPSERT_SQL, batch)
                conn.commit()
                processed += len(batch)

            _finish_run(conn, run_id, status="success", records=processed)
            logger.info("Bootstrap complete: %s rows", f"{processed:,}")
            return processed
        except Exception as exc:
            _finish_run(conn, run_id, status="failed", records=processed, notes=str(exc))
            raise
