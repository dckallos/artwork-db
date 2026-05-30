-- =============================================================================
-- create_databases_and_schemas.sql ROLLBACK: drop the ARTWORK_DB database created by create_databases_and_schemas.sql. DROP DATABASE
-- cascades through BRONZE, SILVER, GOLD and every schema-level object
-- beneath them (tables, views, stages, file formats, tasks, streams, grants).
--
-- Paired forward: infrastructure/create_databases_and_schemas.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   ALL pipeline data in BRONZE / SILVER / GOLD is permanently destroyed.
--   Snowflake Time Travel retains the data per the database's
--   DATA_RETENTION_TIME_IN_DAYS setting and can be recovered via
--     UNDROP DATABASE ARTWORK_DB;
--   within the retention window. Beyond that window, recovery requires a
--   Fail-safe restore (Snowflake Support engagement) or full re-ingestion
--   from the museum APIs.
--
-- Ordering:
--   `make down` runs create_databases_and_schemas.sql drop after create_file_formats.sql - create_tasks.sql drops, so the targeted
--   schema-level objects beneath ARTWORK_DB are already gone by the time
--   this script executes; DROP DATABASE then removes the (mostly empty)
--   container. When invoked standalone (`make rollback FILE=...create_databases_and_schemas.sql...`),
--   the cascading DROP DATABASE removes every remaining schema-level object
--   in one statement. Either invocation path is safe.
--
-- Suspend before drop:
--   Snowflake does NOT require ALTER ... SUSPEND_TASKS before DROP DATABASE;
--   any active tasks in the database are cancelled and dropped with the
--   parent. No pre-suspend dance needed.
--
-- Idempotency:
--   DROP DATABASE IF EXISTS is safe pre-create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP DATABASE IF EXISTS ARTWORK_DB;
