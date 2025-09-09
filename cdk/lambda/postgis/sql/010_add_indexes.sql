-- Useful indexes for query performance
CREATE INDEX IF NOT EXISTS deals_created_at_idx ON app.deals (created_at DESC);
CREATE INDEX IF NOT EXISTS deals_price_idx ON app.deals (price);
