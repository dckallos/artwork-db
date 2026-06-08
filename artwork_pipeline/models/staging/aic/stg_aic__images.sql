-- =============================================================================
-- stg_aic__images.sql -- Staging model: all image references from AIC (long format)
-- =============================================================================
-- One row per image per artwork. Flattens the primary image_id and the
-- alt_image_ids array into a single long table matching stg_met__images shape.
--
-- Grain: (artwork_id, image_type, ordinal_position)
--
-- WHY long format:
--   Structural parity with stg_met__images. Gold's fct_artwork_images UNIONs
--   both sources into a single fact table -- same grain, same column semantics.
--   LATERAL FLATTEN on alt_image_ids array handles 0-N additional images.
--
-- URL construction:
--   AIC provides UUIDs (not full URLs). The IIIF URL is computed inline:
--     https://www.artic.edu/iiif/2/{uuid}/full/{width},/0/default.jpg
--   Standard = 843px (AIC website default). Small = 200px.
--   Raw UUID is preserved as source_image_id (D6) for downstream flexibility.
--
-- Data audit (2026-06-07):
--   - 119,903 artworks have image_id (89.4% of non-deleted)
--   - All image_id values are 36-char hyphenated UUIDs
--   - alt_image_ids: 93% empty, 7% have 1-3, <1% have 4+
--   - Total alt images: 17,480 across 9,343 artworks
--
-- Source: ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
-- Target: ARTWORK_DB.SILVER.STG_AIC__IMAGES (view)
-- =============================================================================

WITH source AS (

    SELECT
        artwork_id,
        raw_payload:image_id::STRING       AS primary_image_id,
        raw_payload:alt_image_ids           AS alt_image_ids,
        _extracted_at,
        _source_system
    FROM {{ source('aic', 'raw_aic_artworks') }}
    WHERE _is_deleted = FALSE
      AND raw_payload:image_id IS NOT NULL
      AND raw_payload:image_id::STRING != ''

),

-- ---------------------------------------------------------------------------
-- Primary images: one row per artwork that has an image_id.
-- ---------------------------------------------------------------------------
primary_images AS (

    SELECT
        artwork_id,
        primary_image_id                                           AS source_image_id,
        'https://www.artic.edu/iiif/2/' || primary_image_id || '/full/843,/0/default.jpg'
                                                                   AS image_url,
        'https://www.artic.edu/iiif/2/' || primary_image_id || '/full/200,/0/default.jpg'
                                                                   AS image_url_small,
        'primary'                                                  AS image_type,
        1                                                          AS ordinal_position,
        _extracted_at,
        _source_system
    FROM source

),

-- ---------------------------------------------------------------------------
-- Additional images: LATERAL FLATTEN on alt_image_ids array.
-- Ordinal starts at 2 (primary = 1) so ordering is intuitive.
-- FLATTEN produces zero rows for empty arrays -- no special handling needed.
-- ---------------------------------------------------------------------------
alt_images AS (

    SELECT
        s.artwork_id,
        f.value::STRING                                            AS source_image_id,
        'https://www.artic.edu/iiif/2/' || f.value::STRING || '/full/843,/0/default.jpg'
                                                                   AS image_url,
        'https://www.artic.edu/iiif/2/' || f.value::STRING || '/full/200,/0/default.jpg'
                                                                   AS image_url_small,
        'additional'                                               AS image_type,
        f.index + 2                                                AS ordinal_position,
        s._extracted_at,
        s._source_system
    FROM source s,
        LATERAL FLATTEN(input => s.alt_image_ids) f
    WHERE f.value::STRING IS NOT NULL
      AND f.value::STRING != ''

),

-- ---------------------------------------------------------------------------
-- Union both sets into the final long table.
-- ---------------------------------------------------------------------------
unioned AS (

    SELECT * FROM primary_images
    UNION ALL
    SELECT * FROM alt_images

)

SELECT
    artwork_id,
    source_image_id,
    image_url,
    image_url_small,
    image_type,
    ordinal_position,
    _extracted_at,
    _source_system
FROM unioned
