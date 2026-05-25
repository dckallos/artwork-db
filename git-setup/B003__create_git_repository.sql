-- =============================================================================
-- B003: Create the GIT REPOSITORY object that points back at this repo.
--
-- Applied by `snow sql` via scripts/apply_sql.sh. Must run AFTER B001 (the API
-- integration exists) and B002 (the host schema exists). Paired rollback:
-- git-setup/B003__drop_git_repository.sql.
--
-- Once this runs, the contents of the repo are reachable from inside Snowflake
-- via the stage path:
--   @ARTWORK_OPS.GIT.artwork_medallion_pipeline/branches/main/<path>
--
-- That means future operators can apply migrations from inside Snowflake, e.g.:
--   ALTER GIT REPOSITORY ARTWORK_OPS.GIT.artwork_medallion_pipeline FETCH;
--   EXECUTE IMMEDIATE FROM
--     '@ARTWORK_OPS.GIT.artwork_medallion_pipeline/branches/main/infrastructure/V001__create_roles.sql';
--
-- Idempotent: uses CREATE OR REPLACE so re-running picks up any change to
-- ORIGIN or API_INTEGRATION wiring.
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE ARTWORK_OPS;
USE SCHEMA GIT;

CREATE OR REPLACE GIT REPOSITORY artwork_medallion_pipeline
    API_INTEGRATION = github_artwork_db_integration
    ORIGIN          = 'https://github.com/dckallos/artwork-medallion-pipeline.git'
    COMMENT         = 'Read-only mirror of the artwork-medallion-pipeline repo for in-Snowflake IaC.';

-- Pull the latest contents of all branches right away so subsequent
-- EXECUTE IMMEDIATE FROM statements work without a manual FETCH.
ALTER GIT REPOSITORY artwork_medallion_pipeline FETCH;

-- Grant read access to ARTWORK_ADMIN so that role can drive future
-- in-Snowflake migrations without escalating to ACCOUNTADMIN.
GRANT READ ON GIT REPOSITORY artwork_medallion_pipeline TO ROLE ARTWORK_ADMIN;