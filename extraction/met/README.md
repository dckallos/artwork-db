# Met OpenAccess Bronze loader

Fully-resumable extractor for the Metropolitan Museum of Art Open Access
collection.

**Current (Snowflake-authoritative) path -- Option B.** State lives in Snowflake
Bronze control tables; SQLite is only disposable in-run scratch.

1. **snapshot**     -- Load the full `MetObjects.csv` from GitHub into
                    `ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT` (descriptive truth; no API
                    calls) via stage + `COPY INTO` + `MERGE`.
2. **seed-control** -- Insert `pending` control rows for a bounded slice of the
                    snapshot into `BRONZE.MET_ENRICHMENT_CONTROL`. This is where the
                    costly API enrichment is bounded.
3. **enrich-met**   -- Drain `BRONZE.MET_WORKLIST`: lease-claim a batch, fetch image
                    URLs from the Met API locally, assemble `RAW_MET_OBJECTS`
                    server-side from the snapshot, and write outcomes back to the
                    control table. Resumable via lease TTL reclaim.

**Legacy SQLite path (superseded; kept in the CLI only).** The original
`bootstrap` -> `enrich` -> `upload` flow stored state in local SQLite. It still
runs but is no longer the architecture; see "Usage (legacy SQLite path)" below.

See the parent action plan sub-page for the full design rationale and code.

## Repository layout

    extraction/met/
    |-- __init__.py
    |-- config.py             # Settings dataclass, env var loading
    |-- db.py                 # SQL loader + SQLite connect()
    |-- csv_bootstrap.py      # Download CSV + upsert into SQLite
    |-- image_enricher.py     # Async API calls to fetch image URLs
    |-- snowflake_uploader.py # NDJSON + PUT + COPY INTO BRONZE
    |-- run.py                # CLI entry point
    |-- sql/                  # Externalized SQL (DDL, UPSERT, COPY INTO)
    |-- requirements.txt
    |-- .env.example
    `-- README.md<br><br>Local data files (created on first run, gitignored):<br><br>    extraction/met/data/<br>    |-- MetObjects.csv  # ~500 MB CSV downloaded from github.com/metmuseum/openaccess<br>    `-- met.db          # SQLite database, ~1-2 GB after full enrichment

Override these locations with `MET_SQLITE_PATH` and `MET_CSV_LOCAL_PATH` in
`.env`.

## Prerequisites

- Python 3.10+ (3.11 recommended).
- Snowflake account with infra applied (run `make infra` from the repo root):
  database `ARTWORK_DB`, schema `BRONZE`, the Bronze tables (`RAW_MET_OBJECTS`,
  `MET_CSV_SNAPSHOT`, `MET_ENRICHMENT_CONTROL`) + `MET_WORKLIST` view, internal
  stage `bronze_load_stage`, role `ARTWORK_LOADER`, warehouse `ARTWORK_WH`.
- ~5 GB free local disk.
- Outbound HTTPS to `raw.githubusercontent.com`,
  `collectionapi.metmuseum.org`, and your Snowflake account URL.

## Quick start

    cd extraction/met
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
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
  Met API locally, assembles `RAW_MET_OBJECTS` server-side, writes outcomes back.
- `--limit N` bounds a single batch (smoke test); omit it to drain the worklist.
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
- Runtime: ~6-7 hours at the default 20 rps across ~471k objects. Bump
  `MET_API_RPS` to 60 to finish in ~2 hours -- the Met API tolerates ~80
  rps.
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
- **Re-upload a batch.** Clear the upload markers in SQLite, then re-run
  `upload`:

        UPDATE met_artworks
        SET bronze_uploaded_at = NULL,
            bronze_batch_id    = NULL
        WHERE bronze_batch_id = '<batch_id>';

  If you want true replacement, delete the matching Snowflake rows first:

        DELETE FROM ARTWORK_DB.BRONZE.raw_met_objects
        WHERE _batch_id = '<batch_id>';

## Tuning knobs

All set via `.env`.

- **`MET_API_RPS`** (default `20`) -- total request rate cap. Met allows
  ~80; 60 finishes the enrich phase in ~2 hours.
- **`MET_API_CONCURRENCY`** (default `10`) -- max in-flight requests. Raise
  alongside `MET_API_RPS` if the rate limiter is starving connections. Rule
  of thumb: `MET_API_CONCURRENCY ~= MET_API_RPS / 4`.
- **`MET_API_MAX_RETRIES`** (default `5`) -- per-request retry budget for
  429/5xx and transport errors. Backoff is exponential with jitter, capped
  at 60 s.
- **`MET_UPLOAD_CHUNK`** (default `5000`) -- rows per NDJSON file / COPY
  INTO operation. Larger chunks reduce stage overhead but increase memory
  pressure and per-COPY failure blast radius. 5k is a sweet spot on an XS
  warehouse.
- **`MET_API_USER_AGENT`** -- the Met asks API clients to identify
  themselves. Keep real contact info in here.

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

If row counts match SQLite's `bronze_uploaded_at IS NOT NULL` count and the
spot-check returns sensible titles, the load is healthy and the Phase 2A
staging models can be built on top of it.
