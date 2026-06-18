CREATE TABLE IF NOT EXISTS APP_PERSON (
  id VARCHAR(64) PRIMARY KEY,
  role VARCHAR(32) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS RECORD_SESSION (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  record_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL,
  current_draft_id VARCHAR(64) NULL,
  request_id VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_record_session_user_id (user_id),
  INDEX ix_record_session_status (status)
);

CREATE TABLE IF NOT EXISTS RECORD_MESSAGE (
  id VARCHAR(64) PRIMARY KEY,
  session_id VARCHAR(64) NOT NULL,
  sender VARCHAR(32) NOT NULL,
  input_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  asr_text TEXT NULL,
  sequence_no INT NOT NULL,
  client_message_id VARCHAR(128) NULL,
  third_session_id VARCHAR(64) NULL,
  request_id VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_record_message_session_client (session_id, client_message_id),
  INDEX ix_record_message_session_id (session_id),
  INDEX ix_record_message_third_session_id (third_session_id)
);

CREATE TABLE IF NOT EXISTS RECORD_DRAFT (
  id VARCHAR(64) PRIMARY KEY,
  session_id VARCHAR(64) NOT NULL,
  version_no INT NOT NULL,
  draft_json JSON NOT NULL,
  preview_text TEXT NOT NULL,
  status VARCHAR(32) NOT NULL,
  third_session_id VARCHAR(64) NULL,
  request_id VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_record_draft_session_version (session_id, version_no),
  INDEX ix_record_draft_session_id (session_id),
  INDEX ix_record_draft_third_session_id (third_session_id)
);

CREATE TABLE IF NOT EXISTS DAILY_RECORD (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  final_draft_id VARCHAR(64) NOT NULL,
  record_date DATE NOT NULL,
  final_text TEXT NOT NULL,
  ai_summary TEXT NULL,
  ai_score INT NULL,
  tags_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL,
  client_confirm_id VARCHAR(128) NOT NULL,
  third_session_id VARCHAR(64) NULL,
  request_id VARCHAR(128) NULL,
  confirmed_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_daily_record_session_confirm (session_id, client_confirm_id),
  UNIQUE KEY uq_daily_record_session_once (session_id),
  INDEX ix_daily_record_user_date (user_id, record_date),
  INDEX ix_daily_record_status (status),
  INDEX ix_daily_record_third_session_id (third_session_id)
);

CREATE TABLE IF NOT EXISTS RECORD_DISPLAY (
  id VARCHAR(64) PRIMARY KEY,
  record_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  summary TEXT NOT NULL,
  score INT NULL,
  display_status VARCHAR(32) NOT NULL,
  admin_content_json JSON NOT NULL,
  display_json JSON NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_record_display_record_id (record_id),
  INDEX ix_record_display_status (display_status)
);

CREATE TABLE IF NOT EXISTS DAILY_CONTENT (
  id VARCHAR(64) PRIMARY KEY,
  target_user_id VARCHAR(64) NOT NULL,
  created_by VARCHAR(64) NOT NULL,
  content_date DATE NOT NULL,
  content_type VARCHAR(32) NOT NULL,
  display_area VARCHAR(32) NOT NULL,
  content_json JSON NOT NULL,
  resource_id VARCHAR(64) NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_daily_content_scope (target_user_id, content_date, display_area, content_type),
  INDEX ix_daily_content_target_date (target_user_id, content_date)
);

CREATE TABLE IF NOT EXISTS RESOURCE_FILE (
  id VARCHAR(64) PRIMARY KEY,
  uploaded_by VARCHAR(64) NOT NULL,
  file_type VARCHAR(32) NOT NULL,
  usage_type VARCHAR(32) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_url VARCHAR(512) NOT NULL,
  storage_path VARCHAR(512) NOT NULL,
  mime_type VARCHAR(128) NULL,
  file_size BIGINT NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_resource_file_uploaded_by (uploaded_by)
);

CREATE TABLE IF NOT EXISTS FEISHU_SYNC (
  id VARCHAR(64) PRIMARY KEY,
  record_id VARCHAR(64) NOT NULL,
  config_id VARCHAR(64) NULL,
  target_type VARCHAR(32) NOT NULL,
  target_id VARCHAR(255) NULL,
  payload_json JSON NOT NULL,
  feishu_ref_id VARCHAR(255) NULL,
  sync_status VARCHAR(32) NOT NULL,
  error_message TEXT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  third_session_id VARCHAR(64) NULL,
  request_id VARCHAR(128) NULL,
  last_sync_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_feishu_sync_record_id (record_id),
  INDEX ix_feishu_sync_status (sync_status),
  INDEX ix_feishu_sync_third_session_id (third_session_id)
);

CREATE TABLE IF NOT EXISTS APP_CONFIG (
  id VARCHAR(64) PRIMARY KEY,
  config_key VARCHAR(128) NOT NULL,
  config_type VARCHAR(64) NOT NULL,
  config_value JSON NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_app_config_key (config_key)
);
