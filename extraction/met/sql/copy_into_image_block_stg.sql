-- Load locally-fetched image blocks from the Bronze internal stage into the
-- session TEMPORARY staging table. Rendered via str.format() in control_enricher.py:
--   {stg}       fully-qualified temporary staging table (object_id, block VARIANT)
--   {stage}     fully-qualified stage prefix (already includes the leading @)
--   {batch_id}  the enrich batch id (path segment + audit)
--   {filename}  the staged NDJSON file name (without path prefix)
--
-- One JSON document per claimed object: the API outcome for that object_id
-- (enrichment_status, has_primary_image, the image URLs). This staging table is the
-- single source the assemble + callback MERGEs both read, so the server-side
-- assembly and the control callback always agree on the same batch of results.
COPY INTO {stg} (object_id, block)
FROM (
    SELECT
        $1:object_id::NUMBER,
        $1
    FROM {stage}/met_enrich/{batch_id}/{filename}
)
FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = FALSE)
ON_ERROR = 'ABORT_STATEMENT'
PURGE = TRUE;
