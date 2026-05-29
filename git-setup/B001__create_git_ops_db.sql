-- =============================================================================
-- B001 (post-renumber 2026-05-27): Create the ARTWORK_OPS database, the
-- ARTWORK_OPS.GIT schema, and the github_pat_artwork_db SECRET that
-- B002's API integration whitelists and B003's GIT REPOSITORY binds to.
--
-- Applied by snow sql via scripts/apply_sql.sh. Must run BEFORE B002 (which
-- references ARTWORK_OPS.GIT.github_pat_artwork_db in its
-- ALLOWED_AUTHENTICATION_SECRETS clause) and BEFORE B003 (which references
-- the same secret in its GIT_CREDENTIALS clause).
--
-- Rename rationale (2026-05-27): the prior B001 created the API integration,
-- which is account-level and cannot reference a schema-level SECRET that
-- does not yet exist. The renumber places DB + schema + SECRET in B001 and
-- promotes the API integration to B002 so the secret exists by the time it
-- is referenced. See Phase 0.6 IaC strategy section 3.3.3.
--
-- Idempotent: CREATE DATABASE / CREATE SCHEMA use IF NOT EXISTS so existing
-- ARTWORK_OPS / ARTWORK_OPS.GIT (from earlier applies) pass through cleanly.
-- CREATE OR REPLACE SECRET handles both the first-time create and any later
-- re-injection of the PAT when B001 is re-run with an updated env file.
--
-- Paired rollback: git-setup/B001__drop_git_ops_db.sql.
--
-- APPLY-TIME INJECTION (private repo): the SECRET below stores no committed
-- PAT. The PASSWORD value is the snow sql templating placeholder
-- <% github_pat %>, which is substituted at apply time from a gitignored env
-- file via:
--
--   snow sql ... -D "github_pat=${GITHUB_PAT}"
--
-- No PAT ever lands in a committed file. Rotation = update the gitignored env
-- file and re-run B001 (make iac). There is no ALTER SECRET step.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_OPS
    COMMENT = 'Operational and tooling objects for the artwork pipeline (Git, scheduled procs, etc.).';

USE DATABASE ARTWORK_OPS;

CREATE SCHEMA IF NOT EXISTS GIT
    COMMENT = 'Holds the GIT REPOSITORY object pointing at artwork-db and the SECRET that authenticates it.';

USE SCHEMA GIT;

CREATE OR REPLACE SECRET github_pat_artwork_db
    TYPE     = PASSWORD
    USERNAME = 'dckallos'
    PASSWORD = '<% github_pat %>'
    COMMENT  = 'GitHub PAT for the artwork-db repository. Injected at apply time from a gitignored env file; rotate by updating that file and re-running B001.';
