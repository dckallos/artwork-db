-- =============================================================================
-- create_databases_and_schemas.sql: Create database and medallion schemas (Bronze, Silver, Gold)
-- Paired rollback: infrastructure/drop_databases_and_schemas.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_DB
    COMMENT = 'Artwork medallion pipeline: 4 museum APIs -> Bronze -> Silver -> Gold';

USE DATABASE ARTWORK_DB;

CREATE SCHEMA IF NOT EXISTS BRONZE
    COMMENT = 'Raw API responses stored as VARIANT. Append-only. No transformations.';

CREATE SCHEMA IF NOT EXISTS SILVER
    COMMENT = 'Cleaned, typed, and conformed data. Owned by dbt staging and intermediate models.';

CREATE SCHEMA IF NOT EXISTS GOLD
    COMMENT = 'Business-ready fact and reporting tables. Owned by dbt mart models.';
