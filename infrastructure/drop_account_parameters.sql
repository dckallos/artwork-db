-- =============================================================================
-- create_account_parameters.sql ROLLBACK: revert account-level parameters set
-- by create_account_parameters.sql back to their Snowflake defaults.
--
-- Paired forward: infrastructure/create_account_parameters.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Destructive scope:
--   None at the data layer -- this only flips an account parameter back to its
--   default. ABORT_DETACHED_QUERY default = FALSE; UNSET reverts to that.
--   In-progress orphaned queries (post-rollback) will run until they hit a
--   warehouse statement_timeout or session policy idle limit instead of being
--   auto-aborted at 5 min. This is the original, less-safe behavior.
--
-- Ordering:
--   No object-level dependency. Account parameters are session-state, not data;
--   safe to roll back at any point in the teardown order. `make down` runs this
--   in REVERSE manifest order, so it rolls back near the END of teardown
--   (paired with its create at the START of apply).
--
-- Idempotency:
--   ALTER ACCOUNT UNSET on an already-default parameter is a no-op. Safe
--   pre-create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

ALTER ACCOUNT UNSET ABORT_DETACHED_QUERY;
