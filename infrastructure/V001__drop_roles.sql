-- =============================================================================
-- V001 ROLLBACK: drop the three custom roles created by V001.
--
-- Paired forward: infrastructure/V001__create_roles.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Ordering:
--   `make down` applies V### drops in REVERSE order (V009 -> V008 -> ... ->
--   V001). By the time this script runs, the warehouse (V002), database
--   (V003), file formats (V004), stages (V005), tables (V007), service user
--   (V008), and tasks (V009) that referenced these roles are already gone.
--   Snowflake's DROP ROLE then has nothing left to fail on.
--
--   Within this script the leaf roles (ARTWORK_LOADER, ARTWORK_TRANSFORMER)
--   are dropped before the parent (ARTWORK_ADMIN) so the inheritance graph
--   unwinds cleanly in OBJECT_HISTORY. With IF EXISTS this is purely
--   cosmetic: Snowflake automatically revokes every grant TO and FROM a role
--   at DROP ROLE time, and the SYSADMIN -> ARTWORK_ADMIN grant from V001
--   forward is removed automatically with the parent.
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
