-- Release any lease held by a batch WITHOUT changing enrichment_status (failure
-- path). Rendered via str.format() in met_enricher.py with:
--   {control}   fully-qualified MET_ENRICHMENT_CONTROL
--   {batch_id}  this run's lease owner id
--
-- If the enrich run dies after claiming but before the status callback commits, we
-- free the lease here so the rows return to the worklist on the next run rather
-- than waiting out MET_LEASE_RECLAIM_TASK's TTL. enrichment_status is left as-is
-- (still 'pending'/'error'), so nothing is lost.
UPDATE {control} AS t
SET claimed_by_batch = NULL,
    claimed_at       = NULL
WHERE t.claimed_by_batch = '{batch_id}';
