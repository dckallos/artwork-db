-- =============================================================================
-- dim_artworks.sql -- Gold: Conformed artwork dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artwork
-- PK: artwork_id (MD5 hash of source_system + source_object_id)
-- FK: artist_id -> dim_artists
--
-- Selects curated attributes from stg_met__artworks. Joins to dim_artists to
-- get the FK (primary artist). Adds source_system for multi-source readiness.
-- =============================================================================

WITH artworks AS (

    SELECT
        object_id AS source_object_id,
        title,
        object_date,
        object_begin_date,
        object_end_date,
        medium,
        dimensions,
        classification,
        department,
        culture,
        period,
        dynasty,
        country,
        credit_line,
        accession_number,
        accession_year,
        is_public_domain,
        is_highlight,
        link_resource,
        object_wikidata_url,
        -- Extract PRIMARY artist (position 1) from pipe-delimited fields.
        -- stg_met__artworks stores the raw compound string; we split here to
        -- get the first artist's key fields for the dim_artists FK lookup.
        TRIM(GET(SPLIT(artist_alpha_sort, '|'), 0)::STRING)  AS primary_artist_alpha_sort,
        TRIM(GET(SPLIT(artist_ulan_url, '|'), 0)::STRING)    AS primary_artist_ulan_url,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__artworks') }}

),

artists AS (

    SELECT
        artist_id,
        artist_alpha_sort,
        artist_ulan_url,
        source_system
    FROM {{ ref('dim_artists') }}

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artworks.source_system', 'artworks.source_object_id']) }}
        AS artwork_id,
    artworks.source_object_id,
    artists.artist_id,
    artworks.title,
    artworks.object_date,
    artworks.object_begin_date,
    artworks.object_end_date,
    artworks.medium,
    artworks.dimensions,
    artworks.classification,
    artworks.department,
    artworks.culture,
    artworks.period,
    artworks.dynasty,
    artworks.country,
    artworks.credit_line,
    artworks.accession_number,
    artworks.accession_year,
    artworks.is_public_domain,
    artworks.is_highlight,
    artworks.link_resource,
    artworks.object_wikidata_url,
    artworks.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM artworks
LEFT JOIN artists
    ON artworks.primary_artist_alpha_sort = artists.artist_alpha_sort
    AND COALESCE(artworks.primary_artist_ulan_url, '') = COALESCE(artists.artist_ulan_url, '')
    AND artworks.source_system = artists.source_system
