CREATE TABLE IF NOT EXISTS APP_ACCOUNT (
  id VARCHAR(64) PRIMARY KEY,
  person_id VARCHAR(64) NOT NULL,
  login_name VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_app_account_person (person_id),
  UNIQUE KEY uq_app_account_login_name (login_name),
  INDEX ix_app_account_enabled (enabled)
);

CREATE TABLE IF NOT EXISTS APP_LOGIN_SESSION (
  id VARCHAR(64) PRIMARY KEY,
  account_id VARCHAR(64) NOT NULL,
  person_id VARCHAR(64) NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_app_login_session_token_hash (token_hash),
  INDEX ix_app_login_session_person (person_id, revoked_at, expires_at),
  INDEX ix_app_login_session_account (account_id)
);
