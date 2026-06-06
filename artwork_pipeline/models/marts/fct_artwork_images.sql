-- =============================================================================
-- fct_artwork_images.sql -- Gold: Image fact table
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per image per artwork
-- PK: image_id (MD5 hash of artwork_id + image_type + ordinal_position)
-- FK: artwork_id -> dim_artworks
--
-- Joins stg_met__images to dim_artworks to get the surrogate artwork_id FK.
-- =============================================================================

WITH images AS (

    SELECT
        object_id AS source_object_id,
        image_url,
        image_url_small,
        image_type,
        ordinal_position,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__images') }}

),

artworks AS (

    SELECT
        artwork_id,
        source_object_id,
        source_system
    FROM {{ ref('dim_artworks') }}

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.artwork_id', 'images.image_type', 'images.ordinal_position']) }}
        AS image_id,
    artworks.artwork_id,
    images.image_url,
    images.image_url_small,
    images.image_type,
    images.ordinal_position,
    images.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM images
INNER JOIN artworks
    ON images.source_object_id = artworks.source_object_id
    AND images.source_system = artworks.source_system
