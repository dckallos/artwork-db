-- =============================================================================
-- stg_met__images.sql -- Staging model: all image URLs from Met API (long format)
-- =============================================================================
-- One row per image per object. Flattens the primary image and the
-- additional_images array into a single long table.
--
-- Grain: (object_id, image_type, ordinal_position)
--
-- WHY long format:
--   The Met stores 0-18 additional images per object as a JSON array. A long
--   table preserves all of them without sparse columns, and is the natural
--   shape for Gold's fct_artwork_images (one fact row per image event).
--   LATERAL FLATTEN on the array does the work.
--
-- Source: ARTWORK_DB.BRONZE.RAW_MET_OBJECTS (api_images sub-key)
-- Target: ARTWORK_DB.SILVER.STG_MET__IMAGES (view)
-- =============================================================================

WITH source AS (

    SELECT
        object_id,
        raw_payload:api_images                           AS api_images,
        _extracted_at,
        _source_system
    FROM {{ source('met', 'raw_met_objects') }}

),

-- ---------------------------------------------------------------------------
-- Primary images: every object gets exactly one row (full-res) and one row
-- (small/web-sized), OR we could treat size as a column. We'll keep size as
-- a column so the grain stays (object_id, image_type, ordinal_position).
-- ---------------------------------------------------------------------------
primary_images AS (

    SELECT
        object_id,
        NULLIF(api_images:primary_image::STRING, '')         AS image_url,
        NULLIF(api_images:primary_image_small::STRING, '')   AS image_url_small,
        'primary'                                            AS image_type,
        1                                                    AS ordinal_position,
        _extracted_at,
        _source_system
    FROM source
    WHERE api_images:primary_image::STRING IS NOT NULL
      AND api_images:primary_image::STRING != ''

),

-- ---------------------------------------------------------------------------
-- Additional images: LATERAL FLATTEN on the array. Each element is a URL string.
-- Ordinal starts at 2 (primary = 1) so ordering is intuitive.
-- ---------------------------------------------------------------------------
additional_images AS (

    SELECT
        s.object_id,
        NULLIF(f.value::STRING, '')                          AS image_url,
        NULL                                                 AS image_url_small,
        'additional'                                         AS image_type,
        f.index + 2                                          AS ordinal_position,
        s._extracted_at,
        s._source_system
    FROM source s,
        LATERAL FLATTEN(input => s.api_images:additional_images) f
    WHERE f.value::STRING IS NOT NULL
      AND f.value::STRING != ''

),

-- ---------------------------------------------------------------------------
-- Union both sets into the final long table.
-- ---------------------------------------------------------------------------
unioned AS (

    SELECT * FROM primary_images
    UNION ALL
    SELECT * FROM additional_images

)

SELECT
    object_id,
    image_url,
    image_url_small,
    image_type,
    ordinal_position,
    _extracted_at,
    _source_system
FROM unioned
