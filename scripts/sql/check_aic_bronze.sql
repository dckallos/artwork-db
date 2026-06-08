-- =============================================================================
-- check_aic_bronze.sql -- READ-ONLY ad-hoc check: AIC Bronze health snapshot.
--
-- Run via: bash ../snowflake-toolkit/check.sh scripts/sql/check_aic_bronze.sql
-- Safe anytime; makes no changes. Provides image coverage, row counts, batch
-- provenance, and alt_image distribution for the AIC Bronze tables.
--
-- Baseline (2026-06-07 data audit):
--   134,078 non-deleted artworks | 89.4% have image_id
--   95.8% of public-domain artworks have image_id
--   93% of artworks have 0 alt images | 17,480 total alt images
-- =============================================================================

-- 1) Row counts + deleted breakdown
SELECT 'RAW_AIC_ARTWORKS' AS table_name,
       COUNT(*) AS total_rows,
       COUNT_IF(_is_deleted) AS deleted_rows,
       COUNT_IF(NOT _is_deleted) AS active_rows,
       MAX(_extracted_at) AS last_load
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
UNION ALL
SELECT 'RAW_AIC_AGENTS', COUNT(*), NULL, COUNT(*), MAX(_extracted_at)
FROM ARTWORK_DB.BRONZE.RAW_AIC_AGENTS;

-- 2) Image coverage (the critical data quality metric)
SELECT
    COUNT(*)                                              AS total_artworks,
    COUNT_IF(raw_payload:image_id IS NOT NULL
             AND raw_payload:image_id::STRING != '')      AS has_image_id,
    ROUND(has_image_id / total_artworks * 100, 1)        AS image_pct,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)      AS public_domain,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN
             AND raw_payload:image_id IS NOT NULL
             AND raw_payload:image_id::STRING != '')      AS public_with_image,
    ROUND(public_with_image / NULLIF(public_domain, 0) * 100, 1)
                                                         AS public_image_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
WHERE _is_deleted = FALSE;

-- 3) alt_image_ids distribution
SELECT
    CASE
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) = 0 THEN '0_none'
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) BETWEEN 1 AND 3 THEN '1-3'
        WHEN ARRAY_SIZE(raw_payload:alt_image_ids) BETWEEN 4 AND 10 THEN '4-10'
        ELSE '11+'
    END AS alt_image_bucket,
    COUNT(*) AS artworks
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
WHERE _is_deleted = FALSE
GROUP BY 1
ORDER BY 1;

-- 4) Batch provenance (most recent batches)
SELECT _batch_id, _source_system, COUNT(*) AS row_count,
       MIN(_extracted_at) AS batch_start, MAX(_extracted_at) AS batch_end
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
GROUP BY 1, 2
ORDER BY MAX(_extracted_at) DESC
LIMIT 5;

-- 5) Null-rate check on key fields (data quality regression detector)
SELECT
    ROUND(COUNT_IF(raw_payload:title IS NULL OR raw_payload:title::STRING = '')
          / COUNT(*) * 100, 2) AS title_null_pct,
    ROUND(COUNT_IF(raw_payload:artist_id IS NULL)
          / COUNT(*) * 100, 2) AS artist_id_null_pct,
    ROUND(COUNT_IF(raw_payload:date_display IS NULL OR raw_payload:date_display::STRING = '')
          / COUNT(*) * 100, 2) AS date_display_null_pct,
    ROUND(COUNT_IF(raw_payload:is_public_domain IS NULL)
          / COUNT(*) * 100, 2) AS is_public_domain_null_pct
FROM ARTWORK_DB.BRONZE.RAW_AIC_ARTWORKS
WHERE _is_deleted = FALSE;
