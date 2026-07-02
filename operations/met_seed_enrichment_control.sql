-- =============================================================================
-- met_seed_enrichment_control.sql  --  Section C, Phase 2: seed the enrichment slice
--
-- Inserts one PENDING control row per object in the CHOSEN enrichment slice, so
-- MET_WORKLIST lights up and the Mac can begin draining (Phase 3). The full
-- ~485k descriptive snapshot already lives in BRONZE.MET_CSV_SNAPSHOT (Phase 1);
-- enrichment is bounded HERE, at the control seed, not at the snapshot.
--
-- Chosen slice (owner, 2026-05-31): culture = 'American' AND is_public_domain = TRUE
--   -> 12,176 objects (verified). Adjust the WHERE predicate to seed a different slice.
--
-- Idempotency: MERGE on object_id, INSERT only WHEN NOT MATCHED. Re-running never
-- resets a row already being worked (status/lease untouched). Safe to re-run after
-- adding more slices.
--
-- Rollback (un-seed this slice):
--   DELETE FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL c
--   USING ARTWORK_DB.BRONZE.MET_CSV_SNAPSHOT s
--   WHERE c.object_id = s.object_id
--     AND s.raw_payload:culture::STRING = 'American'
--     AND s.raw_payload:is_public_domain::BOOLEAN = TRUE
--     AND c.enrichment_status = 'pending' AND c.claimed_at IS NULL;
--
-- Run as ARTWORK_LOADER (has INSERT/UPDATE on BRONZE) or ACCOUNTADMIN:
--   snow sql -c loader -f operations/met_seed_enrichment_control.sql
--
-- NOTE: raw_payload:metadata_date is empty across the whole current snapshot, so
-- control.metadata_date seeds NULL (IMG-03 incremental signal dormant; rows light
-- up via has_primary_image IS NULL instead). TRY_TO_DATE is kept defensively so a
-- future CSV that populates Metadata Date carries through with no SQL change.
-- =============================================================================

USE ROLE ARTWORK_LOADER;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

MERGE INTO MET_ENRICHMENT_CONTROL c
USING (
    SELECT
        object_id,
        TRY_TO_DATE(raw_payload:metadata_date::STRING) AS metadata_date
    FROM MET_CSV_SNAPSHOT
    WHERE raw_payload:culture::STRING       = 'American'
      AND raw_payload:is_public_domain::BOOLEAN = TRUE
) s
ON c.object_id = s.object_id
WHEN NOT MATCHED THEN INSERT (object_id, enrichment_status, metadata_date)
    VALUES (s.object_id, 'pending', s.metadata_date);
