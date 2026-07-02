-- =============================================================================
-- create_file_formats.sql: Create file formats for staged data loading
-- Paired rollback: infrastructure/drop_file_formats.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- JSON file format for raw API payloads
CREATE OR REPLACE FILE FORMAT JSON_RAW
    TYPE = 'JSON'
    STRIP_OUTER_ARRAY = FALSE
    COMPRESSION = 'AUTO'
    COMMENT = 'JSON format for raw API response loading into VARIANT columns.';

-- Parquet file format (used by write_pandas under the hood, but explicit for COPY INTO)
CREATE OR REPLACE FILE FORMAT PARQUET_RAW
    TYPE = 'PARQUET'
    COMPRESSION = 'SNAPPY'
    COMMENT = 'Parquet format for bulk data loading (AIC dumps, Smithsonian S3).';
