-- =============================================================================
-- create_git_repository.sql ROLLBACK: drop the GIT REPOSITORY object that points back at the
-- artwork-db GitHub repo.
--
-- Paired forward: git-setup/create_git_repository.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   This drop is the FIRST step of a full git-setup rollback. Both the API
--   integration (create_git_ops_db.sql) and the host database (create_api_integration.sql) cannot be cleanly dropped
--   while a GIT REPOSITORY still references them, so `make down` applies
--   create_git_repository.sql -> create_api_integration.sql -> create_git_ops_db.sql in that order automatically.
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
-- All three repos share the API integration + github_pat_artwork_db SECRET, so
-- all three must drop here (the FIRST git-setup rollback step) before
-- create_api_integration.sql / create_git_ops_db.sql can be torn down. Dropping
-- the repos leaves the shared integration + secret in place.
DROP GIT REPOSITORY IF EXISTS ARTWORK_OPS.GIT.artwork_db;
DROP GIT REPOSITORY IF EXISTS ARTWORK_OPS.GIT.dbt_diagnostics;
DROP GIT REPOSITORY IF EXISTS ARTWORK_OPS.GIT.snowflake_toolkit;
