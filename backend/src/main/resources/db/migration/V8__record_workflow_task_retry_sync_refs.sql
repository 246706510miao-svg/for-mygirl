ALTER TABLE RECORD_WORKFLOW_TASK
  ADD COLUMN record_id VARCHAR(64) NULL AFTER draft_id,
  ADD COLUMN sync_id VARCHAR(64) NULL AFTER record_id,
  ADD INDEX ix_record_workflow_task_record_id (record_id),
  ADD INDEX ix_record_workflow_task_sync_id (sync_id);
