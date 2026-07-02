-- =============================================================================
-- drop_mcp_integration.sql: Paired rollback for create_mcp_integration.sql.
--
-- Drops the EXTERNAL MCP SERVER first (dependent), then the API integration.
-- Safe to run even if objects do not exist (IF EXISTS).
--
-- WARNING: Dropping the API integration permanently deletes all stored OAuth
-- configuration and secrets. Ensure no agents are currently using the MCP
-- server before running this.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP EXTERNAL MCP SERVER IF EXISTS ARTWORK_OPS.GIT.GITHUB_MCP_SERVER;
DROP API INTEGRATION IF EXISTS GITHUB_MCP_INTEGRATION;
