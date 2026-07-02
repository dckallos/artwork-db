-- =============================================================================
-- create_alerts.sql: Snowflake Alerts for the artwork-db pipeline.
--
-- CORTEX_FORK_ALERT -- detect Cortex-Code dual-instance "ghost fork" incidents
-- (rec #3 in docs/context/connection-resilience.md, owner-decided 2026-05-31).
--
-- WHY: a stunned Cortex-Code Snowsight window's backend keeps running while a
-- newly-opened tab spawns a second instance -- two agents writing the same
-- workspace files concurrently. Empirical evidence: the dual-instance incident
-- recorded in docs/context/session-3-progress-log.md. Today this is invisible
-- until scripts/check.sh is run on demand. This alert turns it into a 5-min
-- detection window with a durable audit trail.
--
-- Detection: more than one DISTINCT session with QUERY_TAG containing
-- 'cortex_code_snowsight' active in the last 10 minutes (overlap with the
-- 5-min schedule, so a fork that lasts <10 min is still caught). Limited to
-- USER_NAME = 'PORCHANALYTICS' to skip system / unrelated cortex_code traffic.
-- Source: ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER (~1 s latency,
-- not the 45-min ACCOUNT_USAGE.QUERY_HISTORY view) so detection is real-time.
--
-- Action: insert one row per detection into BRONZE.CORTEX_FORK_INCIDENTS. We
-- deliberately do NOT call SYSTEM$SEND_EMAIL: that requires a notification
-- integration (out of scope), and a self-contained durable log is more useful
-- for the learning project anyway -- the owner queries the table on resume to
-- see whether a fork happened in their absence.
--
-- Privileges (lockstep with create_roles.sql):
--   - GRANT EXECUTE ALERT ON ACCOUNT TO ROLE ARTWORK_ADMIN -- needed to
--     CREATE ALERT and have its scheduler fire.
--   - GRANT MONITOR EXECUTION ON ACCOUNT TO ROLE ARTWORK_ADMIN -- needed so
--     QUERY_HISTORY_BY_USER returns rows for ALL users (specifically
--     PORCHANALYTICS), not just ARTWORK_ADMIN's own history.
--   Both are pre-checked by scripts/bootstrap.py's privilege contract.
--
-- Idempotency:
--   - CORTEX_FORK_INCIDENTS is state-bearing -> CREATE TABLE IF NOT EXISTS
--     (per the class-based idempotency split in ddl-infrastructure.md).
--   - CORTEX_FORK_ALERT carries no business data -> CREATE OR REPLACE ALERT
--     (stateless, like tasks/views).
--   - Trailing ALTER ALERT ... RESUME activates the schedule (alerts are
--     created suspended, like tasks).
--
-- Paired rollback: infrastructure/drop_alerts.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- ---------------------------------------------------------------
-- Audit table: one row per detection
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CORTEX_FORK_INCIDENTS (
    detected_at      TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'UTC time the alert fired',
    session_count    NUMBER        NOT NULL COMMENT 'How many distinct cortex_code_snowsight sessions were active in the last 10 min',
    session_ids      ARRAY         COMMENT 'The offending session_ids (cast to STRING for display stability)',
    last_query_times ARRAY         COMMENT 'Per-session most-recent START_TIME (parallel to session_ids), to gauge fork lifetime',
    note             VARCHAR       COMMENT 'Human-readable note (e.g. resolution / acknowledgement)'
)
COMMENT = 'Audit log of dual-instance Cortex-Code "ghost fork" detections. Populated by CORTEX_FORK_ALERT every 5 min when >1 cortex_code_snowsight session is active for the workspace user.';

-- ---------------------------------------------------------------
-- The alert itself: 5-min schedule, CURRENT_TIMESTAMP() condition,
-- INSERT-into-incidents action.
-- ---------------------------------------------------------------
CREATE OR REPLACE ALERT CORTEX_FORK_ALERT
    WAREHOUSE = ARTWORK_WH
    SCHEDULE  = '5 MINUTE'
    COMMENT   = 'Detect >1 active cortex_code_snowsight session for PORCHANALYTICS in the last 10 min and write a row to CORTEX_FORK_INCIDENTS.'
    IF (EXISTS (
        SELECT 1
        FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(
            USER_NAME    => 'PORCHANALYTICS',
            RESULT_LIMIT => 1000
        ))
        WHERE START_TIME >= DATEADD(minute, -10, CURRENT_TIMESTAMP())
          AND QUERY_TAG ILIKE '%cortex_code_snowsight%'
        GROUP BY SESSION_ID
        HAVING COUNT(DISTINCT SESSION_ID) > 1
    ))
    THEN
        INSERT INTO CORTEX_FORK_INCIDENTS (session_count, session_ids, last_query_times, note)
        SELECT COUNT(DISTINCT q.SESSION_ID),
               ARRAY_AGG(DISTINCT q.SESSION_ID::STRING),
               ARRAY_AGG(q.MAX_START),
               'auto-detected by CORTEX_FORK_ALERT'
        FROM (
            SELECT SESSION_ID, MAX(START_TIME) AS MAX_START
            FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(
                USER_NAME    => 'PORCHANALYTICS',
                RESULT_LIMIT => 1000
            ))
            WHERE START_TIME >= DATEADD(minute, -10, CURRENT_TIMESTAMP())
              AND QUERY_TAG ILIKE '%cortex_code_snowsight%'
            GROUP BY SESSION_ID
        ) q;

-- A freshly created/replaced alert is SUSPENDED; resume it so the schedule fires.
ALTER ALERT CORTEX_FORK_ALERT RESUME;
