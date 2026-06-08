-- =============================================================================
-- stg_aic__artworks.sql -- Staging model: typed artwork attributes from AIC
-- =============================================================================
-- Flattens the RAW_PAYLOAD VARIANT into typed columns. Materialized as a view.
--
-- Soft-delete filter: WHERE _is_deleted = FALSE (AIC Bronze tracks deletions
-- natively via _is_deleted, _deleted_at, _deletion_reason columns).
-- Met does NOT have this -- see design doc D4 re: accepted asymmetry.
--
-- Grain: one row per artwork (artwork_id is the natural key from the AIC API).
--
-- Source: ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
-- Target: ARTWORK_DB.SILVER.STG_AIC__ARTWORKS (view)
-- =============================================================================

WITH source AS (

    SELECT
        artwork_id,
        raw_payload,
        _extracted_at,
        _source_system,
        _batch_id
    FROM {{ source('aic', 'raw_aic_artworks') }}
    WHERE _is_deleted = FALSE

),

typed AS (

    SELECT
        -- Primary key
        artwork_id,

        -- Core artwork attributes
        raw_payload:title::STRING                          AS title,
        raw_payload:date_display::STRING                   AS date_display,
        raw_payload:date_start::INT                        AS date_start,
        raw_payload:date_end::INT                          AS date_end,
        raw_payload:medium_display::STRING                 AS medium_display,
        raw_payload:dimensions::STRING                     AS dimensions,
        raw_payload:artwork_type_title::STRING             AS artwork_type_title,
        raw_payload:department_title::STRING               AS department_title,
        raw_payload:place_of_origin::STRING                AS place_of_origin,
        raw_payload:credit_line::STRING                    AS credit_line,
        raw_payload:main_reference_number::STRING          AS main_reference_number,
        raw_payload:fiscal_year::INT                       AS fiscal_year,

        -- Access and rights
        raw_payload:is_public_domain::BOOLEAN              AS is_public_domain,
        raw_payload:is_boosted::BOOLEAN                    AS is_boosted,
        raw_payload:api_link::STRING                       AS api_link,

        -- Artist FK (direct integer reference to RAW_AIC_AGENTS.agent_id)
        raw_payload:artist_id::INT                         AS artist_id,
        raw_payload:artist_title::STRING                   AS artist_title,

        -- Thumbnail metadata (D7: 1:1 with artwork grain, not on images model)
        raw_payload:thumbnail:width::INT                   AS thumbnail_width,
        raw_payload:thumbnail:height::INT                  AS thumbnail_height,
        raw_payload:thumbnail:alt_text::STRING             AS thumbnail_alt_text,

        -- Extraction metadata (pass-through for lineage)
        _extracted_at,
        _source_system,
        _batch_id

    FROM source

)

SELECT * FROM typed
