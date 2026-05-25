-- =============================================================================
-- B002: Create the database and schema that will physically host the
-- GIT REPOSITORY object created in B003.
--
-- Applied by `snow sql` via scripts/apply_sql.sh. Must run AFTER B001 and BEFORE
-- B003. Paired rollback: git-setup/B002__drop_git_ops_db.sql.
--
-- The GIT REPOSITORY object is a first-class schema object (like a table or
-- stage). It needs a home. We use a dedicated ARTWORK_OPS database to keep
-- operational / tooling objects separate from the pipeline's data plane
-- (ARTWORK_DB) so Git artifacts do not pollute the medallion namespace.
--
-- Idempotent: uses CREATE ... IF NOT EXISTS.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_OPS
    COMMENT = 'Operational and tooling objects for the artwork pipeline (Git, scheduled procs, etc.).';

USE DATABASE ARTWORK_OPS;

CREATE SCHEMA IF NOT EXISTS GIT
    COMMENT = 'Holds the GIT REPOSITORY object pointing at artwork-medallion-pipeline.';