-- Bulk-load JSON rows from the Bronze internal stage into raw_met_objects.
-- This file is rendered via str.format() in snowflake_uploader.py with:
--   {table}     fully-qualified target table
--   {stage}     fully-qualified stage prefix (already includes the leading @)
--   {batch_id}  surfaced into the _batch_id audit column
--   {filename}  the staged NDJSON file name (without path prefix)

COPY INTO {table} (object_id, raw_payload, _batch_id)
FROM (
    SELECT
        $1:object_id::INT,
        $1,
        '{batch_id}'
    FROM {stage}/met/{batch_id}/{filename}
)
FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = FALSE)
ON_ERROR = 'ABORT_STATEMENT'
PURGE = TRUE;
