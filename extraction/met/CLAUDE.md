# extraction/met/CLAUDE.md

Met Museum OpenAccess data loader. Downloads CSV, enriches via API, uploads to Bronze.

## Key design decisions

- Fetch runs LOCAL on Mac (not in Snowflake) to respect rate limits
- SQLite is disposable scratch storage during runs
- Snowflake Bronze tables are the source of truth for state
- Batch-grained status updates (not per-row)

## Running the loader

The CLI takes SUBCOMMANDS (not --phase). Current Snowflake-authoritative path:

```bash
# Snowflake-authoritative path (Option B)
python -m extraction.met.run snapshot      # Load full CSV into BRONZE.MET_CSV_SNAPSHOT
python -m extraction.met.run seed-control   # Seed bounded slice into MET_ENRICHMENT_CONTROL
python -m extraction.met.run enrich-met     # Drain worklist: fetch images, assemble Bronze

# Legacy SQLite path (superseded; kept in CLI only)
python -m extraction.met.run bootstrap      # Download CSV into SQLite
python -m extraction.met.run enrich         # SQLite API enrichment
python -m extraction.met.run upload         # Upload SQLite rows to Bronze
python -m extraction.met.run status         # SQLite status counts
```

## Key files

- run.py -- CLI entry point
- csv_bootstrap.py -- Downloads Met CSV, handles deduplication
- image_enricher.py -- Async API client with rate limiting (80 rps)
- snowflake_uploader.py -- NDJSON generation and COPY INTO Bronze
- sql/*.sql -- Externalized SQL (schema.sql, upsert_artwork.sql, etc.)

## Before changes

1. Check extraction/met/requirements.txt for dependencies
2. Verify .env has SNOWFLAKE_* credentials for ARTWORK_LOADER_SVC
3. Never embed SQL in Python -- use sql/ directory