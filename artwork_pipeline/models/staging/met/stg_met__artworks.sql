-- =============================================================================
-- stg_met__artworks.sql -- Staging model: typed artwork attributes from Met
-- =============================================================================
-- Flattens the RAW_PAYLOAD VARIANT into typed columns. Materialized as a view
-- (M1); will convert to incremental with hard-delete support in M3.
--
-- Source: ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
-- Target: ARTWORK_DB.SILVER.STG_MET__ARTWORKS (view)
--
-- Naming convention: stg_{source}__{entity}
-- =============================================================================

WITH source AS (

    SELECT
        object_id,
        raw_payload,
        _extracted_at,
        _source_system,
        _batch_id
    FROM {{ source('met', 'raw_met_objects') }}

),

flattened AS (

    SELECT
        -- Primary key (from top-level column, not VARIANT)
        object_id,

        -- Core artwork attributes (from csv sub-object)
        raw_payload:csv:title::STRING                    AS title,
        raw_payload:csv:object_date::STRING              AS object_date,
        raw_payload:csv:object_begin_date::INT           AS object_begin_date,
        raw_payload:csv:object_end_date::INT             AS object_end_date,
        raw_payload:csv:medium::STRING                   AS medium,
        raw_payload:csv:dimensions::STRING               AS dimensions,
        raw_payload:csv:classification::STRING           AS classification,
        raw_payload:csv:department::STRING               AS department,
        raw_payload:csv:object_name::STRING              AS object_name,
        raw_payload:csv:culture::STRING                  AS culture,
        raw_payload:csv:period::STRING                   AS period,
        raw_payload:csv:dynasty::STRING                  AS dynasty,
        raw_payload:csv:credit_line::STRING              AS credit_line,
        raw_payload:csv:accession_year::STRING           AS accession_year,
        raw_payload:csv:object_number::STRING            AS accession_number,

        -- Artist attributes (single-artist for M1; multi-artist in M2)
        raw_payload:csv:artist_display_name::STRING      AS artist_display_name,
        raw_payload:csv:artist_display_bio::STRING       AS artist_display_bio,
        raw_payload:csv:artist_nationality::STRING       AS artist_nationality,
        raw_payload:csv:artist_begin_date::STRING        AS artist_begin_date,
        raw_payload:csv:artist_end_date::STRING          AS artist_end_date,
        raw_payload:csv:artist_gender::STRING            AS artist_gender,
        raw_payload:csv:artist_role::STRING              AS artist_role,
        raw_payload:csv:artist_alpha_sort::STRING        AS artist_alpha_sort,
        raw_payload:csv:artist_ulan_url::STRING          AS artist_ulan_url,
        raw_payload:csv:artist_wikidata_url::STRING      AS artist_wikidata_url,

        -- Geography
        raw_payload:csv:city::STRING                     AS city,
        raw_payload:csv:state::STRING                    AS geo_state,
        raw_payload:csv:county::STRING                   AS county,
        raw_payload:csv:country::STRING                  AS country,
        raw_payload:csv:region::STRING                   AS region,
        raw_payload:csv:subregion::STRING                AS subregion,
        raw_payload:csv:locale::STRING                   AS locale,
        raw_payload:csv:locus::STRING                    AS locus,
        raw_payload:csv:excavation::STRING               AS excavation,
        raw_payload:csv:river::STRING                    AS river,
        raw_payload:csv:geography_type::STRING           AS geography_type,

        -- Access and rights
        raw_payload:csv:is_public_domain::BOOLEAN        AS is_public_domain,
        raw_payload:csv:is_highlight::BOOLEAN            AS is_highlight,
        raw_payload:csv:rights_and_reproduction::STRING  AS rights_and_reproduction,
        raw_payload:csv:link_resource::STRING            AS link_resource,

        -- Images (primary only; additional_images array flattened in M2)
        raw_payload:api_images:primary_image::STRING       AS primary_image_url,
        raw_payload:api_images:primary_image_small::STRING AS primary_image_small_url,

        -- Tags (kept as-is for now; could normalize in M2)
        raw_payload:csv:tags::STRING                     AS tags,
        raw_payload:csv:tags_aat_url::STRING             AS tags_aat_url,
        raw_payload:csv:tags_wikidata_url::STRING        AS tags_wikidata_url,

        -- Wikidata
        raw_payload:csv:object_wikidata_url::STRING      AS object_wikidata_url,

        -- Metadata
        raw_payload:csv:metadata_date::STRING            AS metadata_date,
        raw_payload:csv:repository::STRING               AS repository,
        raw_payload:csv:portfolio::STRING                AS portfolio,
        raw_payload:csv:reign::STRING                    AS reign,

        -- Extraction metadata (pass-through for lineage)
        _extracted_at,
        _source_system,
        _batch_id

    FROM source

)

SELECT * FROM flattened
