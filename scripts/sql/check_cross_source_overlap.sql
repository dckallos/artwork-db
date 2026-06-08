-- =============================================================================
-- check_cross_source_overlap.sql -- READ-ONLY: Cross-source artist overlap.
--
-- Run via: bash ../snowflake-toolkit/check.sh scripts/sql/check_cross_source_overlap.sql
-- Safe anytime; makes no changes. Measures artist overlap between Met and AIC
-- using multiple signals: ULAN exact match, normalized name exact match, and
-- name + birth-year match.
--
-- Purpose: Directly feeds entity resolution upgrade criteria (D2).
-- When this shows >10% overlap on any high-confidence signal, it's time to
-- build int_artist_crosswalk.
--
-- Prerequisite: Both RAW_MET_OBJECTS and RAW_AIC_AGENTS must be populated.
-- =============================================================================

-- 1) ULAN exact match (highest confidence, lowest coverage)
--    AIC has effectively 0% ULAN. This query is here for when that changes.
SELECT
    COUNT(*) AS shared_ulan_count,
    '(expect ~0 given current AIC ULAN coverage)' AS note
FROM (
    SELECT DISTINCT
        NULLIF(SPLIT_PART(raw_payload:csv:artist_ulan_url::STRING, '/', -1), '') AS ulan_numeric
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_ulan_url::STRING IS NOT NULL
      AND raw_payload:csv:artist_ulan_url::STRING != ''
) met
INNER JOIN (
    SELECT DISTINCT raw_payload:ulan_id::STRING AS ulan_numeric
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE TRY_CAST(raw_payload:ulan_id::STRING AS NUMBER) IS NOT NULL
      AND raw_payload:ulan_id::NUMBER > 0
) aic
ON met.ulan_numeric = aic.ulan_numeric;

-- 2) Exact name match (normalized: UPPER + TRIM on "Last, First" sort key)
--    This is the Tier 3 resolution signal. High recall, moderate precision.
SELECT
    COUNT(*) AS exact_name_matches
FROM (
    SELECT DISTINCT
        UPPER(TRIM(
            GET(SPLIT(raw_payload:csv:artist_alpha_sort::STRING, '|'), 0)::STRING
        )) AS norm_name
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_alpha_sort::STRING IS NOT NULL
) met
INNER JOIN (
    SELECT DISTINCT
        UPPER(TRIM(raw_payload:sort_title::STRING)) AS norm_name
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:is_artist::BOOLEAN
      AND raw_payload:sort_title::STRING IS NOT NULL
) aic
ON met.norm_name = aic.norm_name;

-- 3) Name + birth year match (higher confidence than name alone)
SELECT
    COUNT(*) AS name_plus_birth_matches
FROM (
    SELECT DISTINCT
        UPPER(TRIM(
            GET(SPLIT(raw_payload:csv:artist_alpha_sort::STRING, '|'), 0)::STRING
        )) AS norm_name,
        TRIM(
            GET(SPLIT(raw_payload:csv:artist_begin_date::STRING, '|'), 0)::STRING
        ) AS birth_year
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_alpha_sort::STRING IS NOT NULL
      AND raw_payload:csv:artist_begin_date::STRING IS NOT NULL
) met
INNER JOIN (
    SELECT DISTINCT
        UPPER(TRIM(raw_payload:sort_title::STRING)) AS norm_name,
        raw_payload:birth_date::STRING AS birth_year
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:is_artist::BOOLEAN
      AND raw_payload:sort_title::STRING IS NOT NULL
      AND raw_payload:birth_date IS NOT NULL
) aic
ON met.norm_name = aic.norm_name
AND met.birth_year = aic.birth_year;

-- 4) Top 20 high-confidence name matches (for manual inspection)
SELECT
    aic.norm_name AS aic_sort_title,
    met.norm_name AS met_alpha_sort,
    aic.birth_year AS aic_birth,
    met.birth_year AS met_birth,
    aic.death_year AS aic_death
FROM (
    SELECT DISTINCT
        UPPER(TRIM(raw_payload:sort_title::STRING)) AS norm_name,
        raw_payload:birth_date::STRING AS birth_year,
        raw_payload:death_date::STRING AS death_year
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:is_artist::BOOLEAN
      AND raw_payload:sort_title::STRING IS NOT NULL
) aic
INNER JOIN (
    SELECT DISTINCT
        UPPER(TRIM(
            GET(SPLIT(raw_payload:csv:artist_alpha_sort::STRING, '|'), 0)::STRING
        )) AS norm_name,
        TRIM(
            GET(SPLIT(raw_payload:csv:artist_begin_date::STRING, '|'), 0)::STRING
        ) AS birth_year
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_alpha_sort::STRING IS NOT NULL
) met
ON aic.norm_name = met.norm_name
ORDER BY aic.norm_name
LIMIT 20;

-- 5) Summary: overlap as percentage of each source's artist pool
WITH met_artists AS (
    SELECT DISTINCT
        UPPER(TRIM(
            GET(SPLIT(raw_payload:csv:artist_alpha_sort::STRING, '|'), 0)::STRING
        )) AS norm_name
    FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS
    WHERE raw_payload:csv:artist_alpha_sort::STRING IS NOT NULL
),
aic_artists AS (
    SELECT DISTINCT
        UPPER(TRIM(raw_payload:sort_title::STRING)) AS norm_name
    FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
    WHERE raw_payload:is_artist::BOOLEAN
      AND raw_payload:sort_title::STRING IS NOT NULL
),
overlap AS (
    SELECT COUNT(*) AS shared FROM met_artists m INNER JOIN aic_artists a ON m.norm_name = a.norm_name
)
SELECT
    (SELECT COUNT(*) FROM met_artists) AS met_distinct_artists,
    (SELECT COUNT(*) FROM aic_artists) AS aic_distinct_artists,
    (SELECT shared FROM overlap) AS name_overlap,
    ROUND((SELECT shared FROM overlap) / (SELECT COUNT(*) FROM met_artists) * 100, 1) AS overlap_pct_of_met,
    ROUND((SELECT shared FROM overlap) / (SELECT COUNT(*) FROM aic_artists) * 100, 1) AS overlap_pct_of_aic;
