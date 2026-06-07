# AIC (Art Institute of Chicago) Bronze Loader

Fully-automated extractor for the Art Institute of Chicago's public data dump.
Downloads a ~115 MB tar.bz2 from S3, selectively extracts Tier 1 entities
(artworks + agents), transforms them to NDJSON, and MERGEs into Snowflake
Bronze tables with deaccession detection via soft-delete.

No SQLite. No multi-hour API crawl. The entire snapshot path runs in ~2-5
minutes.

## Repository layout

    extraction/aic/
    |-- __init__.py
    |-- config.py          # Settings dataclass, env var loading, constants
    |-- loader.py          # Core logic (download, extract, transform, upload, merge)
    |-- run.py             # CLI entry point (subcommand dispatch)
    |-- sql/
    |   |-- merge_aic_artworks.sql
    |   |-- merge_aic_agents.sql
    |   `-- soft_delete_deaccessioned.sql
    |-- requirements.txt
    |-- .env.example
    `-- README.md

Local data files (created on first run, gitignored):

    data/
    |-- aic_dump.tar.bz2       # ~115 MB cached dump
    |-- aic_extract/           # Selectively extracted JSON files
    |   `-- json/
    |       |-- artworks/*.json  (~131k files)
    |       `-- agents/*.json    (~15k files)
    |-- aic_artworks.ndjson.gz # Transformed NDJSON (gzipped)
    `-- aic_agents.ndjson.gz

## Prerequisites

- Python 3.10+ (3.11 recommended).
- Dependencies: `snowflake-connector-python`, `requests`, `python-dotenv`
  (see `requirements.txt`).
- Snowflake account with infra applied (run `make infra` from the repo root):
  database `ARTWORK_DB`, schema `BRONZE`, tables `RAW_AIC_ARTWORKS`,
  `RAW_AIC_AGENTS`, `AIC_LOAD_WATERMARK`, internal stage `bronze_load_stage`,
  role `ARTWORK_LOADER`, warehouse `ARTWORK_WH`.
- ~2 GB free local disk (tar + extracted JSONs + NDJSON).
- Outbound HTTPS to `artic-api-data.s3.amazonaws.com` and your Snowflake
  account URL.

## Quick start

    cd ~/dev/artwork-db
    python -m venv .venv && source .venv/bin/activate
    pip install -r extraction/aic/requirements.txt
    cp extraction/aic/.env.example .env   # then edit credentials
    python -m extraction.aic.run snapshot -v

## Usage

### snapshot

    python -m extraction.aic.run snapshot [-v] [--no-refresh] [--limit N] [--entities artworks,agents]

- Downloads the AIC data dump tar.bz2 from S3 (~115 MB, ~2 min).
- Selectively extracts only `json/artworks/` and `json/agents/` folders.
- Transforms each individual JSON file to one line in a gzipped NDJSON file.
- Uploads NDJSON to the Snowflake internal stage via PUT.
- COPY INTO a temporary staging table, then MERGE into the Bronze target.
- Post-MERGE: soft-deletes artworks whose `_batch_id` is stale (deaccessioned).

Options:
- `--no-refresh`: Reuse the cached tar.bz2 instead of re-downloading.
- `--limit N`: Cap records per entity (smoke testing).
- `--entities artworks,agents`: Select which entities to load (default: both).

### delta

    python -m extraction.aic.run delta

Not yet implemented. Prints a message and exits. See the design doc (Section 7)
for the planned incremental API delta path.

### status

    python -m extraction.aic.run status [-v]

Prints current row counts, deaccession counts, recent batch info, and
watermark state for all AIC Bronze tables.

## Recovery

- **Interrupted snapshot.** Re-run `snapshot`. The MERGE is idempotent (keyed
  on artwork_id / agent_id). If the download failed, re-run without
  `--no-refresh`. If the transform failed, the entire run restarts cheaply.
- **Check deaccession health:**

        SELECT COUNT(*) AS soft_deleted
        FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
        WHERE _IS_DELETED = TRUE;

- **Un-delete a row (manual override):**

        UPDATE ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
        SET _IS_DELETED = FALSE, _DELETED_AT = NULL, _DELETION_REASON = NULL
        WHERE ARTWORK_ID = <id>;

## Configuration reference

| Env var | Default | Description |
|---------|---------|-------------|
| `SNOWFLAKE_ACCOUNT` | *(required)* | Snowflake account identifier. |
| `SNOWFLAKE_USER` | *(required)* | Service user (`ARTWORK_LOADER_SVC`). |
| `SNOWFLAKE_PRIVATE_KEY_FILE` | *(required)* | Path to the unencrypted `.p8` private key. |
| `SNOWFLAKE_ROLE` | `ARTWORK_LOADER` | Role assumed for Bronze writes. |
| `SNOWFLAKE_WAREHOUSE` | `ARTWORK_WH` | Warehouse for COPY/MERGE ops. |
| `SNOWFLAKE_DATABASE` | `ARTWORK_DB` | Target database. |
| `AIC_DATA_DIR` | `./data` | Local directory for cached files. |
| `AIC_TAR_PATH` | `./data/aic_dump.tar.bz2` | Path to the cached data dump. |
| `AIC_EXTRACT_DIR` | `./data/aic_extract` | Extraction target directory. |
| `AIC_DUMP_URL` | S3 URL | Override the tar.bz2 download URL. |

## Verifying the load in Snowflake

    USE ROLE ARTWORK_LOADER;
    USE WAREHOUSE ARTWORK_WH;
    USE DATABASE ARTWORK_DB;
    USE SCHEMA BRONZE;

    -- 1. Row counts.
    SELECT COUNT(*) AS artworks_rows FROM RAW_AIC_ARTWORKS;
    SELECT COUNT(*) AS agents_rows FROM RAW_AIC_AGENTS;

    -- 2. Deaccession count.
    SELECT COUNT(*) AS deaccessioned FROM RAW_AIC_ARTWORKS WHERE _IS_DELETED = TRUE;

    -- 3. Recent batches.
    SELECT _BATCH_ID, COUNT(*) AS rows_in_batch, MIN(_EXTRACTED_AT) AS loaded_at
    FROM RAW_AIC_ARTWORKS
    GROUP BY _BATCH_ID ORDER BY loaded_at DESC;

    -- 4. Spot-check the JSON shape.
    SELECT ARTWORK_ID,
           RAW_PAYLOAD:title::VARCHAR AS title,
           RAW_PAYLOAD:is_public_domain::BOOLEAN AS is_public_domain,
           RAW_PAYLOAD:image_id::VARCHAR AS image_id
    FROM RAW_AIC_ARTWORKS
    LIMIT 5;

    -- 5. Watermark state (empty until delta is implemented).
    SELECT * FROM AIC_LOAD_WATERMARK;
