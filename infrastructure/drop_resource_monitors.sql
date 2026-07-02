-- =============================================================================
-- drop_resource_monitors.sql: Rollback for create_resource_monitors.sql
-- =============================================================================
-- Detaches the monitor from the warehouse and drops it. Also resets
-- statement timeout parameters to Snowflake defaults.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Detach monitor before dropping (prevents dangling reference).
ALTER WAREHOUSE ARTWORK_WH UNSET RESOURCE_MONITOR;

-- Reset timeout parameters to defaults.
ALTER WAREHOUSE ARTWORK_WH UNSET STATEMENT_TIMEOUT_IN_SECONDS;
ALTER WAREHOUSE ARTWORK_WH UNSET STATEMENT_QUEUED_TIMEOUT_IN_SECONDS;

-- Drop the monitor.
DROP RESOURCE MONITOR IF EXISTS ARTWORK_WH_MONITOR;
