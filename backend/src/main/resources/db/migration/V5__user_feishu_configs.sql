CREATE TABLE IF NOT EXISTS USER_FEISHU_ACCOUNT (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  app_id VARCHAR(128) NULL,
  app_secret_cipher TEXT NULL,
  tenant_access_token_cipher TEXT NULL,
  user_id_type VARCHAR(32) NOT NULL DEFAULT 'open_id',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_user_feishu_account_user (user_id),
  INDEX ix_user_feishu_account_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS USER_FEISHU_TABLE (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  account_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  table_url TEXT NOT NULL,
  app_token VARCHAR(128) NOT NULL,
  table_id VARCHAR(128) NOT NULL,
  table_name VARCHAR(128) NULL,
  view_id VARCHAR(128) NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  field_name_map_json JSON NOT NULL,
  last_test_status VARCHAR(32) NULL,
  last_test_message TEXT NULL,
  last_test_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_user_feishu_table_user_id (user_id),
  INDEX ix_user_feishu_table_account_id (account_id),
  INDEX ix_user_feishu_table_default (user_id, is_default)
);

ALTER TABLE RECORD_SESSION ADD COLUMN feishu_table_config_id VARCHAR(64) NULL;
ALTER TABLE RECORD_SESSION ADD INDEX ix_record_session_feishu_table_config_id (feishu_table_config_id);
