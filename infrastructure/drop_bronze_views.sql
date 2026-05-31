-- =============================================================================
-- create_bronze_views.sql ROLLBACK: drop the Bronze views created by
-- create_bronze_views.sql.
--
-- Paired forward: infrastructure/create_bronze_views.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   `make down` runs this drop (paired with create_bronze_views.sql) in REVERSE
--   manifest order, BEFORE create_bronze_tables.sql is dropped, so the view is
--   gone before its base tables (MET_ENRICHMENT_CONTROL / MET_CSV_SNAPSHOT). A
--   view also cascades automatically when its base tables or the schema are
--   dropped; this paired script exists for fine-grained single-step rollback.
--
-- Idempotency:
--   DROP VIEW IF EXISTS is safe pre-create and safe to re-run. Fully qualified
--   ARTWORK_DB.BRONZE.* paths keep this independent of session USE context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP VIEW IF EXISTS ARTWORK_DB.BRONZE.MET_WORKLIST;
