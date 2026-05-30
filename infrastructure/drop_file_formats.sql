-- =============================================================================
-- create_file_formats.sql ROLLBACK: drop the BRONZE schema file formats created by create_file_formats.sql
-- (json_raw and parquet_raw).
--
-- Paired forward: infrastructure/create_file_formats.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   File formats are schema-level objects inside ARTWORK_DB.BRONZE. They are
--   cascaded away automatically by create_databases_and_schemas.sql drop (DROP DATABASE). This script
--   exists so create_file_formats.sql can be rolled back independently
--   (`make rollback FILE=...create_file_formats.sql...`) without touching unrelated objects in
--   BRONZE. `make down` runs create_file_formats.sql after create_stages.sql (stages) so any stage that
--   referenced these formats is already gone, avoiding the in-use error.
--
-- Dependency error:
--   If any stage (create_stages.sql) still references json_raw or parquet_raw, Snowflake
--   raises:
--     003531 (42000): SQL compilation error: cannot drop FILE FORMAT
--                     '<name>' as it is referenced by STAGE(s).
--   Roll back create_stages.sql first if you see that error.
--
-- Idempotency:
--   DROP FILE FORMAT IF EXISTS is safe pre-create and safe to re-run. Fully
--   qualified ARTWORK_DB.BRONZE paths keep this script independent of the
--   session's USE DATABASE / USE SCHEMA context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP FILE FORMAT IF EXISTS ARTWORK_DB.BRONZE.json_raw;
DROP FILE FORMAT IF EXISTS ARTWORK_DB.BRONZE.parquet_raw;
