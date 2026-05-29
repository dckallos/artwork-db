-- =============================================================================
-- B002 ROLLBACK (post-renumber 2026-05-27): drop the GitHub API integration.
--
-- Paired forward: git-setup/B002__create_api_integration.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   This drop must run AFTER the GIT REPOSITORY object that references the
--   integration has been dropped (B003 rollback). Snowflake will reject
--   DROP API INTEGRATION if any GIT REPOSITORY still depends on it. The make
--   targets handle this automatically:
--     - `make down` applies all paired drops in REVERSE order (B003 -> B002
--       -> B001) so this constraint is satisfied transparently.
--     - `make rollback FILE=git-setup/B002__create_api_integration.sql`
--       assumes B003 has already been rolled back (or was never applied).
--
-- Renumber note (2026-05-27):
--   This file is the paired drop for what used to be B001 (API integration).
--   The forward / drop pair was renumbered to B002 so that the SECRET +
--   schema host now live in B001. The matching DROP SECRET statement that
--   previously lived here has moved to B001__drop_git_ops_db.sql (section
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
--                   'github_artwork_db_integration' is in use.
-- Roll back B003 first if you see that error.
DROP API INTEGRATION IF EXISTS github_artwork_db_integration;
