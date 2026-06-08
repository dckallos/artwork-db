-- =============================================================================
-- check_aic_agents.sql -- READ-ONLY ad-hoc check: AIC agent data quality.
--
-- Run via: bash ../snowflake-toolkit/check.sh scripts/sql/check_aic_agents.sql
-- Safe anytime; makes no changes. Provides agent overview, ULAN coverage
-- (entity resolution readiness), and is_artist distribution.
--
-- Baseline (2026-06-07 data audit):
--   16,051 total agents | 14,105 artists | 1,946 non-artists
--   ULAN coverage: 1/16,051 (0.006%) -- effectively zero
--   sort_title "Last, First" format: 83.6% of artists (rest: orgs + East Asian)
--
-- This script directly feeds entity resolution upgrade criteria (D2):
--   Upgrade when ULAN coverage > 10% OR third source arrives with ULAN.
-- =============================================================================

-- 1) Overview: agent counts + ULAN coverage
SELECT
    COUNT(*)                                          AS total_agents,
    COUNT_IF(raw_payload:is_artist::BOOLEAN)          AS artists,
    COUNT_IF(NOT raw_payload:is_artist::BOOLEAN)      AS non_artists,
    COUNT_IF(raw_payload:ulan_id IS NOT NULL
             AND TRY_CAST(raw_payload:ulan_id::STRING AS NUMBER) IS NOT NULL
             AND raw_payload:ulan_id::NUMBER > 0)     AS has_real_ulan,
    ROUND(has_real_ulan / total_agents * 100, 2)      AS ulan_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS;

-- 2) sort_title format analysis (comma presence = "Last, First" pattern)
SELECT
    COUNT_IF(raw_payload:sort_title::STRING LIKE '%,%') AS has_comma,
    COUNT_IF(raw_payload:sort_title::STRING NOT LIKE '%,%') AS no_comma,
    ROUND(has_comma / COUNT(*) * 100, 1) AS comma_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
WHERE raw_payload:is_artist::BOOLEAN;

-- 3) Non-comma sort_titles (sample: orgs + East Asian names)
SELECT raw_payload:sort_title::STRING AS sort_title,
       raw_payload:title::STRING AS display_title,
       raw_payload:birth_date::INT AS birth_year,
       raw_payload:death_date::INT AS death_year
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
WHERE raw_payload:is_artist::BOOLEAN
  AND raw_payload:sort_title::STRING NOT LIKE '%,%'
LIMIT 10;

-- 4) Null-rate on key agent fields
SELECT
    ROUND(COUNT_IF(raw_payload:title IS NULL OR raw_payload:title::STRING = '')
          / COUNT(*) * 100, 2) AS title_null_pct,
    ROUND(COUNT_IF(raw_payload:sort_title IS NULL OR raw_payload:sort_title::STRING = '')
          / COUNT(*) * 100, 2) AS sort_title_null_pct,
    ROUND(COUNT_IF(raw_payload:birth_date IS NULL)
          / COUNT(*) * 100, 2) AS birth_date_null_pct,
    ROUND(COUNT_IF(raw_payload:death_date IS NULL)
          / COUNT(*) * 100, 2) AS death_date_null_pct,
    ROUND(COUNT_IF(raw_payload:description IS NULL OR raw_payload:description::STRING = '')
          / COUNT(*) * 100, 2) AS description_null_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
WHERE raw_payload:is_artist::BOOLEAN;

-- 5) The one agent with ULAN (Van Gogh -- sanity check it's still there)
SELECT
    raw_payload:title::STRING AS agent_name,
    raw_payload:ulan_id::NUMBER AS ulan_id,
    raw_payload:birth_date::INT AS birth_year,
    raw_payload:death_date::INT AS death_year
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
WHERE TRY_CAST(raw_payload:ulan_id::STRING AS NUMBER) IS NOT NULL
  AND raw_payload:ulan_id::NUMBER > 0;
