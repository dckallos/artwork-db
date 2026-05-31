# extraction/met/CLAUDE.md

Met Museum OpenAccess data loader. Downloads CSV, enriches via API, uploads to Bronze.

## Key design decisions

- Fetch runs LOCAL on Mac (not in Snowflake) to respect rate limits
- SQLite is disposable scratch storage during runs
- Snowflake Bronze tables are the source of truth for state
- Batch-grained status updates (not per-row)

## Running the loader

```bash
# Full pipeline
python -m extraction.met.run --phase all

# Individual phases
python -m extraction.met.run --phase bootstrap  # Download CSV
python -m extraction.met.run --phase enrich     # API enrichment
python -m extraction.met.run --phase upload     # Upload to Bronze

# Check status
python -m extraction.met.run --phase status
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