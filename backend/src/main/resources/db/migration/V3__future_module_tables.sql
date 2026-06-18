UPDATE APP_PERSON
SET role = 'OPS_ADMIN', display_name = '后台人员'
WHERE id = 'person_admin';

CREATE TABLE IF NOT EXISTS USER_BINDING (
  id VARCHAR(64) PRIMARY KEY,
  requester_user_id VARCHAR(64) NOT NULL,
  target_user_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_user_binding_pair (requester_user_id, target_user_id),
  INDEX ix_user_binding_target (target_user_id),
  INDEX ix_user_binding_status (status)
);

CREATE TABLE IF NOT EXISTS USER_PERMISSION (
  id VARCHAR(64) PRIMARY KEY,
  binding_id VARCHAR(64) NOT NULL,
  grantee_user_id VARCHAR(64) NOT NULL,
  permission_key VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_user_permission_scope (binding_id, grantee_user_id, permission_key),
  INDEX ix_user_permission_grantee (grantee_user_id, enabled)
);

CREATE TABLE IF NOT EXISTS USER_STYLE (
  id VARCHAR(64) PRIMARY KEY,
  owner_user_id VARCHAR(64) NOT NULL,
  style_json JSON NOT NULL,
  updated_by VARCHAR(64) NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_user_style_owner (owner_user_id),
  INDEX ix_user_style_updated_by (updated_by)
);

CREATE TABLE IF NOT EXISTS RECORD_COMMENT (
  id VARCHAR(64) PRIMARY KEY,
  record_id VARCHAR(64) NOT NULL,
  author_user_id VARCHAR(64) NOT NULL,
  content TEXT NOT NULL,
  visibility VARCHAR(32) NOT NULL DEFAULT 'bound_users',
  created_at DATETIME NOT NULL,
  INDEX ix_record_comment_record (record_id, created_at),
  INDEX ix_record_comment_author (author_user_id)
);

CREATE TABLE IF NOT EXISTS POINT_ACCOUNT (
  id VARCHAR(64) PRIMARY KEY,
  owner_user_id VARCHAR(64) NOT NULL,
  balance INT NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_point_account_owner (owner_user_id)
);

CREATE TABLE IF NOT EXISTS POINT_LEDGER (
  id VARCHAR(64) PRIMARY KEY,
  account_id VARCHAR(64) NOT NULL,
  owner_user_id VARCHAR(64) NOT NULL,
  change_amount INT NOT NULL,
  reason VARCHAR(128) NOT NULL,
  source_record_id VARCHAR(64) NULL,
  metadata_json JSON NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_point_ledger_owner (owner_user_id, created_at),
  INDEX ix_point_ledger_record (source_record_id)
);

CREATE TABLE IF NOT EXISTS REWARD_ITEM (
  id VARCHAR(64) PRIMARY KEY,
  owner_user_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NULL,
  cost_points INT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_reward_item_owner (owner_user_id, status)
);

CREATE TABLE IF NOT EXISTS REWARD_GRANT (
  id VARCHAR(64) PRIMARY KEY,
  reward_id VARCHAR(64) NOT NULL,
  from_user_id VARCHAR(64) NOT NULL,
  to_user_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_reward_grant_to_user (to_user_id, status),
  INDEX ix_reward_grant_reward (reward_id)
);

CREATE TABLE IF NOT EXISTS REWARD_REDEMPTION (
  id VARCHAR(64) PRIMARY KEY,
  reward_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  point_ledger_id VARCHAR(64) NULL,
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_reward_redemption_user (user_id, status),
  INDEX ix_reward_redemption_reward (reward_id)
);

CREATE TABLE IF NOT EXISTS OPS_AUDIT_LOG (
  id VARCHAR(64) PRIMARY KEY,
  operator_id VARCHAR(64) NOT NULL,
  action VARCHAR(128) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(64) NULL,
  payload_json JSON NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_ops_audit_operator (operator_id, created_at),
  INDEX ix_ops_audit_target (target_type, target_id)
);
