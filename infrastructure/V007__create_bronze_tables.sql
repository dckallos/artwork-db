-- =============================================================================
-- V007: Create Bronze layer tables
-- One table per source API + an extraction log for observability.
-- All tables store raw JSON as VARIANT with extraction metadata.
-- Paired rollback: infrastructure/V007__drop_bronze_tables.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- Metropolitan Museum of Art
CREATE TABLE IF NOT EXISTS raw_met_objects (
    object_id       INT             COMMENT 'Met API objectID',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response from /objects/{id}',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'UTC timestamp of extraction',
    _source_system  VARCHAR         NOT NULL DEFAULT 'met_museum' COMMENT 'Source system identifier',
    _batch_id       VARCHAR         NOT NULL COMMENT 'UUID identifying the extraction batch'
)
COMMENT = 'Raw Met Museum API responses. One row per object.';

-- Art Institute of Chicago
CREATE TABLE IF NOT EXISTS raw_aic_artworks (
    artwork_id      INT             COMMENT 'AIC API artwork id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'art_institute_chicago',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Art Institute of Chicago API responses. One row per artwork.';

-- Cleveland Museum of Art: Artworks
CREATE TABLE IF NOT EXISTS raw_cma_artworks (
    artwork_id      INT             COMMENT 'CMA API artwork id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art artwork responses.';

-- Cleveland Museum of Art: Creators
CREATE TABLE IF NOT EXISTS raw_cma_creators (
    creator_id      INT             COMMENT 'CMA API creator id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art creator responses.';

-- Cleveland Museum of Art: Exhibitions
CREATE TABLE IF NOT EXISTS raw_cma_exhibitions (
    exhibition_id   INT             COMMENT 'CMA API exhibition id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art exhibition responses.';

-- Smithsonian Institution
CREATE TABLE IF NOT EXISTS raw_smithsonian_objects (
    object_id       VARCHAR         COMMENT 'Smithsonian record ID (varies by unit)',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'smithsonian',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Smithsonian Institution OpenAccess responses.';

-- Extraction log: one row per extraction run for observability
CREATE TABLE IF NOT EXISTS extraction_log (
    log_id          INT             AUTOINCREMENT COMMENT 'Auto-incrementing log ID',
    source_system   VARCHAR         NOT NULL COMMENT 'Which museum API was extracted',
    batch_id        VARCHAR         NOT NULL COMMENT 'UUID matching _batch_id in source tables',
    records_loaded  INT             COMMENT 'Number of records loaded in this batch',
    started_at      TIMESTAMP_NTZ   NOT NULL COMMENT 'Extraction start time (UTC)',
    completed_at    TIMESTAMP_NTZ   COMMENT 'Extraction end time (UTC)',
    status          VARCHAR         NOT NULL DEFAULT 'running' COMMENT 'running, success, failed',
    error_message   VARCHAR         COMMENT 'Error details if status = failed',
    CONSTRAINT pk_extraction_log PRIMARY KEY (log_id)
)
COMMENT = 'Tracks every extraction run for observability and debugging.';
