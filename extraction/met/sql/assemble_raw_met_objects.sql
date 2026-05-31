-- Server-side assembly of BRONZE.RAW_MET_OBJECTS (Option B; docs/context/met-deepdive
-- DDL-05 / PIPE-05). Rendered via str.format() in control_enricher.py with:
--   {raw}       fully-qualified RAW_MET_OBJECTS
--   {snapshot}  fully-qualified MET_CSV_SNAPSHOT
--   {stg}       fully-qualified image-block staging table (object_id, block VARIANT)
--   {batch_id}  the enrich batch id (audit)
--
-- Option B: the 47 descriptive CSV columns live ONLY in Snowflake (MET_CSV_SNAPSHOT).
-- We never ship them back from the Mac. The Mac fetches only the small image block;
-- the wide raw_payload is assembled HERE by joining the snapshot to that block. The
-- payload shape mirrors the legacy uploader's _build_payload (csv / api_images /
-- _meta) so Silver is indifferent to which path produced a row.
--
-- Only objects with a real primary image (enrichment_status = 'done') become Bronze
-- rows; no_image / error outcomes are recorded in the control table only. MERGE keyed
-- on object_id keeps exactly one current Bronze row per object (re-enrichment after a
-- metadata change refreshes in place rather than duplicating); RAW_MET_OBJECTS has no
-- ENFORCED key, so the MERGE load pattern carries that guarantee at runtime.
MERGE INTO {raw} AS t
USING (
    SELECT
        s.object_id AS object_id,
        OBJECT_CONSTRUCT(
            'object_id',  s.object_id,
            'csv',        s.raw_payload,
            'api_images', OBJECT_CONSTRUCT(
                'primary_image',       b.block:primary_image,
                'primary_image_small', b.block:primary_image_small,
                'additional_images',   b.block:additional_images
            ),
            '_meta', OBJECT_CONSTRUCT(
                'source_system', 'met_museum',
                'csv_loaded_at', s._extracted_at,
                'enriched_at',   CURRENT_TIMESTAMP(),
                'batch_id',      '{batch_id}'
            )
        ) AS raw_payload
    FROM {stg} AS b
    JOIN {snapshot} AS s
      ON s.object_id = b.object_id
    WHERE b.block:enrichment_status::STRING = 'done'
) AS src
ON t.object_id = src.object_id
WHEN MATCHED THEN UPDATE SET
    t.raw_payload   = src.raw_payload,
    t._extracted_at = CURRENT_TIMESTAMP(),
    t._batch_id     = '{batch_id}'
WHEN NOT MATCHED THEN INSERT (object_id, raw_payload, _batch_id)
    VALUES (src.object_id, src.raw_payload, '{batch_id}');
