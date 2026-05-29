-- =============================================================================
-- B002 (post-renumber 2026-05-27): Create the account-level API integration
-- that lets Snowflake reach GitHub, and whitelist the SECRET created by B001
-- via ALLOWED_AUTHENTICATION_SECRETS.
--
-- Applied by snow sql via scripts/apply_sql.sh. Must run AFTER B001 (which
-- creates ARTWORK_OPS.GIT.github_pat_artwork_db) and BEFORE B003 (which
-- references both this integration and the same SECRET via GIT_CREDENTIALS).
--
-- Renumber rationale (2026-05-27): under the prior layout this file was B001,
-- but the API integration needs to reference an already-existing SECRET via
-- ALLOWED_AUTHENTICATION_SECRETS. Promoting it to B002 ensures the secret
-- in ARTWORK_OPS.GIT exists at this point in the chain. See Phase 0.6 IaC
-- strategy section 3.3.3.
--
-- Idempotent: CREATE OR REPLACE handles both first-time apply and later
-- changes to API_ALLOWED_PREFIXES / ALLOWED_AUTHENTICATION_SECRETS. Snowflake
-- only rejects the REPLACE if a GIT REPOSITORY currently depends on the
-- integration; B003's rollback handles that case.
--
-- Paired rollback: git-setup/B002__drop_api_integration.sql.
--
-- Private-repo bind chain (see section 3.3.3 of the Phase 0.6 IaC strategy):
--   1. B001 creates ARTWORK_OPS.GIT.github_pat_artwork_db SECRET.
--   2. B002 (this file) whitelists that secret on the API integration.
--   3. B003 references the same secret on the GIT REPOSITORY via
--      GIT_CREDENTIALS. Missing any of the three reproduces error
--      093550 (22023): Failed to access the Git Repository.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE API INTEGRATION github_artwork_db_integration
    API_PROVIDER                   = GIT_HTTPS_API
    API_ALLOWED_PREFIXES           = ('https://github.com/dckallos/')
    ALLOWED_AUTHENTICATION_SECRETS = (ARTWORK_OPS.GIT.github_pat_artwork_db)
    ENABLED                        = TRUE
    COMMENT                        = 'Git integration for the artwork-db repo.';
