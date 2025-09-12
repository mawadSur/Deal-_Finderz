-- OpenAddresses nationwide address store
-- Idempotent: uses IF NOT EXISTS; safe to run multiple times.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.addresses (
  id BIGSERIAL PRIMARY KEY,
  number TEXT,
  street TEXT,
  unit TEXT,
  city TEXT,
  district TEXT,          -- county or similar admin unit if present
  region TEXT,            -- state (e.g., GA)
  postcode TEXT,
  lon DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  geom geometry(Point, 4326),
  hash TEXT,              -- OA hash field if present
  source TEXT NOT NULL DEFAULT 'openaddresses',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ensure geometry is present where lon/lat are provided
-- (Ingestion script will populate geom directly. This is a safety fixup.)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='app' AND table_name='addresses' AND column_name='geom') THEN
    -- nothing
    NULL;
  END IF;
END$$;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS addresses_geom_gix    ON app.addresses USING GIST (geom);
CREATE INDEX IF NOT EXISTS addresses_region_idx  ON app.addresses (region);
CREATE INDEX IF NOT EXISTS addresses_city_idx    ON app.addresses (city);
CREATE INDEX IF NOT EXISTS addresses_postcode_idx ON app.addresses (postcode);
CREATE INDEX IF NOT EXISTS addresses_created_at_idx ON app.addresses (created_at);

-- Materialized view that maps addresses into the deals shape so the UI can use them
DROP MATERIALIZED VIEW IF EXISTS app.deals_from_addresses;

CREATE MATERIALIZED VIEW app.deals_from_addresses AS
SELECT
  a.id,
  -- Title: "123 Main St Unit 4, City, ST 30301"
  CONCAT_WS(' ',
    NULLIF(a.number, ''),
    NULLIF(a.street, ''),
    CASE WHEN a.unit IS NOT NULL AND a.unit <> '' THEN CONCAT('Unit ', a.unit) ELSE NULL END
  ) || COALESCE(CONCAT(', ', NULLIF(a.city, '')), '') ||
    COALESCE(CONCAT(', ', NULLIF(a.region, '')), '') ||
    COALESCE(CONCAT(' ', NULLIF(a.postcode, '')), '')       AS title,
  0::NUMERIC(12,2) AS price,                                 -- unknown for OA, set 0
  NULL::TEXT AS url,
  'openaddresses'::TEXT AS source,
  a.created_at,
  ST_Y(a.geom) AS lat,
  ST_X(a.geom) AS lng,
  a.geom,
  NULL::TEXT AS zillow_id,
  NULL::NUMERIC(3,2) AS match_score,
  NULL::NUMERIC(10,2) AS distance_meters,
  NULL::NUMERIC(5,2) AS price_diff_percent,
  NULL::TEXT AS agent_name,
  NULL::TEXT AS agent_phone,
  NULL::TEXT AS agent_email,
  NULL::TEXT AS brokerage,
  -- Filter fields
  a.city,
  a.region AS state,
  a.district AS county,
  'residential'::TEXT AS property_category,   -- default category when unknown
  'house'::TEXT AS property_type,             -- default type when unknown
  NULL::INT AS bedrooms,
  NULL::NUMERIC(4,1) AS bathrooms,
  NULL::INT AS square_feet,
  NULL::NUMERIC(12,4) AS lot_size,
  FALSE AS has_pool,
  FALSE AS has_gym,
  FALSE AS pet_friendly,
  NULL::TEXT AS crime_rate,
  NULL::TEXT AS flood_zone,
  NULL::NUMERIC(4,2) AS school_rating,
  NULL::TEXT AS sewage_system,
  TRUE AS on_market                                -- considered listed/active for discovery
FROM app.addresses a
WHERE a.geom IS NOT NULL;

-- Indexes for the view (note: not all RDBMS support indexing MV columns directly; Postgres does)
CREATE INDEX IF NOT EXISTS deals_from_addresses_state_idx ON app.deals_from_addresses (state);
CREATE INDEX IF NOT EXISTS deals_from_addresses_city_idx  ON app.deals_from_addresses (city);
CREATE INDEX IF NOT EXISTS deals_from_addresses_geom_gix  ON app.deals_from_addresses USING GIST (geom);

-- Rebuild the unified deals_enriched to include OA data alongside native app.deals
DROP MATERIALIZED VIEW IF EXISTS app.deals_enriched;

CREATE MATERIALIZED VIEW app.deals_enriched AS
-- Native deals path
SELECT
    d.id,
    d.title,
    d.price,
    d.url,
    d.source,
    d.created_at,
    ST_X(dl.geom) AS lng,
    ST_Y(dl.geom) AS lat,
    dl.geom,
    m.zillow_id,
    m.match_score,
    m.distance_meters,
    m.price_diff_percent,
    c.agent_name,
    c.agent_phone,
    c.agent_email,
    c.brokerage,
    d.city,
    d.state,
    d.county,
    d.property_category,
    d.property_type,
    d.bedrooms,
    d.bathrooms,
    d.square_feet,
    d.lot_size,
    d.has_pool,
    d.has_gym,
    d.pet_friendly,
    d.crime_rate,
    d.flood_zone,
    d.school_rating,
    d.sewage_system,
    d.on_market
FROM app.deals d
LEFT JOIN app.deal_locations dl ON d.id = dl.deal_id
LEFT JOIN app.deal_zillow_matches m ON d.id = m.deal_id
LEFT JOIN app.zillow_contacts c ON d.id = c.deal_id AND m.zillow_id = c.zillow_id

UNION ALL

-- OpenAddresses as deal-like entries
SELECT
    da.id,
    da.title,
    da.price,
    da.url,
    da.source,
    da.created_at,
    da.lng,
    da.lat,
    da.geom,
    da.zillow_id,
    da.match_score,
    da.distance_meters,
    da.price_diff_percent,
    da.agent_name,
    da.agent_phone,
    da.agent_email,
    da.brokerage,
    da.city,
    da.state,
    da.county,
    da.property_category,
    da.property_type,
    da.bedrooms,
    da.bathrooms,
    da.square_feet,
    da.lot_size,
    da.has_pool,
    da.has_gym,
    da.pet_friendly,
    da.crime_rate,
    da.flood_zone,
    da.school_rating,
    da.sewage_system,
    da.on_market
FROM app.deals_from_addresses da;

-- Indexes for common UI filters
CREATE INDEX IF NOT EXISTS deals_enriched_price_idx ON app.deals_enriched (price);
CREATE INDEX IF NOT EXISTS deals_enriched_created_at_idx ON app.deals_enriched (created_at DESC);
CREATE INDEX IF NOT EXISTS deals_enriched_geom_gix ON app.deals_enriched USING GIST (geom);
CREATE INDEX IF NOT EXISTS deals_enriched_source_idx ON app.deals_enriched (source);
CREATE INDEX IF NOT EXISTS deals_enriched_score_idx ON app.deals_enriched (match_score DESC);
CREATE INDEX IF NOT EXISTS deals_enriched_lat_lng_idx ON app.deals_enriched (lat, lng);
CREATE INDEX IF NOT EXISTS deals_enriched_state_idx ON app.deals_enriched (state);
CREATE INDEX IF NOT EXISTS deals_enriched_category_idx ON app.deals_enriched (property_category);
CREATE INDEX IF NOT EXISTS deals_enriched_on_market_idx ON app.deals_enriched (on_market);