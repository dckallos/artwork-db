-- merge_aic_agents.sql
-- MERGE INTO RAW_AIC_AGENTS from a temporary staging table.
-- Rendered with str.format():
--   {target} = fully qualified target table
--   {stg}    = temporary staging table name
MERGE INTO {target} AS t
USING (
    SELECT agent_id, raw_payload, _batch_id
    FROM {stg}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY agent_id) = 1
) AS s
ON t.AGENT_ID = s.AGENT_ID
WHEN MATCHED THEN UPDATE SET
    t.RAW_PAYLOAD   = s.RAW_PAYLOAD,
    t._EXTRACTED_AT = CURRENT_TIMESTAMP(),
    t._BATCH_ID     = s._BATCH_ID
WHEN NOT MATCHED THEN INSERT (AGENT_ID, RAW_PAYLOAD, _SOURCE_SYSTEM, _BATCH_ID)
    VALUES (s.AGENT_ID, s.RAW_PAYLOAD, 'art_institute_chicago', s._BATCH_ID);
