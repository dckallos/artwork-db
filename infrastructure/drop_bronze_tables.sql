-- =============================================================================
-- create_bronze_tables.sql ROLLBACK: drop the seven Bronze raw_*/extraction_log
-- tables plus the two Met orchestration tables (MET_ENRICHMENT_CONTROL,
-- MET_CSV_SNAPSHOT) created by create_bronze_tables.sql.
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

DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_AIC_AGENTS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.AIC_LOAD_WATERMARK;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_CMA_ARTWORKS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_CMA_CREATORS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_CMA_EXHIBITIONS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.RAW_SMITHSONIAN_OBJECTS;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.EXTRACTION_LOG;
-- Met enrichment orchestration pair (Session 3). MET_WORKLIST (a VIEW over these)
-- is dropped first by the paired drop_bronze_views.sql, which the manifest places
-- AFTER create_bronze_tables.sql -> reversed teardown runs it earlier. Safe to drop
-- the bases here without an explicit view drop.
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL;
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT;
