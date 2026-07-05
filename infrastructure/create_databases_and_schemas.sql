-- =============================================================================
-- create_databases_and_schemas.sql: Create ARTWORK_DB and every dbt-routed schema.
-- Paired rollback: infrastructure/drop_databases_and_schemas.sql
-- =============================================================================
-- dbt schema routing is environment-aware:
--   dev      target.schema=dbt_daniel -> DBT_DANIEL_SILVER / DBT_DANIEL_GOLD
--   staging  target.schema=STAGING    -> STAGING_SILVER / STAGING_GOLD
--   prod     verbatim custom schemas  -> SILVER / GOLD
-- dbt does not create schemas in this project; infrastructure owns them.
-- =============================================================================

USE ROLE ARTWORK_ADMIN;

CREATE DATABASE IF NOT EXISTS ARTWORK_DB
    COMMENT = 'Artwork medallion pipeline: museum APIs -> Bronze -> Silver -> Gold';

USE DATABASE ARTWORK_DB;

CREATE SCHEMA IF NOT EXISTS BRONZE
    COMMENT = 'Raw API responses stored as VARIANT. Append-only. No transformations.';

CREATE SCHEMA IF NOT EXISTS SILVER
    COMMENT = 'Production Silver schema owned by dbt staging and intermediate models.';

CREATE SCHEMA IF NOT EXISTS GOLD
    COMMENT = 'Production Gold schema owned by dbt marts.';

CREATE SCHEMA IF NOT EXISTS STAGING_SILVER
    COMMENT = 'CI staging Silver schema, generated from target schema STAGING and +schema SILVER.';

CREATE SCHEMA IF NOT EXISTS STAGING_GOLD
    COMMENT = 'CI staging Gold schema, generated from target schema STAGING and +schema GOLD.';

CREATE SCHEMA IF NOT EXISTS DBT_DANIEL_SILVER
    COMMENT = 'Daniel local dev Silver schema, generated from target schema dbt_daniel and +schema SILVER.';

CREATE SCHEMA IF NOT EXISTS DBT_DANIEL_GOLD
    COMMENT = 'Daniel local dev Gold schema, generated from target schema dbt_daniel and +schema GOLD.';

CREATE SCHEMA IF NOT EXISTS DBT_TEST__AUDIT
    COMMENT = 'dbt test failure storage (store_failures: true). Tables auto-managed by dbt test runs.';
