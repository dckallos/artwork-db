-- MERGE the staged Met CSV snapshot into BRONZE.MET_CSV_SNAPSHOT keyed on
-- object_id. Rendered via str.format() in snapshot_loader.py with:
--   {target}  fully-qualified MET_CSV_SNAPSHOT
--   {stg}     fully-qualified temporary staging table
--
-- Why MERGE (not COPY append): the table declares object_id as PRIMARY KEY but
-- Snowflake does not ENFORCE it -- the MERGE is what carries the "exactly one
-- current row per object" guarantee at runtime (DDL-05), keeps the control x
-- snapshot join strictly 1:1, and makes the table re-runnable (DATA-01 diffs the
-- snapshot across runs). QUALIFY de-dups the source so a duplicated Object ID in
-- the CSV cannot raise a non-deterministic-merge error.
MERGE INTO {target} AS t
USING (
    SELECT object_id, raw_payload, _batch_id
    FROM {stg}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY object_id ORDER BY object_id) = 1
) AS s
ON t.object_id = s.object_id
WHEN MATCHED THEN UPDATE SET
    t.raw_payload   = s.raw_payload,
    t._extracted_at = CURRENT_TIMESTAMP(),
    t._batch_id     = s._batch_id
WHEN NOT MATCHED THEN INSERT (object_id, raw_payload, _source_system, _batch_id)
    VALUES (s.object_id, s.raw_payload, 'met_museum', s._batch_id);
