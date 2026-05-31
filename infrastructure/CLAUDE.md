# infrastructure/CLAUDE.md

This directory contains all Snowflake DDL as create/drop pairs.

## Critical rules for this directory

1. ALWAYS maintain create_*.sql / drop_*.sql pairing
2. Use IF NOT EXISTS for stateful objects (databases, tables, users)
3. Use OR REPLACE for stateless objects (views, file formats, tasks)
4. After creating new DDL, update scripts/manifest.txt with the create script
5. Test idempotency by running the same create script twice

## Current objects (verify against manifest.txt)

- Account parameters (ABORT_DETACHED_QUERY)
- Roles (ARTWORK_ADMIN, ARTWORK_LOADER, ARTWORK_TRANSFORMER)
- Warehouses (ARTWORK_WH)
- Databases/schemas (ARTWORK_DB with BRONZE, SILVER, GOLD)
- Tables (RAW_*, MET_ENRICHMENT_CONTROL, MET_CSV_SNAPSHOT, RUN_CONTROL)
- Views (MET_WORKLIST)
- Service user (ARTWORK_LOADER_SVC)
- Tasks (MET_LEASE_RECLAIM_TASK)

## Before editing

```bash
# Check what will be affected
scripts/check.sh scripts/sql/show_pipeline_status.sql

# Always run after changes
make infra  # Safe, idempotent
```