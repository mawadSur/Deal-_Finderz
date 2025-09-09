-- Recent deals from the last 30 days
CREATE MATERIALIZED VIEW IF NOT EXISTS app.deals_recent AS
SELECT *
FROM app.deals
WHERE created_at > now() - interval '30 days';

-- Optional helper index for fast ordering
CREATE INDEX IF NOT EXISTS deals_recent_created_at_idx ON app.deals_recent (created_at DESC);

