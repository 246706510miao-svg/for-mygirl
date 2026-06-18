INSERT INTO APP_PERSON (id, role, display_name, enabled, created_at)
VALUES
  ('person_user', 'USER', 'fjl', TRUE, UTC_TIMESTAMP()),
  ('person_admin', 'ADMIN', '管理员', TRUE, UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), enabled = VALUES(enabled);

INSERT INTO DAILY_CONTENT (
  id,
  target_user_id,
  created_by,
  content_date,
  content_type,
  display_area,
  content_json,
  resource_id,
  enabled,
  created_at,
  updated_at
)
VALUES
  (
    'content_default_home_text',
    'person_user',
    'person_admin',
    '2099-12-31',
    'text',
    'home',
    JSON_OBJECT('mainText', '今天也认真照顾自己', 'subText', '把完成过的小事写下来，慢慢看到自己的节奏。'),
    NULL,
    TRUE,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
  ),
  (
    'content_default_record_guide',
    'person_user',
    'person_admin',
    '2099-12-31',
    'reminder',
    'record_page',
    JSON_OBJECT('title', '今日记录引导', 'items', JSON_ARRAY('完成了什么', '遇到什么阻力', '明天想怎么调整')),
    NULL,
    TRUE,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
  )
ON DUPLICATE KEY UPDATE content_json = VALUES(content_json), enabled = VALUES(enabled), updated_at = UTC_TIMESTAMP();
