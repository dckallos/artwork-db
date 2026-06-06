-- =============================================================================
-- dim_artists.sql -- Gold: Conformed artist dimension
-- =============================================================================
-- Contract: models/marts/_marts__models.yml (enforced)
-- Grain: one row per artist entity
-- PK: artist_id (MD5 hash of artist_alpha_sort + artist_ulan_url + source_system)
--
-- This model passes through from stg_met__artists today. When additional sources
-- (CMA, AIC, Smithsonian) are added, this becomes a UNION ALL with entity
-- resolution logic to merge artists that appear in multiple museums.
-- =============================================================================

WITH met_artists AS (

    SELECT
        artist_id,
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

)

SELECT
    -- Re-generate surrogate key to include source_system in the grain
    -- (future-proofs for multi-source: same artist from different museums
    -- gets one row only if ULAN URLs match; otherwise separate rows until
    -- entity resolution is implemented).
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
FROM met_artists
