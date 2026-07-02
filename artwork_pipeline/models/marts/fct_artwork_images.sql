-- =============================================================================
-- fct_artwork_images.sql -- Gold: Image fact table (incremental)
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per image per artwork
-- PK: image_id (MD5 hash of artwork_id + image_type + ordinal_position)
-- FK: artwork_id -> dim_artworks
--
-- Sources: stg_met__images, stg_aic__images (via dim_artworks for artwork_id FK)
-- UNION column order: MUST match between met_images and aic_images CTEs (P3-3).
--
-- Materialization: incremental (merge strategy on image_id).
-- First run: CREATE TABLE AS SELECT (full dataset).
-- Subsequent runs: MERGE -- only rows where _extracted_at > MAX(_loaded_at).
-- Cluster key: [source_system] (learning exercise, P3-4; no-op at <1M rows).
-- =============================================================================

{{
    config(
        materialized='incremental',
        unique_key='image_id',
        incremental_strategy='merge',
        on_schema_change='fail',
        cluster_by=['source_system']
    )
}}

WITH met_images AS (

    -- Column order: MUST match [aic_images] CTE below
    SELECT
        object_id               AS source_object_id,
        NULL::STRING            AS source_image_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'met_museum'            AS source_system,
        _extracted_at
    FROM {{ ref('stg_met__images') }}
    {% if is_incremental() %}
    WHERE _extracted_at > (SELECT MAX(_loaded_at) FROM {{ this }})
    {% endif %}

),

aic_images AS (

    -- Column order: MUST match [met_images] CTE above
    SELECT
        artwork_id              AS source_object_id,
        source_image_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'art_institute_chicago' AS source_system,
        _extracted_at
    FROM {{ ref('stg_aic__images') }}
    {% if is_incremental() %}
    WHERE _extracted_at > (SELECT MAX(_loaded_at) FROM {{ this }})
    {% endif %}

),

all_images AS (

    SELECT * FROM met_images
    UNION ALL
    SELECT * FROM aic_images

),

artworks AS (

    SELECT
        artwork_id,
        source_object_id,
        source_system
    FROM {{ ref('dim_artworks') }}

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.artwork_id', 'all_images.image_type', 'all_images.ordinal_position']) }}
        AS image_id,
    artworks.artwork_id,
    all_images.source_image_id,
    all_images.image_url,
    all_images.image_url_small,
    all_images.image_type,
    all_images.ordinal_position,
    all_images.source_system,
    CURRENT_TIMESTAMP()::TIMESTAMP_NTZ AS _loaded_at
FROM all_images
INNER JOIN artworks
    ON all_images.source_object_id = artworks.source_object_id
    AND all_images.source_system = artworks.source_system
