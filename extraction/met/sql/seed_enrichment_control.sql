-- Seed BRONZE.MET_ENRICHMENT_CONTROL with pending rows for a bounded slice of the
-- snapshot (Phase 2; docs/context/met-deepdive.md DDL-04 / PIPE-05). Rendered via
-- str.format() in control_seeder.py with:
--   {control}    fully-qualified MET_ENRICHMENT_CONTROL
--   {snapshot}   fully-qualified MET_CSV_SNAPSHOT
--   {predicate}  slice WHERE predicate; may contain positional bind placeholders
--                 (NOTE: keep ALL literal percent signs out of this file -- the
--                 Snowflake connector pyformat-binds the WHOLE command string,
--                 comments included, so a stray percent breaks `command % params`)
--   {limit}      trailing LIMIT clause text ('' or 'LIMIT n', n already an int)
--
-- Why MERGE (not INSERT): re-seeding the same or an overlapping slice must be
-- idempotent and MUST NOT disturb rows already being worked. MERGE keyed on
-- object_id inserts only NEW control rows (WHEN NOT MATCHED); it never resets an
-- existing row's enrichment_status, lease, or has_primary_image. This makes the
-- seed safe to re-run and safe to widen incrementally (seed paintings, then add
-- drawings) without clobbering in-flight or completed work.
--
-- metadata_date is carried from the snapshot at seed time so the IMG-03 "upstream
-- changed" delta (metadata_date > last_enriched_at in MET_WORKLIST) is meaningful
-- from the very first enrichment pass. The Met CSV "Metadata Date" is an ISO-8601
-- timestamp string; TRY_TO_TIMESTAMP tolerates bad/blank values (-> NULL) and the
-- ::DATE narrows it to the control column type.
MERGE INTO {control} AS c
USING (
    SELECT
        object_id,
        TRY_TO_TIMESTAMP(raw_payload:metadata_date::STRING)::DATE AS metadata_date
    FROM {snapshot}
    WHERE {predicate}
    {limit}
) AS s
ON c.object_id = s.object_id
WHEN NOT MATCHED THEN INSERT (object_id, enrichment_status, metadata_date)
    VALUES (s.object_id, 'pending', s.metadata_date);
