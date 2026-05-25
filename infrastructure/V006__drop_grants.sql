-- =============================================================================
-- V006 ROLLBACK: no-op script for the grants applied by V006.
--
-- Paired forward: infrastructure/V006__grant_privileges.sql.
-- Applied by:     scripts/rollback_sql.sh -> snow sql --filename
--                 --connection admin --enhanced-exit-codes.
--
-- Why this file contains no REVOKE statements:
--   Every grant issued by V006 references a parent object (WAREHOUSE,
--   DATABASE, SCHEMA, TABLE, STAGE, VIEW, or ROLE) that is destroyed by one
--   of the other V### drop scripts (V001 - V005, V007, V008). Snowflake
--   automatically revokes every grant ON or TO a dropped object, so explicit
--   REVOKE statements here would be redundant.
--
--   REVOKE in Snowflake does NOT support an IF EXISTS guard. If we issued
--   explicit REVOKEs here, a single missing object would abort the script
--   and leave V006 rollback in a partial state. The cascade-from-parent
--   approach avoids that fragility entirely.
--
-- When to add real REVOKEs here:
--   If future grants are issued AGAINST persistent account-level objects
--   that V001 - V008 do NOT drop (for example, a future SHARE or SECRET
--   created elsewhere, or grants on the ARTWORK_OPS database from B002),
--   add the matching
--     REVOKE <privilege> ON <object> FROM ROLE <role>;
--   statements below. Wrap each in a guarded EXECUTE IMMEDIATE block if the
--   target object might be absent (see Snowflake Scripting docs for the
--   pattern), or accept that V006 rollback will then require V001 - V008 to
--   have been applied first.
--
-- Idempotency:
--   A bare SELECT is trivially safe to re-run. It also gives
--   `snow sql --enhanced-exit-codes` a successful exit code (0) so the
--   `make down` chain continues to the next paired drop.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

SELECT 'V006 rollback: no grants to revoke (parent objects cascade their grants)' AS status;
