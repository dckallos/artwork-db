-- =============================================================================
-- B003 ROLLBACK: drop the GIT REPOSITORY object that points back at the
-- artwork-db GitHub repo.
--
-- Paired forward: git-setup/B003__create_git_repository.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   This drop is the FIRST step of a full git-setup rollback. Both the API
--   integration (B001) and the host database (B002) cannot be cleanly dropped
--   while a GIT REPOSITORY still references them, so `make down` applies
--   B003 -> B002 -> B001 in that order automatically.
--
-- Idempotency:
--   DROP GIT REPOSITORY IF EXISTS is safe pre-create and safe to re-run.
--   The fully qualified ARTWORK_OPS.GIT.artwork_db path makes
--   this script independent of the current session's USE DATABASE / USE SCHEMA
--   context, so it works the same whether invoked directly or as part of the
--   bootstrap.py teardown loop.
--
-- Grant cleanup:
--   Dropping the GIT REPOSITORY automatically removes every grant on it (per
--   Snowflake's object-drop semantics), so no explicit REVOKE is required.
--   The earlier `GRANT READ ON GIT REPOSITORY ... TO ROLE ARTWORK_ADMIN` from
--   the forward script cascades away with the object itself.
--
-- Source mirror:
--   This DROP only removes Snowflake's mirror of the repo; the upstream
--   GitHub repository is unaffected.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Use the fully qualified name so this script is order-independent of any
-- preceding USE DATABASE / USE SCHEMA statement, including the case where
-- ARTWORK_OPS has already been torn down (IF EXISTS still applies cleanly).
DROP GIT REPOSITORY IF EXISTS ARTWORK_OPS.GIT.artwork_db;
