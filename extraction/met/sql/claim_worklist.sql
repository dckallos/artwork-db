-- Lease-claim a bounded batch of the prioritized worklist (PIPE-06). Rendered via
-- str.format() in control_enricher.py with:
--   {control}     fully-qualified MET_ENRICHMENT_CONTROL
--   {worklist}    fully-qualified MET_WORKLIST
--   {limit}       batch size (already an int)
--   {dept_filter} either "" (all departments) or "WHERE department = %s"
-- plus positional binds passed to cursor.execute: the claiming batch_id ALWAYS, and
-- the department value WHEN {dept_filter} is non-empty. They are query parameters
-- (never str.format'd) so malformed values cannot inject SQL.
--
-- Bind ordering (pyformat binds positionally by appearance): the SET-clause batch_id
-- %s appears BEFORE the {dept_filter} department %s inside the subquery, so the caller
-- passes (batch_id,) with no department, or (batch_id, department) with one.
--
-- IMPORTANT: control_enricher executes this WITH bind params, so the connector
-- pyformat-binds the ENTIRE command string. Keep every literal percent sign out of
-- this file (control_enricher also strips line comments before binding as a backstop);
-- the only percent tokens are the batch_id bind (SET) and the optional department bind.
--
-- MET_WORKLIST already encodes "claimable" (claimed_at IS NULL) + the IMG-02 priority
-- order (public-domain, highlight, department_priority, object_id). Taking its top
-- {limit} object_ids -- optionally narrowed to a single {dept_filter} department slice
-- so concurrent workers claim DISJOINT partitions -- and stamping the lease
-- (claimed_by_batch + claimed_at) removes them from every future worklist read until the
-- batch finishes (callback clears the lease) or the TTL reclaim task frees an abandoned
-- batch. The redundant claimed_at IS NULL guard makes the claim safe even if two batches
-- race for the same rows.
UPDATE {control}
   SET claimed_by_batch = %s,
       claimed_at       = CURRENT_TIMESTAMP()
 WHERE claimed_at IS NULL
   AND object_id IN (
         SELECT object_id FROM {worklist}
         {dept_filter}
         LIMIT {limit}
       );
