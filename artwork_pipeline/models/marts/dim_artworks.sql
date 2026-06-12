-- =============================================================================
-- dim_artworks.sql -- Gold: Conformed artwork dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artwork
-- PK: artwork_id (MD5 hash of source_system + source_object_id)
-- FK: artist_id -> dim_artists
--
-- Sources: stg_met__artworks, stg_aic__artworks (+ stg_aic__artists for FK resolution)
-- UNION column order: MUST match between met_artworks and aic_artworks CTEs (P3-3).
--
-- AIC FK "round-trip" (P3-1): AIC stores a numeric artist_id FK. To match
-- dim_artists (keyed on alpha_sort + ulan_url + source_system), we pre-join
-- stg_aic__artists to resolve the integer FK to the string values needed for
-- the final artist lookup. QUALIFY guards against fan-out on duplicate sort_titles.
-- =============================================================================

WITH met_artworks AS (

    -- Column order: MUST match [aic_artworks] CTE below
    SELECT
        object_id                                                          AS source_object_id,
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
        TRIM(GET(SPLIT(artist_alpha_sort, '|'), 0)::STRING)  AS primary_artist_alpha_sort,
        TRIM(GET(SPLIT(artist_ulan_url, '|'), 0)::STRING)    AS primary_artist_ulan_url,
        'met_museum' AS source_system
    FROM {{ ref('stg_met__artworks') }}

),

aic_artworks AS (

    -- Column order: MUST match [met_artworks] CTE above
    SELECT
        a.artwork_id                                                       AS source_object_id,
        a.title,
        a.date_display                                                     AS object_date,
        a.date_start                                                       AS object_begin_date,
        a.date_end                                                         AS object_end_date,
        a.medium_display                                                   AS medium,
        a.dimensions,
        a.artwork_type_title                                               AS classification,
        a.department_title                                                 AS department,
        a.place_of_origin                                                  AS culture,
        NULL::STRING                                                       AS period,
        NULL::STRING                                                       AS dynasty,
        NULL::STRING                                                       AS country,
        a.credit_line,
        a.main_reference_number                                            AS accession_number,
        a.fiscal_year::STRING                                                  AS accession_year,
        a.is_public_domain,
        a.is_boosted                                                       AS is_highlight,
        a.api_link                                                         AS link_resource,
        NULL::STRING                                                       AS object_wikidata_url,
        art.sort_title                                                     AS primary_artist_alpha_sort,
        art._ulan_url                                                      AS primary_artist_ulan_url,
        'art_institute_chicago'                                            AS source_system
    FROM {{ ref('stg_aic__artworks') }} a
    LEFT JOIN {{ ref('stg_aic__artists') }} art
        ON a.artist_id = art.agent_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY a.artwork_id ORDER BY art.agent_id) = 1

),

all_artworks AS (

    SELECT * FROM met_artworks
    UNION ALL
    SELECT * FROM aic_artworks

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
    {{ dbt_utils.generate_surrogate_key(['all_artworks.source_system', 'all_artworks.source_object_id']) }}
        AS artwork_id,
    all_artworks.source_object_id,
    artists.artist_id,
    all_artworks.title,
    all_artworks.object_date,
    all_artworks.object_begin_date,
    all_artworks.object_end_date,
    all_artworks.medium,
    all_artworks.dimensions,
    all_artworks.classification,
    all_artworks.department,
    all_artworks.culture,
    all_artworks.period,
    all_artworks.dynasty,
    all_artworks.country,
    all_artworks.credit_line,
    all_artworks.accession_number,
    all_artworks.accession_year,
    all_artworks.is_public_domain,
    all_artworks.is_highlight,
    all_artworks.link_resource,
    all_artworks.object_wikidata_url,
    all_artworks.source_system,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM all_artworks
LEFT JOIN artists
    ON all_artworks.primary_artist_alpha_sort = artists.artist_alpha_sort
    AND COALESCE(all_artworks.primary_artist_ulan_url, '') = COALESCE(artists.artist_ulan_url, '')
    AND all_artworks.source_system = artists.source_system
