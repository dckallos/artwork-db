-- =============================================================================
-- stg_met__artists.sql -- Staging model: deduplicated artist entities from Met
-- =============================================================================
-- Splits pipe-delimited multi-artist fields (the Met CSV packs multiple artists
-- per object into "name1|name2" strings), then deduplicates to one row per
-- distinct artist entity across all objects.
--
-- Grain: one row per artist (identified by artist_alpha_sort + artist_ulan_url).
--
-- WHY this approach:
--   The Met CSV stores artists denormalized ON the artwork row. Multiple artists
--   share pipe-delimited positions (display_name|..., alpha_sort|..., etc.).
--   Splitting positionally and then deduplicating produces a clean dimension that
--   Gold's dim_artists can build on without re-doing the string surgery.
--
-- WHY split only on display_name, then GET(SPLIT(...), index-1) for the rest:
--   SPLIT_TO_TABLE on a NULL input returns ZERO rows, which would drop any source
--   row where even one artist field is NULL (491/503 rows have NULL gender, 46
--   have NULL ulan_url, etc.). By splitting only the anchor field (display_name,
--   which is never NULL) and indexing into the other fields positionally, we
--   preserve all rows regardless of NULLs in secondary fields.
--
-- Deliberate edge case (teaching moment):
--   When artist_ulan_url is NULL/empty (46 objects in our seed), two different
--   artists who share the same alpha_sort would collide. In practice this is
--   extremely rare at the Met (alpha_sort is "Last, First"), but the surrogate
--   key intentionally tolerates it: dbt_utils coalesces NULL -> '' before hashing.
--   If this ever causes a real collision, the fix is adding artist_display_bio
--   to the key grain. For 503 rows it's safe; revisit at full-collection scale.
--
-- Source: ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
-- Target: ARTWORK_DB.SILVER.STG_MET__ARTISTS (view)
-- =============================================================================

WITH source AS (

    SELECT
        object_id,
        raw_payload:csv:artist_display_name::STRING      AS artist_display_name,
        raw_payload:csv:artist_alpha_sort::STRING         AS artist_alpha_sort,
        raw_payload:csv:artist_display_bio::STRING        AS artist_display_bio,
        raw_payload:csv:artist_nationality::STRING        AS artist_nationality,
        raw_payload:csv:artist_begin_date::STRING         AS artist_begin_date,
        raw_payload:csv:artist_end_date::STRING           AS artist_end_date,
        raw_payload:csv:artist_gender::STRING             AS artist_gender,
        raw_payload:csv:artist_role::STRING               AS artist_role,
        raw_payload:csv:artist_ulan_url::STRING           AS artist_ulan_url,
        raw_payload:csv:artist_wikidata_url::STRING       AS artist_wikidata_url,
        _extracted_at
    FROM {{ source('met', 'raw_met_objects') }}

),

-- ---------------------------------------------------------------------------
-- Split pipe-delimited artist fields positionally.
-- Only artist_display_name drives the SPLIT_TO_TABLE (it is never NULL).
-- All other fields are indexed via GET(SPLIT(...), position-1) which is
-- NULL-safe: GET on a NULL array or out-of-bounds index returns NULL.
-- ---------------------------------------------------------------------------
split_artists AS (

    SELECT
        s.object_id,
        TRIM(sn.value::STRING)                                              AS artist_display_name,
        TRIM(GET(SPLIT(s.artist_alpha_sort, '|'), sn.index - 1)::STRING)    AS artist_alpha_sort,
        TRIM(GET(SPLIT(s.artist_display_bio, '|'), sn.index - 1)::STRING)   AS artist_display_bio,
        TRIM(GET(SPLIT(s.artist_nationality, '|'), sn.index - 1)::STRING)   AS artist_nationality,
        TRIM(GET(SPLIT(s.artist_begin_date, '|'), sn.index - 1)::STRING)    AS artist_begin_date,
        TRIM(GET(SPLIT(s.artist_end_date, '|'), sn.index - 1)::STRING)      AS artist_end_date,
        TRIM(GET(SPLIT(s.artist_gender, '|'), sn.index - 1)::STRING)        AS artist_gender,
        TRIM(GET(SPLIT(s.artist_role, '|'), sn.index - 1)::STRING)          AS artist_role,
        TRIM(GET(SPLIT(s.artist_ulan_url, '|'), sn.index - 1)::STRING)      AS artist_ulan_url,
        TRIM(GET(SPLIT(s.artist_wikidata_url, '|'), sn.index - 1)::STRING)  AS artist_wikidata_url,
        sn.index                                                            AS artist_position,
        s._extracted_at
    FROM source s,
        LATERAL SPLIT_TO_TABLE(s.artist_display_name, '|') sn

),

-- ---------------------------------------------------------------------------
-- Generate a deterministic surrogate key per artist entity.
-- The grain is (artist_alpha_sort, artist_ulan_url). Dedup picks the row with
-- the latest extraction timestamp to carry forward the most current bio fields.
-- ---------------------------------------------------------------------------
deduplicated AS (

    SELECT
        {{ dbt_utils.generate_surrogate_key(['artist_alpha_sort', 'artist_ulan_url']) }}
                                                         AS artist_id,
        artist_display_name,
        artist_alpha_sort,
        artist_display_bio,
        artist_nationality,
        artist_begin_date,
        artist_end_date,
        artist_gender,
        artist_role,
        artist_ulan_url,
        artist_wikidata_url,
        _extracted_at
    FROM split_artists
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY artist_alpha_sort, COALESCE(artist_ulan_url, '')
        ORDER BY _extracted_at DESC
    ) = 1

)

SELECT * FROM deduplicated
