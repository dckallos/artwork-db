-- =============================================================================
-- create_roles.sql: Create roles for the artwork medallion pipeline
-- Roles follow least-privilege: loader writes Bronze, transformer writes Silver/Gold
-- Paired rollback: infrastructure/drop_roles.sql
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Role for Python extraction scripts (writes to Bronze only)
CREATE ROLE IF NOT EXISTS ARTWORK_LOADER
    COMMENT = 'Role for Python extraction scripts. Writes raw data to BRONZE schema.';

-- Role for dbt transformations (reads Bronze, writes Silver and Gold)
CREATE ROLE IF NOT EXISTS ARTWORK_TRANSFORMER
    COMMENT = 'Role for dbt transformations. Reads BRONZE, writes SILVER and GOLD schemas.';

-- Admin role that owns all pipeline objects
CREATE ROLE IF NOT EXISTS ARTWORK_ADMIN
    COMMENT = 'Admin role for the artwork pipeline. Owns databases, warehouses, and grants.';

-- Role hierarchy: ARTWORK_ADMIN inherits both functional roles
GRANT ROLE ARTWORK_LOADER TO ROLE ARTWORK_ADMIN;
GRANT ROLE ARTWORK_TRANSFORMER TO ROLE ARTWORK_ADMIN;

-- Grant ARTWORK_ADMIN to SYSADMIN so it participates in the standard hierarchy
GRANT ROLE ARTWORK_ADMIN TO ROLE SYSADMIN;

-- ---------------------------------------------------------------
-- Account-level (global) privileges for ARTWORK_ADMIN.
-- A freshly created custom role holds NO global privileges.
-- ARTWORK_ADMIN owns ARTWORK_DB/ARTWORK_WH, so ownership covers
-- every schema- and object-level DDL downstream (create_file_formats.sql-create_bronze_tables.sql). The
-- ONLY privileges that ever need an explicit account grant are
-- these global ones. Grant the full set here so later scripts
-- never fail with 003001 (42501). Only ACCOUNTADMIN (or a role
-- with MANAGE GRANTS) can grant global privileges -- a role cannot
-- grant them to itself, which is why they live in this bootstrap
-- block per the 2026-05-29 design decision (role model).
-- ---------------------------------------------------------------
GRANT CREATE WAREHOUSE ON ACCOUNT TO ROLE ARTWORK_ADMIN;  -- create_warehouses.sql
GRANT CREATE DATABASE  ON ACCOUNT TO ROLE ARTWORK_ADMIN;  -- create_databases_and_schemas.sql
-- Tasks require EXECUTE TASK on the account to run, even when owned by the
-- executing role. Enabled IN LOCKSTEP with create_tasks.sql, which defines
-- MET_LEASE_RECLAIM_TASK (Session-3 build, 2026-05-31).
GRANT EXECUTE TASK ON ACCOUNT TO ROLE ARTWORK_ADMIN;   -- create_tasks.sql
