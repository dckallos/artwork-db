-- Load API-fetched image blocks from the Bronze stage into a TEMPORARY staging
-- table. Rendered via str.format() in met_enricher.py with:
--   {stg}       fully-qualified temporary staging table
--   {stage}     fully-qualified stage prefix (already includes the leading @)
--   {batch_id}  this run's batch id (stage subpath)
--   {filename}  the staged NDJSON file name (without path prefix)
--
-- Each NDJSON row is {object_id, status, primary_image, primary_image_small,
-- additional_images:[...]}. Only the image block is shipped up -- the 47
-- descriptive columns already live in MET_CSV_SNAPSHOT (Option B), so the Bronze
-- row is assembled server-side from snapshot x this staging table.
COPY INTO {stg} (object_id, status, primary_image, primary_image_small, additional_images)
FROM (
    SELECT
        $1:object_id::NUMBER,
        $1:status::STRING,
        $1:primary_image::STRING,
        $1:primary_image_small::STRING,
        $1:additional_images
    FROM {stage}/met_enrich/{batch_id}/{filename}
)
FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = FALSE)
ON_ERROR = 'ABORT_STATEMENT'
PURGE = TRUE;
