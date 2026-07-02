-- =============================================================================
-- show_pipeline_status.sql -- READ-ONLY ad-hoc check: Met pipeline + object status.
--
-- Run via: scripts/check.sh scripts/sql/show_pipeline_status.sql
-- Safe anytime; makes no changes. Gives a UI-independent snapshot of "where the
-- pipeline stands" -- useful right after a connection break to re-orient without
-- the Snowsight stream. Counts are 0 pre-seed (Section C not yet built).
--
-- Runs as the connection's default role (admin / ACCOUNTADMIN), which inherits
-- ARTWORK_ADMIN (SYSADMIN -> ARTWORK_ADMIN) and can therefore SELECT/SHOW these.
-- =============================================================================

-- 1) Row counts across the control / snapshot / worklist / run-control objects.
SELECT 'MET_ENRICHMENT_CONTROL'      AS object, COUNT(*) AS row_count FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
UNION ALL SELECT 'MET_CSV_SNAPSHOT',           COUNT(*) FROM ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT
UNION ALL SELECT 'MET_WORKLIST (pending work)', COUNT(*) FROM ARTWORK_DB.BRONZE.MET_WORKLIST
UNION ALL SELECT 'RUN_CONTROL',                COUNT(*) FROM ARTWORK_DB.BRONZE.RUN_CONTROL
ORDER BY object;

-- 2) Enrichment status breakdown (empty until the control table is seeded).
SELECT enrichment_status, COUNT(*) AS n
FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
GROUP BY enrichment_status
ORDER BY n DESC;

-- 3) Lease-reclaim task: definition + current state (started/suspended).
SHOW TASKS LIKE 'MET_LEASE_RECLAIM_TASK' IN SCHEMA ARTWORK_DB.BRONZE;

-- 4) Most recent lease-reclaim task runs (empty if it has not fired yet).
SELECT name, state, scheduled_time, completed_time, error_message
FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.TASK_HISTORY(
        TASK_NAME => 'MET_LEASE_RECLAIM_TASK',
        RESULT_LIMIT => 10))
ORDER BY scheduled_time DESC;
