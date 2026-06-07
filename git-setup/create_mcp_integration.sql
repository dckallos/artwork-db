-- =============================================================================
-- create_mcp_integration.sql: Create the API integration and EXTERNAL MCP SERVER
-- that lets Cortex Agents (and Snowflake Intelligence / CoWork) invoke GitHub
-- tools (repos, issues, PRs, code search) on behalf of authenticated users.
--
-- Applied by snow sql via $(TOOLKIT_DIR)/apply_sql.sh. Must run AFTER
-- create_git_ops_db.sql (which creates ARTWORK_OPS.GIT schema) and AFTER
-- create_api_integration.sql (ordering in manifest.txt).
--
-- Idempotent (ADDITIVE, NOT destructive): CREATE ... IF NOT EXISTS keeps object
-- identity stable; ALTER ... SET converges mutable properties on re-apply.
-- The EXTERNAL MCP SERVER uses CREATE OR REPLACE because it has no dependents
-- that hold a binding to its object identity (unlike the Git SECRET).
--
-- APPLY-TIME INJECTION: OAuth credentials are never committed. The client_id
-- and client_secret are injected via snow sql templating placeholders:
--
--   snow sql ... -D "github_oauth_client_id=..." -D "github_oauth_client_secret=..."
--
-- (Passed through the Makefile VARS mechanism, same as github_pat.)
--
-- Paired rollback: git-setup/drop_mcp_integration.sql.
--
-- GitHub OAuth App setup (one-time, in GitHub UI):
--   Settings > Developer settings > OAuth Apps > New OAuth App
--   - Homepage URL: https://app.snowflake.com
--   - Authorization callback URL:
--       https://<account_identifier>.snowflakecomputing.com/oauth/complete
--   Note the Client ID and generate a Client Secret.
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE ARTWORK_OPS;
USE SCHEMA GIT;

-- -----------------------------------------------------------------------------
-- 1. API Integration (account-level, external_mcp provider)
-- -----------------------------------------------------------------------------
CREATE API INTEGRATION IF NOT EXISTS GITHUB_MCP_INTEGRATION
    API_PROVIDER         = external_mcp
    API_ALLOWED_PREFIXES = ('https://api.githubcopilot.com')
    API_USER_AUTHENTICATION = (
        TYPE                       = OAUTH,
        OAUTH_CLIENT_ID            = '<% github_oauth_client_id %>',
        OAUTH_CLIENT_SECRET        = '<% github_oauth_client_secret %>',
        OAUTH_TOKEN_ENDPOINT       = 'https://github.com/login/oauth/access_token',
        OAUTH_AUTHORIZATION_ENDPOINT = 'https://github.com/login/oauth/authorize'
    )
    ENABLED = TRUE
    COMMENT = 'MCP connector: GitHub tools for Cortex Agents (OAuth per-user).';

-- Converge mutable properties on re-apply (object identity preserved).
ALTER API INTEGRATION IF EXISTS GITHUB_MCP_INTEGRATION SET
    API_ALLOWED_PREFIXES = ('https://api.githubcopilot.com')
    API_USER_AUTHENTICATION = (
        TYPE                       = OAUTH,
        OAUTH_CLIENT_ID            = '<% github_oauth_client_id %>',
        OAUTH_CLIENT_SECRET        = '<% github_oauth_client_secret %>',
        OAUTH_TOKEN_ENDPOINT       = 'https://github.com/login/oauth/access_token',
        OAUTH_AUTHORIZATION_ENDPOINT = 'https://github.com/login/oauth/authorize'
    )
    ENABLED = TRUE
    COMMENT = 'MCP connector: GitHub tools for Cortex Agents (OAuth per-user).';

-- -----------------------------------------------------------------------------
-- 2. External MCP Server (schema-level, references the integration above)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE EXTERNAL MCP SERVER ARTWORK_OPS.GIT.GITHUB_MCP_SERVER
    WITH NAME = 'GitHub'
    API_INTEGRATION = GITHUB_MCP_INTEGRATION;
