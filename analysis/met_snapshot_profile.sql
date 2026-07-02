-- =============================================================================
-- met_snapshot_profile.sql -- profile BRONZE.MET_CSV_SNAPSHOT to choose the first
-- enrichment slice (Section C, Phase 1.5). READ-ONLY. Run after the snapshot load.
--
-- The snapshot is the FULL collection (cheap VARIANT landing); enrichment is what
-- we bound. These queries rank candidate slices so you can pick ONE department /
-- classification / period / movement to seed into MET_ENRICHMENT_CONTROL (Phase 2).
-- Priority lens mirrors MET_WORKLIST: public-domain (sellable) > highlight > dept.
--
-- Run as ARTWORK_LOADER (has SELECT on the table) or any role with SELECT.
-- Usage: snow sql -c loader -f analysis/met_snapshot_profile.sql   (or paste a
-- single query into a worksheet).
-- =============================================================================

USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

-- 0. Sanity: total rows + how many are public-domain (the monetizable universe).
SELECT
    COUNT(*)                                                          AS total_objects,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)                   AS public_domain,
    COUNT_IF(raw_payload:is_highlight::BOOLEAN)                       AS highlights
FROM MET_CSV_SNAPSHOT;

-- 1. By department: total, public-domain, highlights. The primary slice axis.
SELECT
    raw_payload:department::STRING                                    AS department,
    COUNT(*)                                                          AS objects,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)                   AS public_domain,
    COUNT_IF(raw_payload:is_highlight::BOOLEAN)                       AS highlights
FROM MET_CSV_SNAPSHOT
GROUP BY 1
ORDER BY public_domain DESC NULLS LAST;

-- 2. By classification (medium family) within the public-domain universe.
SELECT
    raw_payload:classification::STRING                               AS classification,
    COUNT(*)                                                         AS objects
FROM MET_CSV_SNAPSHOT
WHERE raw_payload:is_public_domain::BOOLEAN = TRUE
GROUP BY 1
ORDER BY objects DESC NULLS LAST
LIMIT 50;

-- 3. By culture / period / dynasty -- "movement"-style slices (top buckets only).
SELECT
    raw_payload:culture::STRING                                     AS culture,
    raw_payload:period::STRING                                      AS period,
    COUNT(*)                                                        AS objects,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)                 AS public_domain
FROM MET_CSV_SNAPSHOT
GROUP BY 1, 2
HAVING objects >= 200
ORDER BY public_domain DESC NULLS LAST
LIMIT 50;

-- 4. By century (from Object Begin Date) -- chronological slices.
SELECT
    FLOOR(TRY_TO_NUMBER(raw_payload:object_begin_date::STRING) / 100.0) * 100 AS century_start,
    COUNT(*)                                                                  AS objects,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)                            AS public_domain
FROM MET_CSV_SNAPSHOT
WHERE TRY_TO_NUMBER(raw_payload:object_begin_date::STRING) IS NOT NULL
GROUP BY 1
ORDER BY century_start;

-- 5. Candidate ready-to-seed slices: department x public-domain, image-priority
--    ordered exactly like MET_WORKLIST's department_priority so the top rows are
--    the best first enrichment targets.
SELECT
    raw_payload:department::STRING                                   AS department,
    COUNT_IF(raw_payload:is_public_domain::BOOLEAN)                  AS public_domain_objects,
    CASE
        WHEN raw_payload:department::STRING ILIKE '%painting%'                              THEN 1
        WHEN raw_payload:department::STRING ILIKE '%drawing%'
          OR raw_payload:department::STRING ILIKE '%print%'                                 THEN 2
        WHEN raw_payload:department::STRING ILIKE '%photograph%'                            THEN 3
        WHEN raw_payload:department::STRING ILIKE '%sculpture%'                             THEN 4
        ELSE 9
    END                                                             AS department_priority
FROM MET_CSV_SNAPSHOT
GROUP BY 1, 3
HAVING public_domain_objects > 0
ORDER BY department_priority ASC, public_domain_objects DESC;
