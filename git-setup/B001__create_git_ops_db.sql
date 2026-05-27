-- =============================================================================
-- B001: Create the database and schema that host every git-setup schema-level
-- object (the SECRET below, and the GIT REPOSITORY created later in B003),
-- then create the GitHub PAT SECRET inside ARTWORK_OPS.GIT.
--
-- Applied by `snow sql` via scripts/apply_sql.sh. First file in the git-setup
-- chain because CREATE SECRET is schema-level: it must live inside a real
-- schema, and that schema must exist before CREATE SECRET runs. The API
-- integration in B002 then references this SECRET by its fully qualified
-- name. Paired rollback: git-setup/B001__drop_git_ops_db.sql.
--
-- Why a dedicated ARTWORK_OPS database (not ARTWORK_DB)?
--   ARTWORK_OPS holds operational / tooling objects (the GIT REPOSITORY in
--   B003, the GitHub PAT SECRET below, future scheduled procs). Keeping them
--   out of ARTWORK_DB (BRONZE / SILVER / GOLD) keeps the medallion namespace
--   clean.
--
-- Idempotency:
--   - Database and schema use CREATE ... IF NOT EXISTS.
--   - SECRET uses CREATE OR REPLACE so re-applies pick up a rotated PAT.
--
-- The PAT placeholder below MUST be replaced before the GIT REPOSITORY in
-- B003 can FETCH. The recommended pattern is to apply this file as-is, then
-- rotate the value with:
--   ALTER SECRET ARTWORK_OPS.GIT.github_pat_artwork_db SET PASSWORD = '...';
-- from the admin connection. The real PAT must never be committed; see
-- Section 3.3.3 of this page for the full PAT-handling policy.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_OPS
    COMMENT = 'Operational and tooling objects for the artwork pipeline (Git, secrets, scheduled procs, etc.).';

USE DATABASE ARTWORK_OPS;

CREATE SCHEMA IF NOT EXISTS GIT
    COMMENT = 'Holds the GIT REPOSITORY object and the GitHub PAT SECRET for artwork-medallion-pipeline.';

USE SCHEMA GIT;

-- Schema-level CREATE SECRET: requires both USE DATABASE and USE SCHEMA above
-- (or a fully qualified name). The unqualified short name is used here so the
-- API integration in B002 and the GIT REPOSITORY in B003 can reference the
-- canonical fully qualified path ARTWORK_OPS.GIT.github_pat_artwork_db.
--
-- TYPE = PASSWORD stores the GitHub username + PAT for basic-auth against
-- https://github.com/. Use a fine-grained token scoped to Contents: Read on
-- dckallos/artwork-medallion-pipeline (PAT classic with `repo` also works).
--
-- The PASSWORD value below is a PLACEHOLDER. Rotate to the real PAT
-- immediately after the first apply with:
--   ALTER SECRET ARTWORK_OPS.GIT.github_pat_artwork_db SET PASSWORD = '<your_github_pat>';
-- from the admin connection. See Section 3.3.3 on this page for the full
-- PAT-handling policy.

CREATE OR REPLACE SECRET github_pat_artwork_db
    TYPE     = PASSWORD
    USERNAME = 'dckallos'
    PASSWORD = 'REPLACE_WITH_GITHUB_PAT_DO_NOT_COMMIT'
    COMMENT  = 'GitHub PAT used by github_artwork_db_integration to FETCH the private artwork-medallion-pipeline repo. Rotate immediately after first apply via ALTER SECRET ... SET PASSWORD.';
