-- =============================================================================
-- create_warehouses.sql: Create compute warehouses for local, staging, and prod.
-- Paired rollback: infrastructure/drop_warehouses.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;

CREATE WAREHOUSE IF NOT EXISTS ARTWORK_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Primary local/dev warehouse for the artwork medallion pipeline.';

CREATE WAREHOUSE IF NOT EXISTS ARTWORK_WH_STAGING
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Staging dbt CI warehouse for the artwork medallion pipeline.';

CREATE WAREHOUSE IF NOT EXISTS ARTWORK_WH_PROD
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Production dbt warehouse for the artwork medallion pipeline.';
