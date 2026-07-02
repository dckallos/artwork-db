-- =============================================================================
-- stg_met__enrichment_status.sql -- Staging model: Met enrichment control state
-- =============================================================================
-- Typed passthrough of the Bronze enrichment control table. One row per Met
-- objectID, tracking enrichment lifecycle (status, image gate, lease, errors).
-- Materialized as a view (Unit 3 decision: queryable + lineage-visible).
--
-- Source: ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL (2327 rows, PK OBJECT_ID)
-- Target: ARTWORK_DB.SILVER.STG_MET__ENRICHMENT_STATUS (view)
--
-- Naming convention: stg_{source}__{entity}
-- =============================================================================

{{ config(materialized='view') }}

WITH source AS (

    SELECT
        object_id,
        enrichment_status,
        last_enriched_at,
        metadata_date,
        has_primary_image,
        image_status,
        last_head_check_at,
        claimed_by_batch,
        claimed_at,
        enrichment_error
    FROM {{ source('met', 'met_enrichment_control') }}

),

renamed AS (

    SELECT
        -- Primary key (join key to stg_met__artworks.object_id)
        object_id,

        -- Enrichment lifecycle
        enrichment_status,                          -- pending | done | no_image | error
        last_enriched_at,                           -- when API discovery last ran
        metadata_date,                              -- Met metadataDate (change signal)

        -- Image gate + liveness
        has_primary_image,                          -- monetization gate (LEG-02 / IMG-02)
        image_status,                               -- unknown | live | dead (IMG-04)
        last_head_check_at,                         -- CDN HEAD liveness-sweep timestamp

        -- Lease (concurrency control for the enrichment fetcher)
        claimed_by_batch,                           -- batch_id holding the lease (NULL = free)
        claimed_at,                                 -- lease timestamp (TTL reclaim)

        -- Diagnostics
        enrichment_error                            -- last fetch error (cleared on success)

    FROM source

)

SELECT * FROM renamed
