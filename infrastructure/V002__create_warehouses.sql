-- =============================================================================
-- V002: Create compute warehouses
-- X-Small is sufficient for development. Scale up for full Met extraction.
-- Paired rollback: infrastructure/V002__drop_warehouses.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;

CREATE WAREHOUSE IF NOT EXISTS ARTWORK_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Primary warehouse for the artwork medallion pipeline.';
