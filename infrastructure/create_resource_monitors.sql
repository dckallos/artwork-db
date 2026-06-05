-- =============================================================================
-- create_resource_monitors.sql: Cost controls for compute warehouses
-- =============================================================================
-- DBA-OWNED. This is Snowflake-kernel enforcement -- no amount of dbt macro
-- tampering or engineer misconfiguration can bypass these controls.
--
-- Controls applied:
--   1. RESOURCE MONITOR: hard monthly credit ceiling with suspend triggers.
--   2. STATEMENT_TIMEOUT_IN_SECONDS: kills runaway queries (bad joins, full scans).
--   3. STATEMENT_QUEUED_TIMEOUT_IN_SECONDS: prevents pile-up when suspended.
--
-- Paired rollback: infrastructure/drop_resource_monitors.sql
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- ---------------------------------------------------------------------------
-- Resource Monitor: monthly credit ceiling for the primary warehouse.
-- Notify at 75%, suspend warehouse at 95%, force-kill at 100%.
-- Adjust CREDIT_QUOTA based on account budget (trial = 400 total credits).
-- ---------------------------------------------------------------------------
CREATE RESOURCE MONITOR IF NOT EXISTS ARTWORK_WH_MONITOR
    WITH
        CREDIT_QUOTA = 20
        FREQUENCY = MONTHLY
        START_TIMESTAMP = IMMEDIATELY
        TRIGGERS
            ON 75 PERCENT DO NOTIFY
            ON 95 PERCENT DO SUSPEND
            ON 100 PERCENT DO SUSPEND_IMMEDIATE;

-- Attach the monitor to the warehouse.
ALTER WAREHOUSE ARTWORK_WH SET RESOURCE_MONITOR = ARTWORK_WH_MONITOR;

-- ---------------------------------------------------------------------------
-- Statement timeout: 15 minutes max per query. Kills Cartesian joins, runaway
-- full-table scans, and any dbt model that takes longer than it should.
-- 900s is generous for an X-Small warehouse processing <500k rows.
-- ---------------------------------------------------------------------------
ALTER WAREHOUSE ARTWORK_WH SET STATEMENT_TIMEOUT_IN_SECONDS = 900;

-- ---------------------------------------------------------------------------
-- Queue timeout: if the warehouse is suspended (by the resource monitor or
-- manually), don't let queries pile up waiting. Fail fast after 2 minutes.
-- ---------------------------------------------------------------------------
ALTER WAREHOUSE ARTWORK_WH SET STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 120;
