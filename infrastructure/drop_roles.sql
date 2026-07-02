-- =============================================================================
-- create_roles.sql ROLLBACK: drop the three custom roles created by create_roles.sql.
--
-- Paired forward: infrastructure/create_roles.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   `make down` applies paired drops in REVERSE manifest order (create_tasks.sql -> create_service_user.sql -> ... ->
--   create_roles.sql). By the time this script runs, the warehouse (create_warehouses.sql), database
--   (create_databases_and_schemas.sql), file formats (create_file_formats.sql), stages (create_stages.sql), tables (create_bronze_tables.sql), service user
--   (create_service_user.sql), and tasks (create_tasks.sql) that referenced these roles are already gone.
--   Snowflake's DROP ROLE then has nothing left to fail on.
--
--   Within this script the leaf roles (ARTWORK_LOADER, ARTWORK_TRANSFORMER)
--   are dropped before the parent (ARTWORK_ADMIN) so the inheritance graph
--   unwinds cleanly in OBJECT_HISTORY. With IF EXISTS this is purely
--   cosmetic: Snowflake automatically revokes every grant TO and FROM a role
--   at DROP ROLE time, and the SYSADMIN -> ARTWORK_ADMIN grant from create_roles.sql
--   forward is removed automatically with the parent. The account-level
--   (global) grants added to ARTWORK_ADMIN by create_roles.sql forward -- CREATE
--   WAREHOUSE and CREATE DATABASE ON ACCOUNT (and EXECUTE TASK once create_tasks.sql
--   needs it) -- are likewise revoked automatically by DROP ROLE, so this
--   rollback needs no explicit REVOKE ... ON ACCOUNT statements; it stays a
--   roles-only teardown.
--
-- Account-level effects:
--   DROP ROLE revokes every grant on every object that was issued TO the
--   role. Any user who held the role as their DEFAULT_ROLE has it cleared.
--   Active sessions running under the role continue until they end on their
--   own; no in-flight query is killed by DROP ROLE alone.
--
-- Idempotency:
--   DROP ROLE IF EXISTS is safe pre-create and safe to re-run.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

DROP ROLE IF EXISTS ARTWORK_LOADER;
DROP ROLE IF EXISTS ARTWORK_TRANSFORMER;
DROP ROLE IF EXISTS ARTWORK_ADMIN;
