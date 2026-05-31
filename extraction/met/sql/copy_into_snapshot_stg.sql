-- Load CSV-derived JSON rows from the Bronze internal stage into a TEMPORARY
-- staging table. Rendered via str.format() in snapshot_loader.py with:
--   {stg}       fully-qualified temporary staging table
--   {stage}     fully-qualified stage prefix (already includes the leading @)
--   {batch_id}  surfaced into the _batch_id audit column
--   {filename}  the staged NDJSON file name (without path prefix)
--
-- COPY cannot MERGE, so we land into a transient session table first; the
-- snapshot's PK 1:1 guarantee is then enforced by merge_csv_snapshot.sql.
COPY INTO {stg} (object_id, raw_payload, _batch_id)
FROM (
    SELECT
        $1:object_id::NUMBER,
        $1,
        '{batch_id}'
    FROM {stage}/met_snapshot/{batch_id}/{filename}
)
FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = FALSE)
ON_ERROR = 'ABORT_STATEMENT'
PURGE = TRUE;
