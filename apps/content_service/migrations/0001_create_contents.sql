CREATE TABLE IF NOT EXISTS contents (
  content_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  summary_text TEXT NOT NULL DEFAULT '',
  body_text TEXT NOT NULL DEFAULT '',
  published_at TIMESTAMPTZ NULL,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  language TEXT NULL,
  authors JSONB NOT NULL DEFAULT '[]'::jsonb,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  media JSONB NOT NULL DEFAULT '[]'::jsonb,
  sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_count INT NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_contents_updated_at
  ON contents (updated_at ASC, content_id ASC);

CREATE INDEX IF NOT EXISTS idx_contents_published_at
  ON contents (published_at ASC);

CREATE INDEX IF NOT EXISTS idx_contents_sources_gin
  ON contents
  USING GIN (sources);

CREATE INDEX IF NOT EXISTS idx_contents_tags_gin
  ON contents
  USING GIN (tags);

CREATE TABLE IF NOT EXISTS subscriptions (
  subscription_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  timezone TEXT NOT NULL,
  cadence TEXT NOT NULL,
  delivery_channel TEXT NOT NULL,
  language TEXT NOT NULL,
  filters JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_cursor TEXT NULL,
  last_run_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled_created_at
  ON subscriptions (enabled ASC, created_at ASC);

CREATE TABLE IF NOT EXISTS delivery_runs (
  run_id TEXT PRIMARY KEY,
  subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  delivered_count INT NOT NULL DEFAULT 0,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_runs_subscription_started_at
  ON delivery_runs (subscription_id ASC, started_at DESC);
