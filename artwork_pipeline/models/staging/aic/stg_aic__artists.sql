-- =============================================================================
-- stg_aic__artists.sql -- Staging model: all agent entities from AIC
-- =============================================================================
-- Flattens the RAW_PAYLOAD VARIANT into typed columns. Unlike Met's pipe-
-- delimited multi-artist split, AIC agents are already one-per-row -- no
-- SPLIT_TO_TABLE or deduplication needed.
--
-- ALL agents pass through staging (D5). Gold applies WHERE is_artist = TRUE
-- for dim_artists; non-artist agents (curators, donors, orgs) are available
-- for future Gold models.
--
-- Entity resolution pre-positioning: _ulan_url is computed from the numeric
-- ulan_id when non-null. Data audit (2026-06-07) showed only 1 of 16,051
-- agents has a real ULAN ID -- source-partitioned v1 (D2) is correct.
--
-- Grain: one row per agent (agent_id is the natural key from the AIC API).
--
-- Source: ARTWORK_DB.BRONZE.RAW_AIC_AGENTS
-- Target: ARTWORK_DB.SILVER.STG_AIC__ARTISTS (view)
-- =============================================================================

WITH source AS (

    SELECT
        agent_id,
        raw_payload,
        _extracted_at,
        _source_system
    FROM {{ source('aic', 'raw_aic_agents') }}

),

typed AS (

    SELECT
        -- Primary key
        agent_id,

        -- Core agent attributes
        raw_payload:title::STRING                          AS title,
        raw_payload:sort_title::STRING                     AS sort_title,
        raw_payload:alt_titles                             AS alt_titles,
        raw_payload:is_artist::BOOLEAN                     AS is_artist,
        raw_payload:birth_date::INT                        AS birth_date,
        raw_payload:death_date::INT                        AS death_date,
        raw_payload:description::STRING                    AS description,

        -- ULAN identifier (numeric). Data audit: 1/16051 agents have a real value.
        -- Pre-positioned for entity resolution upgrade (D2 criteria).
        raw_payload:ulan_id::NUMBER                        AS ulan_id,
        CASE
            WHEN raw_payload:ulan_id IS NOT NULL
                 AND TRY_CAST(raw_payload:ulan_id::STRING AS NUMBER) IS NOT NULL
                 AND raw_payload:ulan_id::NUMBER > 0
            THEN 'http://vocab.getty.edu/page/ulan/' || raw_payload:ulan_id::STRING
        END                                                AS _ulan_url,

        -- Extraction metadata
        _extracted_at,
        _source_system

    FROM source

)

SELECT * FROM typed
