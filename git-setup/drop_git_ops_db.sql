-- =============================================================================
-- create_git_ops_db.sql ROLLBACK (post-renumber 2026-05-28): drop the github_pat_artwork_db
-- SECRET, the ARTWORK_OPS.GIT schema, and the ARTWORK_OPS database created by
-- create_git_ops_db.sql.
--
-- Paired forward: git-setup/create_git_ops_db.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Renumber note (2026-05-28):
--   Under the prior layout this file dropped only the ARTWORK_OPS database
--   (it was the create_api_integration.sql drop). The renumber moves the SECRET + schema host into
--   create_git_ops_db.sql, so this drop now owns the SECRET teardown as well. The DROP SECRET
--   statement that previously lived in the API-integration drop (now
--   drop_api_integration.sql, section 4.4) has moved here.
--
-- Ordering:
--   This drop must run AFTER create_git_repository.sql (GIT REPOSITORY) and create_api_integration.sql (API integration)
--   have been rolled back, because the API integration's
--   ALLOWED_AUTHENTICATION_SECRETS clause references this secret and the GIT
--   REPOSITORY binds it via GIT_CREDENTIALS. The make targets handle this
--   automatically:
--     - `make down` applies all paired drops in REVERSE order (create_git_repository.sql -> create_api_integration.sql
--       -> create_git_ops_db.sql) so the dependents are gone before the secret is dropped.
--     - `make rollback FILE=git-setup/create_git_ops_db.sql` assumes
--       create_git_repository.sql and create_api_integration.sql have already been rolled back (or were never applied).
--
-- Fully qualified secret name:
--   DROP SECRET resolves its name against the current namespace BEFORE the
--   IF EXISTS guard is consulted, so an unqualified
--   DROP SECRET IF EXISTS github_pat_artwork_db; fails with 090105 on a
--   session that has no current database. The fully qualified
--   ARTWORK_OPS.GIT.github_pat_artwork_db name keeps this script independent
--   of session context. See Phase 0.6 IaC strategy section 3.3.3 Q1/Q2.
--
-- Idempotency:
--   DROP SECRET / DROP SCHEMA / DROP DATABASE IF EXISTS are all safe
--   pre-create and safe to re-run. Each succeeds silently when absent.
--
-- Caution / data safety:
--   DROP DATABASE removes ALL objects in ARTWORK_OPS. That database is an
--   operational / tooling database hosting the GIT REPOSITORY and the SECRET
--   and nothing else. The pipeline's medallion data lives in ARTWORK_DB
--   (BRONZE / SILVER / GOLD), which is unrelated to this script and is torn
--   down separately by V003__drop_databases_and_schemas.sql.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Drop the GitHub PAT secret first, fully qualified so no USE DATABASE /
-- USE SCHEMA context is required. Fully qualified is mandatory; see Phase 0.6
-- IaC strategy section 3.3.3 Q1/Q2 for why unqualified DROP SECRET fails 090105.
DROP SECRET IF EXISTS ARTWORK_OPS.GIT.github_pat_artwork_db;

-- Drop the GIT schema explicitly so the dependency chain is visible. The
-- subsequent DROP DATABASE would catch it anyway via CASCADE.
DROP SCHEMA IF EXISTS ARTWORK_OPS.GIT;

-- Drop the database. Cascades any remaining schemas / schema-level objects.
DROP DATABASE IF EXISTS ARTWORK_OPS;
