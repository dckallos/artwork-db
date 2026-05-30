-- =============================================================================
-- create_git_repository.sql: Create the GIT REPOSITORY object that points back at this repo.
--
-- Applied by snow sql via scripts/apply_sql.sh. Must run AFTER create_git_ops_db.sql
-- (ARTWORK_OPS database + GIT schema + github_pat_artwork_db SECRET) and
-- create_api_integration.sql (github_artwork_db_integration with ALLOWED_AUTHENTICATION_SECRETS).
-- Paired rollback: git-setup/drop_git_repository.sql.
--
-- Object name (2026-05-27): the GIT REPOSITORY is named artwork_db to match
-- the actual GitHub repository dckallos/artwork-db. The earlier canonical
-- name artwork_medallion_pipeline was the GitHub repo name before it was
-- renamed; canonical Notion is updated to match the live repo on disk.
--
-- Phase ordering (2026-05-29 design decision "IaC Phase Ordering + Role Model:
-- Git mirror runs last"): git-setup (B) now runs LAST, AFTER infrastructure
-- (V then R). infrastructure/V001__create_roles.sql has therefore already
-- created ARTWORK_ADMIN by the time this script runs, so the trailing
-- "GRANT READ ON GIT REPOSITORY artwork_db TO ROLE ARTWORK_ADMIN;" below
-- succeeds in place. No relocation of that grant (e.g. to R001) is needed;
-- relocation would only matter if git-setup still ran before infra, which it
-- no longer does.
--
-- Once this runs, the contents of the repo are reachable from inside Snowflake
-- via the stage path:
--   @ARTWORK_OPS.GIT.artwork_db/branches/main/<path>
--
-- That means future operators can apply migrations from inside Snowflake, e.g.:
--   ALTER GIT REPOSITORY ARTWORK_OPS.GIT.artwork_db FETCH;
--   EXECUTE IMMEDIATE FROM
--     '@ARTWORK_OPS.GIT.artwork_db/branches/main/infrastructure/V001__create_roles.sql';
--
-- Private-repo authentication: this object binds the secret created by create_git_ops_db.sql
-- (ARTWORK_OPS.GIT.github_pat_artwork_db) via GIT_CREDENTIALS. The secret is
-- already whitelisted on the API integration by create_api_integration.sql via
-- ALLOWED_AUTHENTICATION_SECRETS. Together these three pieces eliminate the
-- anonymous-clone fallback that previously produced
--   093550 (22023): Failed to access the Git Repository. Operation 'clone'
--                   is not authorized.
-- See Phase 0.6 IaC strategy section 3.3.3.
--
-- Because create_git_ops_db.sql injects the real PAT at apply time via
--   snow sql ... -D "github_pat=${GITHUB_PAT}"
-- the github_pat_artwork_db secret already holds a working credential by the
-- time create_git_repository.sql runs, so create_git_repository.sql succeeds in the same make iac run. There is no
-- placeholder PAT, no ALTER SECRET step, and no rollback / re-apply cycle.
--
-- Idempotent: uses CREATE OR REPLACE so re-running picks up any change to
-- ORIGIN, API_INTEGRATION, or GIT_CREDENTIALS wiring.
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE ARTWORK_OPS;
USE SCHEMA GIT;

CREATE OR REPLACE GIT REPOSITORY artwork_db
    API_INTEGRATION = github_artwork_db_integration
    GIT_CREDENTIALS = ARTWORK_OPS.GIT.github_pat_artwork_db
    ORIGIN          = 'https://github.com/dckallos/artwork-db.git'
    COMMENT         = 'Read-only mirror of the artwork-db repo for in-Snowflake IaC.';

-- Pull the latest contents of all branches right away so subsequent
-- EXECUTE IMMEDIATE FROM statements work without a manual FETCH.
ALTER GIT REPOSITORY artwork_db FETCH;

-- Grant read access to ARTWORK_ADMIN so that role can drive future
-- in-Snowflake migrations without escalating to ACCOUNTADMIN.
GRANT READ ON GIT REPOSITORY artwork_db TO ROLE ARTWORK_ADMIN;
