-- =============================================================================
-- create_git_ops_db.sql (post-renumber 2026-05-27): Create the ARTWORK_OPS database, the
-- ARTWORK_OPS.GIT schema, and the github_pat_artwork_db SECRET that
-- create_api_integration.sql's API integration whitelists and create_git_repository.sql's GIT REPOSITORY binds to.
--
-- Applied by snow sql via scripts/apply_sql.sh. Must run BEFORE create_api_integration.sql (which
-- references ARTWORK_OPS.GIT.github_pat_artwork_db in its
-- ALLOWED_AUTHENTICATION_SECRETS clause) and BEFORE create_git_repository.sql (which references
-- the same secret in its GIT_CREDENTIALS clause).
--
-- Rename rationale (2026-05-27): the prior create_git_ops_db.sql created the API integration,
-- which is account-level and cannot reference a schema-level SECRET that
-- does not yet exist. The renumber places DB + schema + SECRET in create_git_ops_db.sql and
-- promotes the API integration to create_api_integration.sql so the secret exists by the time it
-- is referenced. See Phase 0.6 IaC strategy section 3.3.3.
--
-- Idempotent (ADDITIVE, NOT destructive): CREATE DATABASE / CREATE SCHEMA use
-- IF NOT EXISTS so existing ARTWORK_OPS / ARTWORK_OPS.GIT (from earlier applies)
-- pass through cleanly. The SECRET uses CREATE SECRET IF NOT EXISTS followed by a
-- convergent ALTER SECRET ... SET so a re-run NEVER changes the secret's object
-- identity.
--
-- WHY NOT CREATE OR REPLACE (regression fixed 2026-05-31): CREATE OR REPLACE is an
-- atomic drop+recreate -> the secret gets a NEW internal object identity on every
-- run. The Snowsight Workspace's Git push binding ("secret from configuration")
-- references the prior object identity, so a full `make iac` ORPHANED that binding
-- and broke push with "Secret 'secret from configuration' does not exist or not
-- authorized." IF NOT EXISTS keeps the object stable; ALTER ... SET updates the
-- credential value in place. Routine applies should also prefer `make infra`
-- (V+R only) so this B-phase git-setup does not re-run at all.
--
-- Paired rollback: git-setup/drop_git_ops_db.sql.
--
-- APPLY-TIME INJECTION (private repo): the SECRET below stores no committed
-- PAT. The PASSWORD value is the snow sql templating placeholder
-- <% github_pat %>, which is substituted at apply time from a gitignored env
-- file via:
--
--   snow sql ... -D "github_pat=${GITHUB_PAT}"
--
-- No PAT ever lands in a committed file. Rotation = update the gitignored env
-- file and re-run create_git_ops_db.sql (make iac); the ALTER SECRET ... SET
-- below re-applies the new PAT in place without disturbing the object identity.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_OPS
    COMMENT = 'Operational and tooling objects for the artwork pipeline (Git, scheduled procs, etc.).';

USE DATABASE ARTWORK_OPS;

CREATE SCHEMA IF NOT EXISTS GIT
    COMMENT = 'Holds the GIT REPOSITORY object pointing at artwork-db and the SECRET that authenticates it.';

USE SCHEMA GIT;

-- Stable object identity (CREATE ... IF NOT EXISTS), convergent credential
-- (ALTER ... SET). See the header note "WHY NOT CREATE OR REPLACE".
CREATE SECRET IF NOT EXISTS github_pat_artwork_db
    TYPE     = PASSWORD
    USERNAME = 'dckallos'
    PASSWORD = '<% github_pat %>'
    COMMENT  = 'GitHub PAT for the artwork-db repository. Injected at apply time from a gitignored env file; rotate by updating that file and re-running create_git_ops_db.sql.';

-- Re-apply username + PAT in place on every run (rotation path) WITHOUT changing
-- the secret's object identity, so the Snowsight Workspace push binding survives.
ALTER SECRET IF EXISTS github_pat_artwork_db SET
    USERNAME = 'dckallos'
    PASSWORD = '<% github_pat %>';
