-- =============================================================================
-- create_alerts.sql ROLLBACK: drop the alerts and audit table created by
-- create_alerts.sql.
--
-- Paired forward: infrastructure/create_alerts.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   Every detected-fork incident row is permanently destroyed (Time Travel
--   recoverable via UNDROP TABLE within the schema's
--   DATA_RETENTION_TIME_IN_DAYS window). Rebuilding the table from a fresh
--   create_alerts.sql apply yields an empty incident log; historical incidents
--   are gone unless restored from Time Travel.
--
-- Ordering:
--   `make down` runs this drop in REVERSE manifest order: alerts FIRST in the
--   alert-bearing region (so the scheduled alert stops firing before any
--   object it references -- QUERY_HISTORY_BY_USER, the incidents table -- is
--   torn down). Snowflake does NOT support ALTER ALERT IF EXISTS, so DROP
--   ALERT IF EXISTS alone is sufficient (it cancels in-flight runs and
--   prevents future runs from starting).
--
-- Idempotency:
--   DROP ALERT IF EXISTS / DROP TABLE IF EXISTS are safe pre-create and safe
--   to re-run. Fully qualified ARTWORK_DB.BRONZE.* paths keep this independent
--   of session USE context.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Stop the schedule first (defensive; DROP ALERT also cancels in-flight runs).
DROP ALERT IF EXISTS ARTWORK_DB.BRONZE.CORTEX_FORK_ALERT;

-- Then destroy the audit table.
DROP TABLE IF EXISTS ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS;
