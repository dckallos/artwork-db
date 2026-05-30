-- =============================================================================
-- create_bronze_tables.sql ROLLBACK: drop the seven Bronze raw_* tables and the extraction_log
-- table created by create_bronze_tables.sql.
--
-- Paired forward: infrastructure/create_bronze_tables.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   Every loaded row in raw_met_objects, raw_aic_artworks, raw_cma_artworks,
--   raw_cma_creators, raw_cma_exhibitions, raw_smithsonian_objects, and
--   extraction_log is permanently destroyed. Snowflake Time Travel keeps
--   each table recoverable via
--     UNDROP TABLE ARTWORK_DB.BRONZE.<table_name>;
--   within the schema's DATA_RETENTION_TIME_IN_DAYS window. Beyond that,
--   recovery requires re-ingestion from the museum APIs.
--   If the intent is to reset schemas rather than discard data, consider
--   TRUNCATE TABLE instead, or snapshot via
--     CREATE TABLE <table>_backup CLONE <table>;
--   first.
--
-- Ordering:
--   `make down` runs create_bronze_tables.sql after create_tasks.sql (tasks) and create_service_user.sql (service user), so no
--   task is mid-MERGE and the loader cannot insert during the drop window.
--   These tables are also cascaded by create_databases_and_schemas.sql drop (DROP DATABASE); this paired
--   script exists for fine-grained single-step rollback.
--
-- Idempotency:
--   DROP TABLE IF EXISTS is safe pre-create and safe to re-run. Fully
--   qualified ARTWORK_DB.BRONZE.* paths keep this script independent of the
--   session's USE DATABASE / USE SCHEMA context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_met_objects;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_aic_artworks;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_cma_artworks;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_cma_creators;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_cma_exhibitions;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.raw_smithsonian_objects;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.extraction_log;
