-- =============================================================================
-- create_tasks.sql ROLLBACK: drop the Met pipeline tasks created by
-- create_tasks.sql.
--
-- Paired forward: infrastructure/create_tasks.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   `make down` runs this drop FIRST (REVERSE manifest order: create_tasks.sql ->
--   create_bronze_views.sql -> ... -> create_roles.sql) so the scheduled task
--   stops firing before any object it references (MET_ENRICHMENT_CONTROL) is
--   torn down. This avoids a window in which the task fires against
--   partially-destroyed objects.
--
-- In-flight runs:
--   DROP TASK cancels any currently executing run and prevents future runs from
--   starting. No explicit SUSPEND is required for teardown. Snowflake does NOT
--   support ALTER TASK IF EXISTS, so a guarded suspend would need a Scripting
--   block; DROP TASK IF EXISTS alone is sufficient and idempotent.
--
-- Idempotency:
--   DROP TASK IF EXISTS is safe pre-create and safe to re-run. Fully qualified
--   ARTWORK_DB.BRONZE.* paths keep this independent of session USE context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP TASK IF EXISTS ARTWORK_DB.BRONZE.MET_LEASE_RECLAIM_TASK;
