ALTER TABLE APP_PERSON
  ADD COLUMN current_view_role VARCHAR(32) NOT NULL DEFAULT 'USER';

INSERT INTO APP_PERSON (id, role, display_name, enabled, created_at, current_view_role)
VALUES
  ('person_partner', 'USER', 'TA', TRUE, UTC_TIMESTAMP(), 'USER')
ON DUPLICATE KEY UPDATE role = 'USER', display_name = VALUES(display_name), enabled = TRUE;

UPDATE APP_PERSON
SET role = 'USER', display_name = 'fjl', current_view_role = 'USER'
WHERE id = 'person_user';

UPDATE APP_PERSON
SET role = 'OPS_ADMIN', display_name = '后台人员', current_view_role = 'OPS_ADMIN'
WHERE id = 'person_admin';

ALTER TABLE RECORD_COMMENT
  ADD COLUMN score INT NULL,
  ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD UNIQUE KEY uq_record_comment_record_author (record_id, author_user_id);

ALTER TABLE POINT_LEDGER
  ADD COLUMN source_type VARCHAR(64) NOT NULL DEFAULT 'manual',
  ADD COLUMN source_key VARCHAR(191) NOT NULL DEFAULT '',
  ADD UNIQUE KEY uq_point_ledger_source (owner_user_id, source_type, source_key);

ALTER TABLE REWARD_ITEM
  ADD COLUMN created_by_user_id VARCHAR(64) NULL,
  ADD COLUMN redeemed_at DATETIME NULL;

ALTER TABLE REWARD_REDEMPTION
  ADD COLUMN notified_at DATETIME NULL;

INSERT INTO USER_BINDING (id, requester_user_id, target_user_id, status, created_at, updated_at)
VALUES
  ('binding_user_partner', 'person_user', 'person_partner', 'active', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('binding_partner_user', 'person_partner', 'person_user', 'active', UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE status = 'active', updated_at = UTC_TIMESTAMP();

INSERT INTO USER_PERMISSION (id, binding_id, grantee_user_id, permission_key, enabled, created_at, updated_at)
VALUES
  ('perm_user_partner_comment', 'binding_user_partner', 'person_user', 'record.comment', TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('perm_user_partner_reward', 'binding_user_partner', 'person_user', 'reward.manage', TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('perm_partner_user_comment', 'binding_partner_user', 'person_partner', 'record.comment', TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('perm_partner_user_reward', 'binding_partner_user', 'person_partner', 'reward.manage', TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE enabled = TRUE, updated_at = UTC_TIMESTAMP();

INSERT INTO POINT_ACCOUNT (id, owner_user_id, balance, updated_at)
VALUES
  ('point_account_user', 'person_user', 0, UTC_TIMESTAMP()),
  ('point_account_partner', 'person_partner', 0, UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at);

INSERT INTO REWARD_ITEM (id, owner_user_id, title, description, cost_points, status, created_by_user_id, created_at, updated_at)
VALUES
  ('reward_user_movie', 'person_user', '一起看电影', '适合周末兑换的小奖励', 80, 'active', 'person_partner', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('reward_user_milk_tea', 'person_user', '奶茶一次', '管理员添加的轻量奖励', 35, 'active', 'person_partner', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('reward_user_praise', 'person_user', '认真夸夸 10 分钟', '不花钱但很有用', 20, 'active', 'person_partner', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('reward_partner_movie', 'person_partner', '一起看电影', '适合周末兑换的小奖励', 80, 'active', 'person_user', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('reward_partner_milk_tea', 'person_partner', '奶茶一次', '管理员添加的轻量奖励', 35, 'active', 'person_user', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
  ('reward_partner_praise', 'person_partner', '认真夸夸 10 分钟', '不花钱但很有用', 20, 'active', 'person_user', UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE title = VALUES(title), description = VALUES(description), cost_points = VALUES(cost_points);
