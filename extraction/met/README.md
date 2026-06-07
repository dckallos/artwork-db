# Met OpenAccess Bronze loader

Fully-resumable extractor for the Metropolitan Museum of Art Open Access
collection. All API calls are **synchronous** (`requests` library); there is no
async/await or `aiohttp` in the runtime path.

**Current (Snowflake-authoritative) path -- Option B.** State lives in Snowflake
Bronze control tables; SQLite is only disposable in-run scratch.

1. **snapshot**     -- Load the full `MetObjects.csv` from GitHub into
                    `ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT` (descriptive truth; no API
                    calls) via stage + `COPY INTO` + `MERGE`.
2. **seed-control** -- Insert `pending` control rows for a bounded slice of the
                    snapshot into `BRONZE.MET_ENRICHMENT_CONTROL`. This is where the
                    costly API enrichment is bounded.
3. **enrich-met**   -- Drain `BRONZE.MET_WORKLIST`: lease-claim a batch, fetch image
                    URLs from the Met API locally (sync `requests`), assemble
                    `RAW_MET_OBJECTS` server-side from the snapshot, and write
                    outcomes back to the control table. Resumable via lease TTL
                    reclaim.

**Legacy SQLite path (superseded; kept in the CLI only).** The original
`bootstrap` -> `enrich` -> `upload` flow stored state in local SQLite. It still
runs but is no longer the architecture; see "Usage (legacy SQLite path)" below.

## Repository layout

    extraction/met/
    |-- __init__.py
    |-- config.py             # Settings dataclass, env var loading
    |-- db.py                 # SQL loader + SQLite connect()
    |-- csv_bootstrap.py      # Download CSV + upsert into SQLite
    |-- image_enricher.py     # Sync API calls (requests) to fetch image URLs;
    |                         #   adaptive rate limiter + global throttle gate
    |-- control_enricher.py   # Phase 3: lease-claim-fetch-assemble-callback loop
    |                         #   (Snowflake-authoritative enrichment driver)
    |-- control_seeder.py     # Phase 2: seed MET_ENRICHMENT_CONTROL from snapshot
    |-- snapshot_loader.py    # Phase 1: CSV -> stage -> COPY -> MERGE into snapshot
    |-- snowflake_uploader.py # NDJSON + PUT + COPY INTO BRONZE (legacy path)
    |-- run.py                # CLI entry point (subcommand dispatch)
    |-- sql/                  # Externalized SQL templates (MERGE, COPY, CLAIM, etc.)
    |-- requirements.txt
    |-- .env.example
    `-- README.md

Local data files (created on first run, gitignored):

    extraction/met/data/
    |-- MetObjects.csv  # ~500 MB CSV from github.com/metmuseum/openaccess
    `-- met.db          # SQLite database (legacy path only)

Override these locations with `MET_SQLITE_PATH` and `MET_CSV_LOCAL_PATH` in
`.env`.

## Prerequisites

- Python 3.10+ (3.11 recommended).
- Dependencies: `snowflake-connector-python`, `requests`, `python-dotenv`
  (see `requirements.txt` -- no async libraries needed).
- Snowflake account with infra applied (run `make infra` from the repo root):
  database `ARTWORK_DB`, schema `BRONZE`, the Bronze tables (`RAW_MET_OBJECTS`,
  `MET_CSV_SNAPSHOT`, `MET_ENRICHMENT_CONTROL`) + `MET_WORKLIST` view, internal
  stage `bronze_load_stage`, role `ARTWORK_LOADER`, warehouse `ARTWORK_WH`.
- ~5 GB free local disk.
- Outbound HTTPS to `media.githubusercontent.com`,
  `collectionapi.metmuseum.org`, and your Snowflake account URL.

## Quick start

    cd ~/dev/artwork-db
    python -m venv .venv && source .venv/bin/activate
    pip install -r extraction/met/requirements.txt
    cp .env.example .env   # then edit credentials
    # Current path (run from the repo root):
    python -m extraction.met.run snapshot -v
    python -m extraction.met.run seed-control -v
    python -m extraction.met.run enrich-met -v

## Usage (current: Option B)

Three subcommands, run in order on a fresh load. State lives in Snowflake, so
each is independently re-runnable and `enrich-met` is resumable via lease reclaim.

### snapshot

    python -m extraction.met.run snapshot -v

- Streams `MetObjects.csv` from GitHub and loads it into
  `BRONZE.MET_CSV_SNAPSHOT` via stage -> `COPY INTO` -> `MERGE` (no API calls).
- Pass `--no-refresh` to reuse the local CSV; `--limit N` to cap rows (smoke test).

### seed-control

    python -m extraction.met.run seed-control -v

- Inserts `pending` rows into `BRONZE.MET_ENRICHMENT_CONTROL` for a bounded slice
  of the snapshot. `--department "European Paintings"` scopes the slice;
  `--limit N` caps it; `--include-non-public-domain` drops the PD gate.
- This is the cost-control point: enrichment only touches seeded rows.

### enrich-met

    python -m extraction.met.run enrich-met -v

- Drains `BRONZE.MET_WORKLIST`: lease-claims a batch, fetches image URLs from the
  Met API using synchronous `requests` calls with adaptive rate limiting, assembles
  `RAW_MET_OBJECTS` server-side, writes outcomes back.
- `--limit N` bounds a single batch (smoke test); omit it to drain the worklist.
- `--progress-every N` controls how often a progress line is emitted (default: 100).
- Resumable: abandoned leases reclaim via TTL (see `MET_LEASE_RECLAIM_TASK`).

## Usage (legacy SQLite path)

Superseded by Option B above; kept in the CLI for reference. Each phase is
independently runnable and fully resumable. Run them in order on a fresh setup,
or invoke a single phase if you only need to refresh one part of the pipeline.

### Phase A: bootstrap

    python -m extraction.met.run bootstrap -v

- Streams `MetObjects.csv` from GitHub and upserts every row into
  `met_artworks` with `enrichment_status='pending'`.
- Runtime: ~2-5 minutes.
- Idempotent. Pass `--no-refresh` to reuse the local CSV instead of
  re-downloading.
- The CSV lands at `./data/MetObjects.csv` and the SQLite database at
  `./data/met.db`, both relative to the directory you invoke the CLI from.

### Phase B: enrich

    python -m extraction.met.run enrich -v

- Calls `/objects/{object_id}` on the Met API for every row with
  `enrichment_status IN ('pending', 'error')`.
- Stores `primaryImage`, `primaryImageSmall`, and `additionalImages`. Rows
  whose response has no `primaryImage` (or a 404) are flagged `no_image`
  and excluded from the Bronze load.
- Uses synchronous `requests` with an adaptive rate limiter (decays on 403/429
  throttle bursts, recovers on success) and a global throttle gate
  (exponential backoff shared across all requests).
- Runtime: ~6-7 hours at the default 40 rps across ~471k objects.
- Fully resumable; commits every 500 rows. Re-running picks up only
  `pending` and `error` rows so transient failures self-heal.

### Phase C: upload

    python -m extraction.met.run upload -v

- Streams `enrichment_status='done' AND bronze_uploaded_at IS NULL` rows
  out of SQLite, builds a nested JSON payload, writes gzipped NDJSON chunks
  to a temp directory, `PUT`s them to
  `@BRONZE.bronze_load_stage/met/<batch_id>/`, then
  `COPY INTO raw_met_objects (object_id, raw_payload, _batch_id)` with
  `PURGE=TRUE`.
- Runtime: ~10-30 minutes for a full first load.
- Idempotent: rows with `bronze_uploaded_at` set are skipped, so retrying
  after a failure only re-sends the missing rows.

### status

    python -m extraction.met.run status

Prints three small dashboards: row counts by `enrichment_status`, current
upload state (done total / not uploaded / uploaded), and the 10 most recent
`extraction_runs` entries.

### all

    python -m extraction.met.run all -v

Runs `bootstrap` -> `enrich` -> `upload` back-to-back. Best for a fresh
environment you can leave running overnight.

## Recovery

### Option B (Snowflake-authoritative) recovery

- **Interrupted enrich-met.** Re-run `enrich-met`. Rows leased by the crashed
  batch are released automatically after the 30-min TTL by
  `MET_LEASE_RECLAIM_TASK` (hourly cron). They re-appear in the worklist on
  the next run.
- **Check worklist health.**

        SELECT enrichment_status, COUNT(*)
        FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
        GROUP BY enrichment_status;

- **Check recent extraction batches.**

        SELECT * FROM ARTWORK_DB.BRONZE.EXTRACTION_LOG
        ORDER BY started_at DESC LIMIT 10;

### Legacy SQLite path recovery

- **Interrupted enrich.** Re-run `enrich`. Only `pending` and `error` rows
  are retried. Run `status` first to see how many are outstanding.
- **Persistent error rows.** Inspect failure messages in SQLite:

        SELECT object_id, enrichment_error
        FROM met_artworks
        WHERE enrichment_status = 'error'
        LIMIT 20;

  Most errors are HTTP 5xx or transport timeouts and clear on a subsequent
  run. Hard errors usually mean a malformed object ID and are safe to leave
  as `error`.
- **Transient Snowflake errors during upload.** Re-run `upload`. Already-
  uploaded rows are skipped via `bronze_uploaded_at`. Staged files use
  `OVERWRITE=TRUE` on PUT and `PURGE=TRUE` after a successful COPY, so
  retries do not duplicate or strand files.
- **Partial upload check.** Cross-check counts:

        -- SQLite
        SELECT COUNT(*) FROM met_artworks
        WHERE bronze_uploaded_at IS NOT NULL;

        -- Snowflake
        SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.raw_met_objects;

  Counts should match.

## Rate limiting

The Met API uses both 403 and 429 as throttle signals (403 is a soft-throttle
in disguise, not a permission error). The enricher handles this with two
cooperating mechanisms:

1. **Adaptive rate limiter** (`_RateLimiter`): token-bucket style. After 3
   consecutive throttles, RPS drops 30%. On each success, RPS edges back up 5%
   toward the configured ceiling. Floor: 1 rps. Ceiling: configured `MET_API_RPS`.

2. **Global throttle gate** (`_ThrottleGate`): exponential backoff shared across
   all requests. When any request sees a throttle, subsequent requests block
   behind a shared `backoff_until` timestamp. Honors `Retry-After` headers.
   Detects chronic rejection (>80% failure over a 50-request window) and
   escalates backoff ceiling; auto-resets on recovery.

The combination means the enricher self-throttles under load and bails out
entirely if the API persistently rejects requests (chronic mode), preserving
progress for the next run.

## Tuning knobs

All set via `.env`.

- **`MET_API_RPS`** (default `40`) -- target request rate. The adaptive
  limiter decays below this under throttle pressure and recovers toward it
  on success. The Met nominally allows ~80 rps but empirically throttles
  well below that.
- **`MET_API_CONCURRENCY`** (default `3`) -- reserved for future use. The
  current sync path processes one request at a time; this setting is read
  but not actively used.
- **`MET_API_MAX_RETRIES`** (default `8`) -- per-request retry budget for
  403/429/5xx and transport errors. Large enough for the backoff sequence
  to ride out sustained throttle windows.
- **`MET_API_TIMEOUT`** (default `20`) -- per-request socket timeout in
  seconds.
- **`MET_UPLOAD_CHUNK`** (default `5000`) -- rows per NDJSON file / COPY
  INTO operation. Larger chunks reduce stage overhead but increase memory
  pressure and per-COPY failure blast radius. 5k is a sweet spot on an XS
  warehouse.
- **`MET_API_USER_AGENT`** -- the Met asks API clients to identify
  themselves. Keep real contact info in here.

## Configuration reference

All settings are read from environment variables (loaded from `.env` via
`python-dotenv`). Copy `.env.example` and fill in your values.

| Env var | Default | Description |
|---------|---------|-------------|
| `SNOWFLAKE_ACCOUNT` | *(required)* | Snowflake account identifier (e.g. `OBANOYY-MK07348`). |
| `SNOWFLAKE_USER` | *(required)* | Service user for Bronze loading (`ARTWORK_LOADER_SVC`). |
| `SNOWFLAKE_PRIVATE_KEY_FILE` | *(required)* | Path to the unencrypted PKCS#8 private key (`.p8`) registered for the loader user. Minted by `make loader CONN=<conn>`. |
| `SNOWFLAKE_PRIVATE_KEY_FILE_PWD` | `None` | Passphrase for the private key, only if the key was generated encrypted (default keys are unencrypted). |
| `SNOWFLAKE_ROLE` | `ARTWORK_LOADER` | Role assumed for all Bronze writes. |
| `SNOWFLAKE_WAREHOUSE` | `ARTWORK_WH` | Warehouse for COPY INTO / MERGE operations. |
| `SNOWFLAKE_DATABASE` | `ARTWORK_DB` | Target database. |
| `SNOWFLAKE_SCHEMA` | `BRONZE` | Target schema. |
| `SNOWFLAKE_TABLE` | `raw_met_objects` | Target table for the legacy upload path. |
| `SNOWFLAKE_STAGE` | `bronze_load_stage` | Internal stage for PUT + COPY INTO. |
| `MET_CSV_URL` | GitHub media URL | Override the MetObjects.csv download URL (rarely needed). |
| `MET_CSV_LOCAL_PATH` | `./data/MetObjects.csv` | Where the CSV is cached locally. |
| `MET_SQLITE_PATH` | `./data/met.db` | SQLite database path (legacy path only). |
| `MET_API_RPS` | `40` | Target requests per second. Adaptive limiter decays below this under throttle pressure. |
| `MET_API_CONCURRENCY` | `3` | Reserved for future threading use. Not actively used in the sync path. |
| `MET_API_MAX_RETRIES` | `8` | Per-request retry budget for 403/429/5xx and transport errors. |
| `MET_API_TIMEOUT` | `20` | Per-request socket read timeout in seconds. |
| `MET_API_USER_AGENT` | `artwork-db/1.0 (...)` | User-Agent header sent to the Met API. Keep real contact info. |
| `MET_UPLOAD_CHUNK` | `5000` | Rows per NDJSON file / COPY INTO operation. |

## Verifying the load in Snowflake

    USE ROLE ARTWORK_LOADER;
    USE WAREHOUSE ARTWORK_WH;
    USE DATABASE ARTWORK_DB;
    USE SCHEMA BRONZE;

    -- 1. Row count.
    SELECT COUNT(*) AS bronze_rows FROM raw_met_objects;

    -- 2. Recent batches and their sizes.
    SELECT _batch_id, COUNT(*) AS rows_in_batch,
           MIN(_extracted_at) AS loaded_at
    FROM raw_met_objects
    GROUP BY _batch_id
    ORDER BY loaded_at DESC;

    -- 3. Spot-check the JSON shape.
    SELECT object_id,
           raw_payload:csv:title::VARCHAR                AS title,
           raw_payload:csv:department::VARCHAR           AS department,
           raw_payload:api_images:primary_image::VARCHAR AS primary_image
    FROM raw_met_objects
    LIMIT 5;

    -- 4. Every row should have a primary image URL.
    SELECT COUNT(*) AS rows_missing_primary_image
    FROM raw_met_objects
    WHERE raw_payload:api_images:primary_image IS NULL;

If row counts match the control table's `enrichment_status = 'done'` count and
the spot-check returns sensible titles, the load is healthy and the Silver/Gold
models can be built on top of it.
