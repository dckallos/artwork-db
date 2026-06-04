-- =============================================================================
-- create_api_integration.sql ROLLBACK (post-renumber 2026-05-27): drop the GitHub API integration.
--
-- Paired forward: git-setup/create_api_integration.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   This drop must run AFTER the GIT REPOSITORY object that references the
--   integration has been dropped (create_git_repository.sql rollback). Snowflake will reject
--   DROP API INTEGRATION if any GIT REPOSITORY still depends on it. The make
--   targets handle this automatically:
--     - `make down` applies all paired drops in REVERSE order (create_git_repository.sql -> create_api_integration.sql
--       -> create_git_ops_db.sql) so this constraint is satisfied transparently.
--     - `make rollback FILE=git-setup/create_api_integration.sql`
--       assumes create_git_repository.sql has already been rolled back (or was never applied).
--
-- Renumber note (2026-05-27):
--   This file is the paired drop for what used to be create_git_ops_db.sql (API integration).
--   The forward / drop pair was renumbered to create_api_integration.sql so that the SECRET +
--   schema host now live in create_git_ops_db.sql. The matching DROP SECRET statement that
--   previously lived here has moved to drop_git_ops_db.sql (section
--   4.4a) where it is run before DROP SCHEMA / DROP DATABASE using the
--   fully qualified ARTWORK_OPS.GIT.github_pat_artwork_db name -- see
--   section 3.3.3 Q2 for why fully qualified is required to bypass 090105.
--
-- Idempotency:
--   DROP API INTEGRATION IF EXISTS is safe pre-create and safe to re-run.
--   Account-level statement; no USE DATABASE / USE SCHEMA context required.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Drop the API integration. If a GIT REPOSITORY still references it,
-- Snowflake raises:
--   003531 (42000): SQL compilation error: API_INTEGRATION
--                   'GITHUB_ARTWORK_DB_INTEGRATION' is in use.
-- Roll back create_git_repository.sql first if you see that error.
DROP API INTEGRATION IF EXISTS GITHUB_ARTWORK_DB_INTEGRATION;
