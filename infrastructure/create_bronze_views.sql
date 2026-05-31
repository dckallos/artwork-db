-- =============================================================================
-- create_bronze_views.sql: Bronze views for the Met enrichment pipeline
-- MET_WORKLIST -- the prioritized, lease-aware worklist the Mac drains (the
-- Snowflake->Mac half of the two-table contract; see docs/context/met-deepdive.md
-- AUTO-01/AUTO-02/IMG-02 + Session-1 strawman section 2).
--
-- A VIEW (not a second table) so it can never drift from MET_ENRICHMENT_CONTROL
-- (single authority). Priority truth comes from MET_CSV_SNAPSHOT (VARIANT raw
-- CSV blob), which is landed at bootstrap independent of enrichment so PENDING
-- rows can be ranked before they are ever fetched.
--
-- Idempotency: CREATE OR REPLACE (stateless/derived object, per the class-based
-- idempotency split in docs/context/ddl-infrastructure.md).
-- Paired rollback: infrastructure/drop_bronze_views.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

CREATE OR REPLACE VIEW MET_WORKLIST
COMMENT = 'Prioritized, lease-aware Met enrichment worklist (control x CSV snapshot). The Mac drains this.'
AS
SELECT
    c.object_id,
    c.enrichment_status,
    c.metadata_date,
    c.last_enriched_at,
    c.has_primary_image,
    -- Priority inputs (CSV truth, not duplicated into control): extracted from
    -- the VARIANT snapshot. CSV booleans arrive as 'True'/'False' text; ::BOOLEAN
    -- uses TO_BOOLEAN semantics (case-insensitive) so the cast is safe.
    s.raw_payload:is_public_domain::BOOLEAN   AS is_public_domain,
    s.raw_payload:is_highlight::BOOLEAN       AS is_highlight,
    s.raw_payload:department::STRING          AS department,
    -- IMG-02 department ranking: monetizable, image-rich departments first.
    CASE
        WHEN s.raw_payload:department::STRING ILIKE '%painting%'                                  THEN 1
        WHEN s.raw_payload:department::STRING ILIKE '%drawing%'
          OR s.raw_payload:department::STRING ILIKE '%print%'                                     THEN 2
        WHEN s.raw_payload:department::STRING ILIKE '%photograph%'                                THEN 3
        WHEN s.raw_payload:department::STRING ILIKE '%sculpture%'                                 THEN 4
        ELSE 9
    END                                       AS department_priority
FROM MET_ENRICHMENT_CONTROL c
JOIN MET_CSV_SNAPSHOT       s
  ON s.object_id = c.object_id
WHERE c.claimed_at IS NULL                              -- not currently leased
  AND (
        c.enrichment_status IN ('pending', 'error')     -- never done / retryable
        OR c.metadata_date  > c.last_enriched_at         -- upstream changed (IMG-03)
        OR c.has_primary_image IS NULL                   -- never discovered
      )
ORDER BY
    is_public_domain    DESC,   -- IMG-02: public-domain (sellable) first
    is_highlight        DESC,   -- then curatorial highlights
    department_priority ASC,    -- then high-value departments
    c.object_id ASC;            -- stable tiebreaker
