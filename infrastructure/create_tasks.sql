-- =============================================================================
-- create_tasks.sql: Snowflake Tasks for the Met enrichment pipeline.
--
-- MET_LEASE_RECLAIM_TASK -- lease housekeeping. The Mac claims a batch of rows
-- in MET_ENRICHMENT_CONTROL (sets claimed_by_batch / claimed_at) before fetching
-- them locally. If the Mac crashes or is closed mid-batch, those rows stay leased
-- to a batch that will never finish and would never be re-fetched. This task
-- periodically resets leases older than the TTL so the next claim can pick them
-- up again. It runs Snowflake-side -- the Mac can be closed.
--
-- TTL = 30 min: far longer than a realistic batch fetch (a 500-2000 row batch at
-- ~20 rps finishes in ~25-100 s), so an in-flight batch is never reclaimed.
-- Schedule = hourly: reclaim is not time-urgent (no new claims happen while the
-- Mac is closed), and hourly keeps ARTWORK_WH spins minimal. Owner-decided
-- 2026-05-31 (met-deepdive.md Session-3 build).
--
-- Idempotency: CREATE OR REPLACE TASK -- a task carries no business data (only
-- run history), so it follows the stateless/derived class of the idempotency
-- split, like views/file formats/stages.
--
-- Lockstep: requires GRANT EXECUTE TASK ON ACCOUNT TO ROLE ARTWORK_ADMIN
-- (uncommented in create_roles.sql). A new task is created SUSPENDED; the
-- trailing ALTER ... RESUME starts the schedule.
-- Paired rollback: infrastructure/drop_tasks.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

CREATE OR REPLACE TASK MET_LEASE_RECLAIM_TASK
    WAREHOUSE = ARTWORK_WH
    SCHEDULE  = 'USING CRON 0 * * * * UTC'
    COMMENT   = 'Reset abandoned enrichment leases (claimed_at older than 30 min TTL) so stranded rows are re-claimable.'
AS
    UPDATE MET_ENRICHMENT_CONTROL
       SET claimed_by_batch = NULL,
           claimed_at       = NULL
     WHERE claimed_at IS NOT NULL
       AND claimed_at < DATEADD(minute, -30, CURRENT_TIMESTAMP());

-- A freshly created task is SUSPENDED; resume it so the schedule fires.
ALTER TASK MET_LEASE_RECLAIM_TASK RESUME;
