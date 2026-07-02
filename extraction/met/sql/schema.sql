-- SQLite schema for the Met OpenAccess extraction pipeline.
-- Two tables only:
--   met_artworks    : one row per Met object_id, CSV fields + API image URLs
--                     + pipeline state.
--   extraction_runs : one row per pipeline phase invocation, for observability.

PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA temp_store   = MEMORY;

CREATE TABLE IF NOT EXISTS met_artworks (
    -- Identity
    object_id                INTEGER PRIMARY KEY,
    object_number            TEXT,

    -- CSV-sourced descriptive fields (snake_case copies of CSV headers)
    is_highlight             INTEGER,
    is_public_domain         INTEGER,
    department               TEXT,
    accession_year           TEXT,
    object_name              TEXT,
    title                    TEXT,
    culture                  TEXT,
    period                   TEXT,
    dynasty                  TEXT,
    reign                    TEXT,
    portfolio                TEXT,
    artist_role              TEXT,
    artist_display_name      TEXT,
    artist_display_bio       TEXT,
    artist_alpha_sort        TEXT,
    artist_nationality       TEXT,
    artist_begin_date        TEXT,
    artist_end_date          TEXT,
    artist_gender            TEXT,
    artist_ulan_url          TEXT,
    artist_wikidata_url      TEXT,
    object_date              TEXT,
    object_begin_date        INTEGER,
    object_end_date          INTEGER,
    medium                   TEXT,
    dimensions               TEXT,
    credit_line              TEXT,
    geography_type           TEXT,
    city                     TEXT,
    state                    TEXT,
    county                   TEXT,
    country                  TEXT,
    region                   TEXT,
    subregion                TEXT,
    locale                   TEXT,
    locus                    TEXT,
    excavation               TEXT,
    river                    TEXT,
    classification           TEXT,
    rights_and_reproduction  TEXT,
    link_resource            TEXT,
    object_wikidata_url      TEXT,
    metadata_date            TEXT,
    repository               TEXT,
    tags                     TEXT,
    tags_aat_url             TEXT,
    tags_wikidata_url        TEXT,

    -- API-enriched image URLs (filled in by image_enricher)
    primary_image_url        TEXT,
    primary_image_small_url  TEXT,
    additional_image_urls    TEXT,    -- JSON array stored as TEXT

    -- Pipeline state
    enrichment_status        TEXT NOT NULL DEFAULT 'pending',
                                    -- pending | done | no_image | error
    enrichment_error         TEXT,
    enriched_at              TEXT,
    bronze_batch_id          TEXT,
    bronze_uploaded_at       TEXT,

    -- Audit
    csv_loaded_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_met_artworks_status
    ON met_artworks (enrichment_status);

CREATE INDEX IF NOT EXISTS idx_met_artworks_upload_ready
    ON met_artworks (enrichment_status, bronze_uploaded_at);

CREATE TABLE IF NOT EXISTS extraction_runs (
    run_id              TEXT PRIMARY KEY,
    phase               TEXT NOT NULL,    -- bootstrap | enrich | upload
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    status              TEXT NOT NULL,    -- running | success | failed
    records_processed   INTEGER,
    notes               TEXT
);
