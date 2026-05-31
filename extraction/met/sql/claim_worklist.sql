-- Lease-claim a bounded batch of the prioritized worklist (PIPE-06). Rendered via
-- str.format() in control_enricher.py with:
--   {control}   fully-qualified MET_ENRICHMENT_CONTROL
--   {worklist}  fully-qualified MET_WORKLIST
--   {limit}     batch size (already an int)
-- and one %s bind: the claiming batch_id.
--
-- MET_WORKLIST already encodes "claimable" (claimed_at IS NULL) + the IMG-02
-- priority order (public-domain, highlight, department, object_id). Taking its top
-- {limit} object_ids and stamping the lease (claimed_by_batch + claimed_at) removes
-- them from every future worklist read until the batch finishes (callback clears
-- the lease) or the TTL reclaim task frees an abandoned batch. The redundant
-- claimed_at IS NULL guard on the UPDATE makes the claim safe even if two batches
-- race.
UPDATE {control}
   SET claimed_by_batch = %s,
       claimed_at       = CURRENT_TIMESTAMP()
 WHERE claimed_at IS NULL
   AND object_id IN (SELECT object_id FROM {worklist} LIMIT {limit});
