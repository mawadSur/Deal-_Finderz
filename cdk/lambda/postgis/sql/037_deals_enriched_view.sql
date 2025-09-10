-- Materialized view for efficient UI queries with enriched data
CREATE MATERIALIZED VIEW IF NOT EXISTS app.deals_enriched AS
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
    c.brokerage
FROM app.deals d
LEFT JOIN app.deal_locations dl ON d.id = dl.deal_id
LEFT JOIN app.deal_zillow_matches m ON d.id = m.deal_id
LEFT JOIN app.zillow_contacts c ON d.id = c.deal_id AND m.zillow_id = c.zillow_id;

-- Indexes for common UI filters
CREATE INDEX IF NOT EXISTS deals_enriched_price_idx ON app.deals_enriched (price);
CREATE INDEX IF NOT EXISTS deals_enriched_created_at_idx ON app.deals_enriched (created_at DESC);
CREATE INDEX IF NOT EXISTS deals_enriched_geom_gix ON app.deals_enriched USING GIST (geom);
CREATE INDEX IF NOT EXISTS deals_enriched_source_idx ON app.deals_enriched (source);
CREATE INDEX IF NOT EXISTS deals_enriched_score_idx ON app.deals_enriched (match_score DESC);
CREATE INDEX IF NOT EXISTS deals_enriched_lat_lng_idx ON app.deals_enriched (lat, lng);