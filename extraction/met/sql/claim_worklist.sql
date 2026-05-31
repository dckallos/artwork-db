-- Lease-claim a bounded batch of the prioritized worklist (PIPE-06). Rendered via
-- str.format() in met_enricher.py with:
--   {control}       fully-qualified MET_ENRICHMENT_CONTROL
--   {worklist}      fully-qualified MET_WORKLIST
--   {batch_id}      this run's lease owner id (machine-generated token; str.format'd,
--                   never a pyformat bind -- this command is executed WITHOUT params)
--   {limit_clause}  'LIMIT <n>' to bound the batch, or '' for the whole worklist
--
-- NOTE: keep ALL literal percent signs out of this file. met_enricher executes this
-- WITHOUT params (every value is str.format'd), so no pyformat binding runs here -- but
-- staying percent-free keeps the file safe if a bind is ever added.
--
-- MET_WORKLIST already encodes "claimable" (claimed_at IS NULL) + the IMG-02 priority
-- order (public-domain, highlight, department, object_id). Taking its top {limit_clause}
-- object_ids and stamping the lease (claimed_by_batch + claimed_at) removes them from
-- every future worklist read until the batch finishes (callback clears the lease) or the
-- TTL reclaim task frees an abandoned batch. The redundant claimed_at IS NULL guard on
-- the UPDATE makes the claim safe even if two batches race.
UPDATE {control}
   SET claimed_by_batch = '{batch_id}',
       claimed_at       = CURRENT_TIMESTAMP()
 WHERE claimed_at IS NULL
   AND object_id IN (SELECT object_id FROM {worklist} {limit_clause});
