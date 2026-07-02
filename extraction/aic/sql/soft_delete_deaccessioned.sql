-- soft_delete_deaccessioned.sql
-- Run AFTER the snapshot MERGE for artworks completes.
-- Any row whose _BATCH_ID does not match the current snapshot batch was NOT
-- in the dump -> deaccessioned / withdrawn / merged into another record.
-- Rendered with str.format():
--   {target}           = fully qualified target table
--   {current_batch_id} = the batch UUID of the just-completed snapshot run
UPDATE {target}
SET _IS_DELETED      = TRUE,
    _DELETED_AT      = CURRENT_TIMESTAMP(),
    _DELETION_REASON = 'snapshot_anti_join'
WHERE _BATCH_ID != '{current_batch_id}'
  AND _IS_DELETED = FALSE;
