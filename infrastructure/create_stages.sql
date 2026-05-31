-- =============================================================================
-- create_stages.sql: Create internal stages for bulk data loading
-- Paired rollback: infrastructure/drop_stages.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- Shared internal stage for Python extraction uploads
CREATE OR REPLACE STAGE BRONZE_LOAD_STAGE
    FILE_FORMAT = JSON_RAW
    COMMENT = 'Internal stage for Python extraction scripts to upload raw data files.';
