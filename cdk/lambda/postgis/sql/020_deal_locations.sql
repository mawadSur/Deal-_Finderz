-- Spatial locations for deals (PostGIS geometry)
CREATE TABLE IF NOT EXISTS app.deal_locations (
  id BIGSERIAL PRIMARY KEY,
  deal_id BIGINT NOT NULL REFERENCES app.deals(id) ON DELETE CASCADE,
  geom geometry(Point, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS deal_locations_geom_gix ON app.deal_locations USING GIST (geom);
CREATE INDEX IF NOT EXISTS deal_locations_deal_id_idx ON app.deal_locations (deal_id);

