-- =============================================================================
-- dim_artists.sql -- Gold: Conformed artist dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artist entity per source system
-- PK: artist_id (MD5 hash of artist_alpha_sort + artist_ulan_url + source_system)
--
-- Sources: stg_met__artists, stg_aic__artists
-- UNION column order: MUST match between met_artists and aic_artists CTEs (P3-3).
-- =============================================================================

WITH met_artists AS (

    -- Column order: MUST match [aic_artists] CTE below
    SELECT
        artist_display_name,
        artist_alpha_sort,
        artist_display_bio,
        artist_nationality,
        artist_begin_date,
        artist_end_date,
        artist_gender,
        artist_ulan_url,
        artist_wikidata_url,
        'met_museum' AS source_system,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM {{ ref('stg_met__artists') }}

),

aic_artists AS (

    -- Column order: MUST match [met_artists] CTE above
    SELECT
        title                               AS artist_display_name,
        sort_title                          AS artist_alpha_sort,
        description                         AS artist_display_bio,
        NULL::STRING                        AS artist_nationality,
        birth_date::STRING                  AS artist_begin_date,
        death_date::STRING                  AS artist_end_date,
        NULL::STRING                        AS artist_gender,
        _ulan_url                           AS artist_ulan_url,
        NULL::STRING                        AS artist_wikidata_url,
        'art_institute_chicago'             AS source_system,
        CURRENT_TIMESTAMP()::TIMESTAMP_NTZ   AS _loaded_at
    FROM {{ ref('stg_aic__artists') }}
    WHERE is_artist = TRUE

),

unioned AS (

    SELECT * FROM met_artists
    UNION ALL
    SELECT * FROM aic_artists

)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artist_alpha_sort', 'artist_ulan_url', 'source_system']) }}
        AS artist_id,
    artist_display_name,
    artist_alpha_sort,
    artist_display_bio,
    artist_nationality,
    artist_begin_date,
    artist_end_date,
    artist_gender,
    artist_ulan_url,
    artist_wikidata_url,
    source_system,
    _loaded_at
FROM unioned
