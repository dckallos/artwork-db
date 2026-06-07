-- merge_aic_artworks.sql
-- MERGE INTO RAW_AIC_ARTWORKS from a temporary staging table.
-- Used by the snapshot path. Rendered with str.format():
--   {target} = fully qualified target table
--   {stg}    = temporary staging table name
MERGE INTO {target} AS t
USING (
    SELECT artwork_id, raw_payload, _batch_id
    FROM {stg}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY artwork_id ORDER BY artwork_id) = 1
) AS s
ON t.ARTWORK_ID = s.ARTWORK_ID
WHEN MATCHED THEN UPDATE SET
    t.RAW_PAYLOAD      = s.RAW_PAYLOAD,
    t._EXTRACTED_AT    = CURRENT_TIMESTAMP(),
    t._BATCH_ID        = s._BATCH_ID,
    t._IS_DELETED      = FALSE,
    t._DELETED_AT      = NULL,
    t._DELETION_REASON = NULL
WHEN NOT MATCHED THEN INSERT (ARTWORK_ID, RAW_PAYLOAD, _SOURCE_SYSTEM, _BATCH_ID)
    VALUES (s.ARTWORK_ID, s.RAW_PAYLOAD, 'art_institute_chicago', s._BATCH_ID);
