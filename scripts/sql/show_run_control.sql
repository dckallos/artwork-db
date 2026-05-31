-- =============================================================================
-- show_run_control.sql -- READ-ONLY ad-hoc check for BRONZE.RUN_CONTROL.
--
-- Run via: scripts/check.sh scripts/sql/show_run_control.sql
-- Safe anytime; makes no changes. RUN_CONTROL is empty until a run writes it,
-- so 0 rows is normal pre-use.
--
-- Purpose: observe durable run progress INDEPENDENT of the Snowsight UI stream.
-- If a Cortex window is stunned and the UI stops rendering, a writer that
-- checkpoints into RUN_CONTROL is still observable here from any other channel.
-- =============================================================================

-- 1) Latest checkpoint per run_id (one row per run; most recent step shown).
SELECT
    run_id,
    step          AS latest_step,
    status,
    note,
    session_id    AS last_writer_session,
    query_tag,
    updated_at
FROM ARTWORK_DB.BRONZE.RUN_CONTROL
QUALIFY ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY updated_at DESC) = 1
ORDER BY updated_at DESC;

-- 2) Full step trail for the single most-recently-touched run_id.
SELECT run_id, step, status, note, session_id, query_tag, created_at, updated_at
FROM ARTWORK_DB.BRONZE.RUN_CONTROL
WHERE run_id = (
    SELECT run_id FROM ARTWORK_DB.BRONZE.RUN_CONTROL
    ORDER BY updated_at DESC LIMIT 1
)
ORDER BY created_at;

-- 3) Dual-instance smell: any (run_id, step) written by MORE THAN ONE session.
--    Rows here mean two windows touched the same checkpoint -> investigate.
SELECT
    run_id,
    step,
    COUNT(DISTINCT session_id) AS distinct_writer_sessions,
    ARRAY_AGG(DISTINCT session_id) AS sessions
FROM ARTWORK_DB.BRONZE.RUN_CONTROL
GROUP BY run_id, step
HAVING COUNT(DISTINCT session_id) > 1
ORDER BY run_id, step;
