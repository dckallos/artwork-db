-- =============================================================================
-- V005: Create internal stages for bulk data loading
-- Paired rollback: infrastructure/V005__drop_stages.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- Shared internal stage for Python extraction uploads
CREATE OR REPLACE STAGE bronze_load_stage
    FILE_FORMAT = json_raw
    COMMENT = 'Internal stage for Python extraction scripts to upload raw data files.';
