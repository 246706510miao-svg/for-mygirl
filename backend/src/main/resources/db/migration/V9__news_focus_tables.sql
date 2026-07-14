CREATE TABLE IF NOT EXISTS NEWS_FOCUS_RUN (
  id VARCHAR(64) PRIMARY KEY,
  focus_date DATE NOT NULL,
  status VARCHAR(32) NOT NULL,
  source_count INT NOT NULL DEFAULT 0,
  candidate_count INT NOT NULL DEFAULT 0,
  selected_count INT NOT NULL DEFAULT 0,
  generated_at DATETIME NULL,
  error_text TEXT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_news_focus_run_date (focus_date),
  INDEX ix_news_focus_run_status_date (status, focus_date)
);

CREATE TABLE IF NOT EXISTS NEWS_FOCUS_ITEM (
  id VARCHAR(64) PRIMARY KEY,
  run_id VARCHAR(64) NOT NULL,
  rank_no INT NOT NULL,
  source_name VARCHAR(128) NOT NULL,
  source_url VARCHAR(2048) NOT NULL,
  title VARCHAR(500) NOT NULL,
  summary TEXT NOT NULL,
  score DECIMAL(4, 1) NOT NULL,
  tags_json JSON NOT NULL,
  published_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_news_focus_item_rank (run_id, rank_no),
  INDEX ix_news_focus_item_run (run_id, rank_no)
);
