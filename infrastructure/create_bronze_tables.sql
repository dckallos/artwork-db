-- =============================================================================
-- create_bronze_tables.sql: Create Bronze layer tables
-- One table per source API + an extraction log for observability, plus the Met
-- image-enrichment orchestration pair (MET_ENRICHMENT_CONTROL + MET_CSV_SNAPSHOT).
-- All raw tables store raw JSON as VARIANT with extraction metadata.
-- Paired rollback: infrastructure/drop_bronze_tables.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- Metropolitan Museum of Art
CREATE TABLE IF NOT EXISTS RAW_MET_OBJECTS (
    object_id       INT             COMMENT 'Met API objectID',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response from /objects/{id}',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'UTC timestamp of extraction',
    _source_system  VARCHAR         NOT NULL DEFAULT 'met_museum' COMMENT 'Source system identifier',
    _batch_id       VARCHAR         NOT NULL COMMENT 'UUID identifying the extraction batch'
)
COMMENT = 'Raw Met Museum API responses. One row per object.';

-- Art Institute of Chicago
CREATE TABLE IF NOT EXISTS RAW_AIC_ARTWORKS (
    artwork_id      INT             COMMENT 'AIC API artwork id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'art_institute_chicago',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Art Institute of Chicago API responses. One row per artwork.';

-- Cleveland Museum of Art: Artworks
CREATE TABLE IF NOT EXISTS RAW_CMA_ARTWORKS (
    artwork_id      INT             COMMENT 'CMA API artwork id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art artwork responses.';

-- Cleveland Museum of Art: Creators
CREATE TABLE IF NOT EXISTS RAW_CMA_CREATORS (
    creator_id      INT             COMMENT 'CMA API creator id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art creator responses.';

-- Cleveland Museum of Art: Exhibitions
CREATE TABLE IF NOT EXISTS RAW_CMA_EXHIBITIONS (
    exhibition_id   INT             COMMENT 'CMA API exhibition id',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'cleveland_museum_art',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Cleveland Museum of Art exhibition responses.';

-- Smithsonian Institution
CREATE TABLE IF NOT EXISTS RAW_SMITHSONIAN_OBJECTS (
    object_id       VARCHAR         COMMENT 'Smithsonian record ID (varies by unit)',
    raw_payload     VARIANT         NOT NULL COMMENT 'Complete raw JSON response',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    _source_system  VARCHAR         NOT NULL DEFAULT 'smithsonian',
    _batch_id       VARCHAR         NOT NULL
)
COMMENT = 'Raw Smithsonian Institution OpenAccess responses.';

-- Extraction log: one row per extraction run for observability
CREATE TABLE IF NOT EXISTS EXTRACTION_LOG (
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

-- -----------------------------------------------------------------------------
-- Met enrichment orchestration (Session 3 build; see docs/context/met-deepdive.md
-- DDL-04 / PIPE-05 / Session-1 strawman). The thin, Snowflake-AUTHORITATIVE
-- control table is the system of record for enrichment STATE only -- never the
-- wide descriptive row (that lives in RAW_MET_OBJECTS / MET_CSV_SNAPSHOT). Narrow
-- by design: a scheduling Task decides work and audits progress from these cols.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS MET_ENRICHMENT_CONTROL (
    object_id           NUMBER          NOT NULL COMMENT 'Met objectID; join key to RAW_MET_OBJECTS / MET_CSV_SNAPSHOT',
    enrichment_status   VARCHAR         NOT NULL DEFAULT 'pending' COMMENT 'Outcome enum: pending | done | no_image | error',
    last_enriched_at    TIMESTAMP_NTZ   COMMENT 'When API discovery last ran for this object',
    metadata_date       DATE            COMMENT 'Met Metadata Date / API metadataDate (incremental change signal)',
    has_primary_image   BOOLEAN         COMMENT 'Monetization gate result (LEG-02 / IMG-02)',
    image_status        VARCHAR         DEFAULT 'unknown' COMMENT 'Liveness enum: unknown | live | dead (IMG-04)',
    last_head_check_at  TIMESTAMP_NTZ   COMMENT 'CDN HEAD liveness-sweep timestamp (IMG-04)',
    claimed_by_batch    VARCHAR         COMMENT 'Lease owner: batch_id currently fetching this row (NULL = free)',
    claimed_at          TIMESTAMP_NTZ   COMMENT 'Lease timestamp; TTL reclaim of abandoned claims (see create_tasks.sql)',
    CONSTRAINT pk_met_enrichment_control PRIMARY KEY (object_id)
)
COMMENT = 'Thin Snowflake-authoritative enrichment control/lease table for the Met worklist. State only, not data.';

-- -----------------------------------------------------------------------------
-- Full Met CSV snapshot landed at bootstrap (Session 3 build; see DDL-05,
-- Option A, VARIANT raw-blob -- owner-decided 2026-05-31). One JSON row per
-- objectID mirroring the RAW_MET_OBJECTS shape, INDEPENDENT of enrichment so the
-- worklist can prioritize PENDING (not-yet-enriched) rows and DATA-01 deaccession
-- can be detected via snapshot-diff. Discipline: land the whole raw row in Bronze
-- (sparse cols ~free as VARIANT); promote typed columns selectively in Silver.
--
-- Uniqueness (owner-directed 2026-05-31): object_id is the PRIMARY KEY -- exactly
-- ONE current row per Met object. The bootstrap MUST load via MERGE keyed on
-- object_id (insert new / update changed), NOT append. Snowflake does not ENFORCE
-- PK/UNIQUE, so the MERGE load pattern is what carries the guarantee at runtime
-- (Section C); the constraint declares intent + lets the optimizer assume
-- distinctness. This keeps the MET_WORKLIST control x snapshot join strictly 1:1
-- (no row fan-out) and makes DATA-01 deaccession detection a clean anti-join
-- (object_ids in a prior snapshot but absent from the current CSV).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS MET_CSV_SNAPSHOT (
    object_id       NUMBER          NOT NULL COMMENT 'Met objectID (from CSV Object ID column); PK -> one snapshot row per object',
    raw_payload     VARIANT         NOT NULL COMMENT 'Full Met CSV row as JSON (snake_case keys per _CSV_PAYLOAD_COLUMNS)',
    _extracted_at   TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'UTC timestamp the snapshot row was landed',
    _source_system  VARCHAR         NOT NULL DEFAULT 'met_museum' COMMENT 'Source system identifier',
    _batch_id       VARCHAR         NOT NULL COMMENT 'UUID identifying the bootstrap snapshot batch',
    CONSTRAINT pk_met_csv_snapshot PRIMARY KEY (object_id)
)
COMMENT = 'Raw Met OpenAccess CSV snapshot (full list, VARIANT). One row per objectID (PK). Feeds MET_WORKLIST priority + DATA-01 deaccession diff.';
