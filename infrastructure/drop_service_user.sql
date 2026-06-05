-- =============================================================================
-- create_service_user.sql ROLLBACK: drop the service users created by
-- create_service_user.sql -- ARTWORK_TRANSFORMER_SVC (dbt) and
-- ARTWORK_LOADER_SVC (extraction).
--
-- Paired forward: infrastructure/create_service_user.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   `make down` runs create_service_user.sql BEFORE create_roles.sql so each
--   service user is removed before its DEFAULT_ROLE (ARTWORK_TRANSFORMER /
--   ARTWORK_LOADER) is dropped. Within this script ARTWORK_TRANSFORMER_SVC is
--   dropped before ARTWORK_LOADER_SVC (reverse of create order). With IF EXISTS
--   on both scripts the reverse order also succeeds; the ordering is purely a
--   convention for cleaner OBJECT_HISTORY trails.
--
-- Owned-object check:
--   DROP USER fails with:
--     090105 (22023): Cannot perform DROP USER. The current user is the
--                     owner of <n> objects.
--   if either service user owns any Snowflake object. By design, both service
--   users are least-privilege: create_grants.sql grants INSERT / UPDATE / DELETE / SELECT
--   on BRONZE tables and READ / WRITE on stages (loader), and SELECT on BRONZE
--   plus CREATE on SILVER/GOLD (transformer), but does NOT grant OWNERSHIP.
--   Schemas and tables are owned by ARTWORK_ADMIN via create_databases_and_schemas.sql / create_bronze_tables.sql.
--   If a future change grants OWNERSHIP to this user (for example, custom
--   tables created by the loader at runtime), transfer ownership back to
--   ARTWORK_ADMIN with:
--     GRANT OWNERSHIP ON <object> TO ROLE ARTWORK_ADMIN
--       REVOKE CURRENT GRANTS;
--   before invoking this rollback.
--
-- Credential cleanup:
--   Each user's password and any registered RSA public key are removed
--   automatically with the user object. The matching `.env` file
--   (SNOWFLAKE_PASSWORD) and any operator-side key files are NOT touched by
--   this script and should be cleaned up manually if the account is being
--   decommissioned.
--
-- Idempotency:
--   DROP USER IF EXISTS is safe pre-create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP USER IF EXISTS ARTWORK_TRANSFORMER_SVC;
DROP USER IF EXISTS ARTWORK_LOADER_SVC;
