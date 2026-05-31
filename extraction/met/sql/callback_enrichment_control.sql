-- Write the API outcome back into MET_ENRICHMENT_CONTROL and release the lease
-- (PIPE-06 status callback). Rendered via str.format() in control_enricher.py with:
--   {control}  fully-qualified MET_ENRICHMENT_CONTROL
--   {stg}      fully-qualified image-block staging table (object_id, block VARIANT)
--
-- Runs for EVERY claimed object in the batch (done / no_image / error), not just the
-- ones that produced a Bronze row, so the lease is always cleared and the row's
-- terminal state recorded. Clearing claimed_by_batch / claimed_at returns the row to
-- the "not leased" pool; because enrichment_status moves to done/no_image, the
-- worklist's pending/error filter then excludes it (error rows remain claimable for
-- automatic retry). last_enriched_at advances so the IMG-03 metadata_date delta is
-- evaluated against this pass on future re-seeds.
MERGE INTO {control} AS c
USING (
    SELECT object_id, block FROM {stg}
) AS s
ON c.object_id = s.object_id
WHEN MATCHED THEN UPDATE SET
    c.enrichment_status = s.block:enrichment_status::STRING,
    c.has_primary_image = s.block:has_primary_image::BOOLEAN,
    c.last_enriched_at  = CURRENT_TIMESTAMP(),
    c.claimed_by_batch  = NULL,
    c.claimed_at        = NULL;
