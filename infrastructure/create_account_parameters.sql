-- =============================================================================
-- create_account_parameters.sql: Account-level Snowflake session parameters.
--
-- WHY (connection-resilience hardening, 2026-05-31; owner-decided per
-- docs/context/connection-resilience.md rec #2):
--
--   ABORT_DETACHED_QUERY = TRUE
--     Snowflake auto-aborts any in-progress query 5 minutes after the client
--     connection is detected as lost (browser tab discard, OS sleep, network
--     blip, VPN reconnect, websocket break). Defaults to FALSE: an orphaned
--     Cortex-Code Snowsight session can keep running queries indefinitely after
--     the UI stuns -- which is one half of the dual-instance "ghost fork"
--     incident pattern recorded in docs/context/session-3-progress-log.md.
--     Verified: https://docs.snowflake.com/en/sql-reference/parameters
--
--   This does NOT prevent the agent process itself from continuing (the bigger
--   structural defect tracked in connection-resilience.md §4); it caps the
--   blast radius of any orphaned QUERY at 5 min. It pairs with the >1-cortex-
--   session alert (create_alerts.sql) which is the detective-side companion.
--
-- Idempotency: ALTER ACCOUNT SET is naturally idempotent -- re-running with the
-- same value is a no-op from the parameter's perspective. Treated as the
-- stateless/derived class of the idempotency split (no business data, just
-- account state), so reapplying is always safe.
--
-- Scope: ACCOUNT level. Only ACCOUNTADMIN can ALTER ACCOUNT, which is why this
-- runs as ACCOUNTADMIN (same role as create_roles.sql). Placed FIRST in the
-- manifest so the parameter is in effect before any subsequent session-bearing
-- DDL applies; subsequent migrations therefore inherit the safer default.
--
-- Paired rollback: infrastructure/drop_account_parameters.sql (UNSET reverts to
-- the Snowflake default, FALSE).
-- =============================================================================

USE ROLE ACCOUNTADMIN;

ALTER ACCOUNT SET ABORT_DETACHED_QUERY = TRUE;
