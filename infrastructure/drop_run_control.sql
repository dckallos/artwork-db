-- =============================================================================
-- create_run_control.sql ROLLBACK: drop the BRONZE.RUN_CONTROL checkpoint table
-- created by create_run_control.sql.
--
-- Paired forward: infrastructure/create_run_control.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   Every checkpoint row is permanently destroyed. Snowflake Time Travel keeps
--   the table recoverable via
--     UNDROP TABLE ARTWORK_DB.BRONZE.RUN_CONTROL;
--   within the schema's DATA_RETENTION_TIME_IN_DAYS window. RUN_CONTROL holds
--   operational checkpoints (not source data), so loss is low-impact -- a new run
--   simply starts a fresh run_id.
--
-- Ordering:
--   RUN_CONTROL is an independent BRONZE table (no view/task depends on it), so
--   teardown order relative to the other Bronze drops does not matter. It is also
--   cascaded by create_databases_and_schemas.sql drop (DROP DATABASE); this paired
--   script exists for fine-grained single-step rollback.
--
-- Idempotency:
--   DROP TABLE IF EXISTS is safe pre-create and safe to re-run. Fully qualified
--   ARTWORK_DB.BRONZE.* path keeps this independent of session USE context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RUN_CONTROL;
