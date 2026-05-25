-- =============================================================================
-- V002 ROLLBACK: drop the ARTWORK_WH virtual warehouse created by V002.
--
-- Paired forward: infrastructure/V002__create_warehouses.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   Warehouses are account-level objects independent of ARTWORK_DB, so this
--   drop is order-independent of V003 (databases) and may run before or
--   after. `make down` applies it after V003 in the reverse chain (V009 ->
--   ... -> V002 -> V001).
--
-- Active-session note:
--   DROP WAREHOUSE IF EXISTS succeeds even when sessions are currently using
--   the warehouse; in-flight queries are cancelled by Snowflake at drop
--   time. Co-ordinate the rollback with any active Phase 1A load before
--   invoking `make down`, or pre-suspend with:
--     snow sql -c admin -q "ALTER WAREHOUSE ARTWORK_WH SUSPEND;"
--
-- Resource monitor note:
--   The current V002 forward does not attach a resource monitor, but the
--   project's roadmap includes one. If a resource monitor is attached to
--   ARTWORK_WH at drop time, the attachment is removed automatically with
--   the warehouse. The resource monitor itself is an account-level object
--   with no paired drop script (account-level monitors are intentionally
--   outside the V### chain); drop it manually for full account cleanup with:
--     snow sql -c admin -q "DROP RESOURCE MONITOR IF EXISTS <name>;"
--
-- Idempotency:
--   DROP WAREHOUSE IF EXISTS is safe pre-create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP WAREHOUSE IF EXISTS ARTWORK_WH;
