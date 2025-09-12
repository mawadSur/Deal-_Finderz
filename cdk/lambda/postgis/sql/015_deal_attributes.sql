-- Extend deals table with attributes required by the UI and API
-- This migration is idempotent (uses IF NOT EXISTS)

CREATE SCHEMA IF NOT EXISTS app;

ALTER TABLE app.deals
  ADD COLUMN IF NOT EXISTS city TEXT,
  ADD COLUMN IF NOT EXISTS state TEXT,
  ADD COLUMN IF NOT EXISTS county TEXT,
  ADD COLUMN IF NOT EXISTS property_category TEXT,
  ADD COLUMN IF NOT EXISTS property_type TEXT,
  ADD COLUMN IF NOT EXISTS bedrooms INTEGER,
  ADD COLUMN IF NOT EXISTS bathrooms NUMERIC(4,1),
  ADD COLUMN IF NOT EXISTS square_feet INTEGER,
  ADD COLUMN IF NOT EXISTS lot_size NUMERIC(12,4), -- acres
  ADD COLUMN IF NOT EXISTS has_pool BOOLEAN,
  ADD COLUMN IF NOT EXISTS has_gym BOOLEAN,
  ADD COLUMN IF NOT EXISTS pet_friendly BOOLEAN,
  ADD COLUMN IF NOT EXISTS crime_rate TEXT,
  ADD COLUMN IF NOT EXISTS flood_zone TEXT,
  ADD COLUMN IF NOT EXISTS school_rating NUMERIC(4,2),
  ADD COLUMN IF NOT EXISTS sewage_system TEXT,
  ADD COLUMN IF NOT EXISTS on_market BOOLEAN;

-- Set sensible defaults for existing rows
UPDATE app.deals
SET on_market = COALESCE(on_market, TRUE);

-- Helpful indexes to speed up filters
CREATE INDEX IF NOT EXISTS deals_state_idx ON app.deals(state);
CREATE INDEX IF NOT EXISTS deals_city_idx ON app.deals(city);
CREATE INDEX IF NOT EXISTS deals_county_idx ON app.deals(county);
CREATE INDEX IF NOT EXISTS deals_category_idx ON app.deals(property_category);
CREATE INDEX IF NOT EXISTS deals_type_idx ON app.deals(property_type);
CREATE INDEX IF NOT EXISTS deals_on_market_idx ON app.deals(on_market);
CREATE INDEX IF NOT EXISTS deals_price_idx ON app.deals(price);
CREATE INDEX IF NOT EXISTS deals_created_at_idx ON app.deals(created_at);