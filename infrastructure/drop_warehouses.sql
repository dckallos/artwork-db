-- =============================================================================
-- create_warehouses.sql ROLLBACK: drop compute warehouses created by create_warehouses.sql.
--
-- Paired forward: infrastructure/create_warehouses.sql.
-- Applied by:     make rollback FILE=infrastructure/create_warehouses.sql
--                 or make down via the sibling snowflake-toolkit orchestrator.
--
-- Idempotency:
--   DROP WAREHOUSE IF EXISTS is safe before create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP WAREHOUSE IF EXISTS ARTWORK_WH_PROD;
DROP WAREHOUSE IF EXISTS ARTWORK_WH_STAGING;
DROP WAREHOUSE IF EXISTS ARTWORK_WH;
