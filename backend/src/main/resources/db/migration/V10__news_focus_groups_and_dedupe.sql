ALTER TABLE NEWS_FOCUS_ITEM
  DROP INDEX uq_news_focus_item_rank,
  DROP COLUMN score,
  ADD COLUMN category_key VARCHAR(32) NOT NULL DEFAULT 'ai' AFTER run_id,
  ADD UNIQUE KEY uq_news_focus_item_category_rank (run_id, category_key, rank_no);

CREATE TABLE IF NOT EXISTS NEWS_FOCUS_SEEN (
  fingerprint VARCHAR(128) PRIMARY KEY,
  seen_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_news_focus_seen_at (seen_at)
);
