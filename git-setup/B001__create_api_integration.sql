-- =============================================================================
-- B001: Create the API integration that lets Snowflake reach GitHub.
--
-- This is a GIT-SETUP script applied by `snow sql` via scripts/apply_sql.sh.
-- It must run BEFORE the Snowflake GIT REPOSITORY object can be created
-- (see B003) and BEFORE any V### / R### migration can be applied from inside
-- Snowflake via EXECUTE IMMEDIATE FROM.
--
-- Idempotent: uses CREATE OR REPLACE so it can be re-run when allowed
-- prefixes or authentication secrets change. Paired rollback:
-- git-setup/B001__drop_api_integration.sql.
--
-- If the GitHub repo is PUBLIC, you do NOT need the SECRET block below.
-- If the GitHub repo is PRIVATE, create the SECRET first (see commented block)
-- and reference it via ALLOWED_AUTHENTICATION_SECRETS.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- -- PRIVATE REPO ONLY: uncomment and fill in a GitHub PAT (or fine-grained
-- -- token with Contents: Read). The SECRET must exist before the API
-- -- INTEGRATION can reference it.
-- CREATE OR REPLACE SECRET github_pat_artwork_db
--     TYPE     = PASSWORD
--     USERNAME = 'dckallos'
--     PASSWORD = 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
--     COMMENT  = 'GitHub PAT for the artwork-medallion-pipeline repository.';

CREATE OR REPLACE API INTEGRATION github_artwork_db_integration
    API_PROVIDER         = GIT_HTTPS_API
    API_ALLOWED_PREFIXES = ('https://github.com/dckallos/')
    -- ALLOWED_AUTHENTICATION_SECRETS = (github_pat_artwork_db)  -- PRIVATE REPO ONLY
    ENABLED              = TRUE
    COMMENT              = 'Git integration for the artwork-medallion-pipeline repo.';