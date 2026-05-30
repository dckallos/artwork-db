-- =============================================================================
-- create_stages.sql ROLLBACK: drop the BRONZE.bronze_load_stage internal stage created
-- by create_stages.sql.
--
-- Paired forward: infrastructure/create_stages.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   Internal stages hold files PUT'd from extraction/* before COPY INTO
--   merges them into raw_*. Any files still resident in the stage at drop
--   time are deleted permanently. Phase 1A's extractor is expected to issue
--     REMOVE @bronze_load_stage PATTERN='.*';
--   after every successful load, so production runs should normally find
--   the stage empty. Verify with `LIST @bronze_load_stage;` before rolling
--   back if a load may be mid-flight.
--
-- Ordering:
--   Stages are schema-level objects inside ARTWORK_DB.BRONZE and are also
--   cascaded by create_databases_and_schemas.sql drop. `make down` runs create_stages.sql after create_bronze_tables.sql (raw_* tables)
--   so no COPY INTO can reference the stage at the moment of drop. This
--   paired script exists for fine-grained single-step rollback
--   (`make rollback FILE=...create_stages.sql...`).
--
-- Idempotency:
--   DROP STAGE IF EXISTS is safe pre-create and safe to re-run. The fully
--   qualified ARTWORK_DB.BRONZE.bronze_load_stage path keeps this script
--   independent of session context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP STAGE IF EXISTS ARTWORK_DB.BRONZE.bronze_load_stage;
