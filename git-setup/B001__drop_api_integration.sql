-- =============================================================================
-- B001 ROLLBACK: drop the GitHub API integration.
--
-- Paired forward: git-setup/B001__create_api_integration.sql.
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
--     - `make rollback FILE=git-setup/B001__create_api_integration.sql`
--       assumes B003 has already been rolled back (or was never applied).
--
-- Idempotency:
--   DROP ... IF EXISTS makes every statement safe to re-run and safe to run
--   even if the paired create script was never applied.
--
-- Private repo addendum:
--   If the forward script's PRIVATE REPO ONLY block was uncommented to create
--   github_pat_artwork_db, the matching DROP SECRET below cleans it up. It is
--   wrapped in DROP SECRET IF EXISTS so it is a no-op for public-repo setups
--   where the secret was never created.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Drop the API integration. If a GIT REPOSITORY still references it, Snowflake
-- raises:
--   003531 (42000): SQL compilation error: API_INTEGRATION
--                   'github_artwork_db_integration' is in use.
-- Roll back B003 first if you see that error.
DROP API INTEGRATION IF EXISTS github_artwork_db_integration;

-- Drop the optional GitHub PAT secret (private-repo path only). Safe no-op
-- when the secret was never created.
DROP SECRET IF EXISTS github_pat_artwork_db;
