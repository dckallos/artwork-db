-- =============================================================================
-- openaccess_catalog.sql -- Gold: Public-domain artwork catalog (OBT)
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per public-domain artwork WITH a primary image
-- PK: artwork_id (from dim_artworks)
--
-- Pre-joins dim_artworks + dim_artists + primary image from fct_artwork_images
-- into a single wide table. Filtered to public-domain + has-image.
-- This is the consumption layer for Cortex Analyst, dashboards, and apps.
-- =============================================================================

WITH artworks AS (

    SELECT *
    FROM {{ ref('dim_artworks') }}
    WHERE is_public_domain = TRUE

),

artists AS (

    SELECT
        artist_id,
        artist_display_name,
        artist_nationality
    FROM {{ ref('dim_artists') }}

),

primary_images AS (

    SELECT
        artwork_id,
        image_url AS primary_image_url,
        image_url_small AS primary_image_small_url
    FROM {{ ref('fct_artwork_images') }}
    WHERE image_type = 'primary'
      AND ordinal_position = 1

),

image_counts AS (

    SELECT
        artwork_id,
        COUNT(*) - 1 AS additional_image_count  -- subtract the primary image
    FROM {{ ref('fct_artwork_images') }}
    GROUP BY artwork_id

)

SELECT
    artworks.artwork_id,
    artworks.source_object_id,
    artworks.title,
    artists.artist_display_name,
    artists.artist_nationality,
    artworks.object_date,
    artworks.object_begin_date,
    artworks.object_end_date,
    artworks.medium,
    artworks.classification,
    artworks.department,
    artworks.culture,
    artworks.country,
    primary_images.primary_image_url,
    primary_images.primary_image_small_url,
    COALESCE(image_counts.additional_image_count, 0) AS additional_image_count,
    artworks.link_resource,
    artworks.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM artworks
INNER JOIN primary_images
    ON artworks.artwork_id = primary_images.artwork_id
LEFT JOIN artists
    ON artworks.artist_id = artists.artist_id
LEFT JOIN image_counts
    ON artworks.artwork_id = image_counts.artwork_id
