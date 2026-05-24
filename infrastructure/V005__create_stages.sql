-- =============================================================================
-- V005: Create internal stages for bulk data loading
-- One shared stage for all sources. Subdirectories separate source files.
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- Shared internal stage for Python extraction uploads
CREATE OR REPLACE STAGE bronze_load_stage
    FILE_FORMAT = json_raw
COMMENT = 'Internal stage for Python extraction scripts to upload raw data files.';
