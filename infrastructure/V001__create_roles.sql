-- =============================================================================
-- V001: Create roles for the artwork medallion pipeline
-- Roles follow least-privilege: loader writes Bronze, transformer writes Silver/Gold
-- Paired rollback: infrastructure/V001__drop_roles.sql
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
