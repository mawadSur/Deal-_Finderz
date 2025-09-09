-- Create application schema and base tables
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.deals (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  price NUMERIC(12,2) NOT NULL,
  url TEXT,
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.import_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  notes TEXT
);

